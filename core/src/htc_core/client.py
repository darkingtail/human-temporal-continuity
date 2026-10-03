from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .runtime import RuntimeSettings, settings_from_env


class DaemonUnavailable(RuntimeError):
    pass


class RpcError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class RuntimeManifest:
    version: int
    host: str
    port: int
    pid: int
    token: str
    started_at: str

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @classmethod
    def load(cls, path: Path) -> RuntimeManifest:
        value = json.loads(path.read_text(encoding="utf-8"))
        manifest = cls(
            version=int(value["version"]),
            host=str(value["host"]),
            port=int(value["port"]),
            pid=int(value["pid"]),
            token=str(value["token"]),
            started_at=str(value["started_at"]),
        )
        try:
            is_loopback = (
                manifest.host == "localhost"
                or ipaddress.ip_address(manifest.host).is_loopback
            )
        except ValueError as exc:
            raise ValueError("runtime_host_must_be_loopback") from exc
        if not is_loopback:
            raise ValueError("runtime_host_must_be_loopback")
        if manifest.version != 1 or not manifest.token:
            raise ValueError("invalid_runtime_manifest")
        return manifest

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}-{os.getpid()}-{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        os.replace(temporary, path)
        path.chmod(0o600)


class SpoolWriter:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def append(self, envelope: dict[str, Any]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        key = str(envelope["idempotency_key"])
        target = self.directory / f"{key}.jsonl"
        if target.exists():
            return target
        temporary = self.directory / f".{key}-{uuid.uuid4().hex}.tmp"
        temporary.write_text(
            json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        temporary.chmod(0o600)
        try:
            os.replace(temporary, target)
            target.chmod(0o600)
        finally:
            temporary.unlink(missing_ok=True)
        return target


class HtcClient:
    def __init__(
        self,
        settings: RuntimeSettings | None = None,
        *,
        timeout: float = 5.0,
    ) -> None:
        self.settings = settings or settings_from_env()
        self.timeout = timeout
        self.spool = SpoolWriter(self.settings.spool_dir)

    @staticmethod
    def idempotency_key(op: str, payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            {"op": op, "payload": payload},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:32]

    def codex_event_idempotency_key(
        self,
        op: str,
        event: dict[str, Any],
        *,
        role: str,
        content: str | None = None,
        content_hash: str | None = None,
    ) -> str:
        resolved_hash = content_hash or hashlib.sha256((content or "").encode("utf-8")).hexdigest()
        identity = "\0".join(
            (
                self.settings.user_id,
                op,
                "codex",
                str(event.get("session_id", "")),
                str(event.get("turn_id", "")),
                role,
                resolved_hash,
            )
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]

    def spool_envelope(
        self,
        op: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> Path:
        return self.spool.append(
            {
                "v": 1,
                "op": op,
                "idempotency_key": idempotency_key,
                "payload": payload,
            }
        )

    @staticmethod
    def _pid_is_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            # On Windows signal 0 is CTRL_C_EVENT, not a harmless PID probe.
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel32.CloseHandle.restype = wintypes.BOOL
            if pid > 0xFFFFFFFF:
                return False
            handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
            if not handle:
                return False
            try:
                return kernel32.WaitForSingleObject(handle, 0) == 0x00000102  # WAIT_TIMEOUT
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def call(
        self,
        op: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        spool_on_failure: bool = False,
    ) -> dict[str, Any] | None:
        resolved_key = idempotency_key
        if resolved_key is None and op in {"codex.user_prompt_submit", "codex.stop"}:
            event = payload.get("event")
            if isinstance(event, dict):
                content_key = "prompt" if op == "codex.user_prompt_submit" else "last_assistant_message"
                role = "user" if op == "codex.user_prompt_submit" else "assistant"
                content = event.get(content_key) or ""
                if isinstance(content, str):
                    resolved_key = self.codex_event_idempotency_key(
                        op,
                        event,
                        role=role,
                        content=content,
                    )
        envelope = {
            "v": 1,
            "op": op,
            "idempotency_key": resolved_key or self.idempotency_key(op, payload),
            "payload": payload,
        }
        try:
            manifest = RuntimeManifest.load(self.settings.manifest_path)
            if not self._pid_is_alive(manifest.pid):
                raise DaemonUnavailable("stale_runtime_manifest")
            request = urllib.request.Request(
                manifest.base_url + "/rpc",
                data=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {manifest.token}",
                },
            )
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=self.timeout) as response:
                reply = json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"http_{exc.code}") from exc
        except (OSError, ValueError, KeyError, urllib.error.URLError, DaemonUnavailable) as exc:
            if spool_on_failure:
                self.spool.append(envelope)
                return None
            raise DaemonUnavailable("htc_daemon_unavailable") from exc
        if not reply.get("ok"):
            error = reply.get("error", {})
            if spool_on_failure and error.get("retryable") is True:
                self.spool.append(envelope)
                return None
            raise RpcError(
                str(error.get("code", "rpc_error")),
                retryable=error.get("retryable") is True,
            )
        result = reply.get("result", {})
        if not isinstance(result, dict):
            raise RuntimeError("invalid_rpc_result")
        return result
