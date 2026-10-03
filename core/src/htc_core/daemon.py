from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import uuid
from datetime import datetime
from http.server import HTTPServer
from typing import Any
from zoneinfo import ZoneInfo

from .client import DaemonUnavailable, HtcClient, RpcError, RuntimeManifest
from .http_api import create_server
from .runtime import RuntimeSettings, settings_from_env


class InstanceLock:
    def __init__(self, path) -> None:
        self.path = path
        self.file = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise RuntimeError("htc_daemon_already_running") from exc
        self.file.seek(0)
        self.file.truncate()
        self.file.write(str(os.getpid()).encode("ascii"))
        self.file.flush()

    def release(self) -> None:
        if self.file is None:
            return
        self.file.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()
            self.file = None


def create_daemon_server(
    settings: RuntimeSettings | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> HTTPServer:
    resolved = settings or settings_from_env()
    instance_lock = InstanceLock(resolved.resolved_runtime_dir / "htcd.lock")
    database_path = resolved.database_path.expanduser().resolve()
    database_lock = InstanceLock(database_path.with_name(database_path.name + ".writer.lock"))
    instance_lock.acquire()

    def release_locks() -> None:
        try:
            database_lock.release()
        finally:
            instance_lock.release()

    token = secrets.token_urlsafe(32)
    server = None
    try:
        database_lock.acquire()
        server = create_server(resolved, host=host, port=port, auth_token=token)
        manifest = RuntimeManifest(
            version=1,
            host=str(server.server_address[0]),
            port=int(server.server_address[1]),
            pid=os.getpid(),
            token=token,
            started_at=datetime.now(ZoneInfo(resolved.timezone)).isoformat(timespec="seconds"),
        )
        manifest.write(resolved.manifest_path)
    except Exception:
        try:
            if server is not None:
                server.server_close()
        finally:
            release_locks()
        raise
    original_close = server.server_close

    def close_and_remove_manifest() -> None:
        try:
            original_close()
        finally:
            try:
                try:
                    current = RuntimeManifest.load(resolved.manifest_path)
                except (OSError, ValueError, KeyError):
                    current = None
                if current == manifest:
                    resolved.manifest_path.unlink(missing_ok=True)
            finally:
                release_locks()

    server.server_close = close_and_remove_manifest  # type: ignore[method-assign]
    return server


def replay_spool(
    settings: RuntimeSettings | None = None,
    *,
    dispatcher: Any | None = None,
) -> int:
    resolved = settings or settings_from_env()
    if not resolved.spool_dir.exists():
        return 0
    replay_lock = InstanceLock(resolved.spool_dir / "replay.lock")
    try:
        replay_lock.acquire()
    except RuntimeError:
        return 0
    try:
        return _replay_spool(resolved, dispatcher=dispatcher)
    finally:
        replay_lock.release()


def _replay_spool(resolved: RuntimeSettings, *, dispatcher: Any | None) -> int:
    replaying_dir = resolved.spool_dir / "replaying"
    failed_dir = resolved.spool_dir / "failed"
    replaying_dir.mkdir(parents=True, exist_ok=True)
    replayed = 0
    client = HtcClient(resolved)
    # Recover claims left by a crash, including requests committed before ACK.
    paths = sorted(replaying_dir.glob("*.jsonl")) + sorted(resolved.spool_dir.glob("*.jsonl"))
    for path in paths:
        staging = replaying_dir / path.name
        try:
            if path != staging:
                if staging.exists():
                    continue
                os.replace(path, staging)
            envelope = json.loads(staging.read_text(encoding="utf-8"))
            if (
                not isinstance(envelope, dict)
                or envelope.get("v") != 1
                or not isinstance(envelope.get("payload"), dict)
                or not isinstance(envelope.get("idempotency_key"), str)
                or not envelope["idempotency_key"]
                or envelope.get("op") not in {
                    "codex.user_prompt_submit", "codex.stop",
                    "codex.user_prompt_hash", "codex.stop_hash",
                }
            ):
                raise ValueError("invalid_spool_envelope")
            if dispatcher is None:
                result = client.call(
                    envelope["op"],
                    envelope["payload"],
                    idempotency_key=envelope["idempotency_key"],
                )
                succeeded = result is not None
            else:
                reply = dispatcher.dispatch(envelope)
                succeeded = bool(reply.get("ok"))
                if not succeeded and not reply.get("error", {}).get("retryable", False):
                    raise RpcError(
                        str(reply.get("error", {}).get("code", "rpc_error")),
                        retryable=False,
                    )
            if not succeeded:
                raise DaemonUnavailable("spool_replay_retryable")
            staging.unlink()
            replayed += 1
        except RpcError as error:
            if error.retryable:
                continue
            _quarantine(staging, failed_dir)
        except (ValueError, KeyError, TypeError):
            _quarantine(staging, failed_dir)
        except (OSError, RuntimeError):
            # Leave the claim recoverable on network/auth/filesystem failures.
            continue
    return replayed


def _quarantine(staging, failed_dir) -> None:
    failed_dir.mkdir(parents=True, exist_ok=True)
    target = failed_dir / staging.name
    if target.exists():
        target = failed_dir / f"{staging.stem}-{uuid.uuid4().hex}.jsonl"
    os.replace(staging, target)


def main() -> None:
    settings = settings_from_env()
    server = create_daemon_server(settings)
    dispatcher = server.RequestHandlerClass.dispatcher
    stopped = threading.Event()

    def replay_periodically() -> None:
        while not stopped.wait(5):
            try:
                replay_spool(settings)
            except OSError:
                # A temporarily inaccessible spool must not end future replay.
                continue

    replay_thread = threading.Thread(target=replay_periodically, daemon=True)
    try:
        replayed = replay_spool(settings, dispatcher=dispatcher)
        print(
            "HTC daemon listening on "
            f"http://{server.server_address[0]}:{server.server_address[1]} "
            f"(replayed={replayed})",
            flush=True,
        )
        replay_thread.start()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        if replay_thread.ident is not None:
            replay_thread.join(timeout=6)
        server.server_close()


if __name__ == "__main__":
    main()
