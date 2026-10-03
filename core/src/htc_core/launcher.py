from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from .client import HtcClient, RuntimeManifest
from .runtime import RuntimeSettings, settings_from_env


class _BootstrapLock:
    def __init__(self, path: Path) -> None:
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
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            self.file = None
            raise

    def release(self) -> None:
        if self.file is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        finally:
            self.file.close()
            self.file = None


def _manifest_is_live(settings: RuntimeSettings) -> bool:
    try:
        manifest = RuntimeManifest.load(settings.manifest_path)
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return HtcClient._pid_is_alive(manifest.pid)


def _child_environment(settings: RuntimeSettings, package_root: Path | None) -> dict[str, str]:
    environment = {
        **os.environ,
        "HTC_DB": str(settings.database_path),
        "HTC_RUNTIME_DIR": str(settings.resolved_runtime_dir),
        "HTC_USER_ID": settings.user_id,
        "HTC_TIMEZONE": settings.timezone,
    }
    if package_root is not None:
        current = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = (
            str(package_root) if not current else str(package_root) + os.pathsep + current
        )
    return environment


def ensure_runtime(
    settings: RuntimeSettings | None = None,
    *,
    python_executable: Path | None = None,
    package_root: Path | None = None,
    timeout: float = 2.0,
) -> bool:
    resolved = settings or settings_from_env()
    if _manifest_is_live(resolved):
        return True
    deadline = time.monotonic() + max(0.1, timeout)
    lock = _BootstrapLock(resolved.resolved_runtime_dir / "bootstrap.lock")
    while True:
        try:
            lock.acquire()
            break
        except OSError:
            if _manifest_is_live(resolved):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return _manifest_is_live(resolved)
            time.sleep(min(0.05, remaining))
    process = None
    try:
        if _manifest_is_live(resolved):
            return True
        executable = python_executable or Path(sys.executable)
        if not executable.is_file():
            return False
        log_dir = resolved.resolved_runtime_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / "htcd.stdout.log"
        stderr_path = log_dir / "htcd.stderr.log"
        environment = _child_environment(resolved, package_root)
        creationflags = 0
        if os.name == "nt":
            creationflags = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            )
        with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
            process = subprocess.Popen(
                [str(executable), "-m", "htc_core.daemon"],
                cwd=str(resolved.resolved_runtime_dir),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                creationflags=creationflags,
                # Do not let the detached daemon inherit Codex's Hook pipes.
                # On Windows that keeps the parent waiting for EOF forever.
                close_fds=True,
            )
        deadline = time.monotonic() + max(0.1, timeout)
        while time.monotonic() < deadline:
            if _manifest_is_live(resolved):
                return True
            if process.poll() is not None:
                return False
            time.sleep(0.05)
        return _manifest_is_live(resolved)
    except (OSError, ValueError):
        return False
    finally:
        lock.release()


def runtime_status(settings: RuntimeSettings | None = None) -> dict[str, object]:
    resolved = settings or settings_from_env()
    try:
        manifest = RuntimeManifest.load(resolved.manifest_path)
    except (OSError, ValueError, KeyError, TypeError):
        return {
            "running": False,
            "runtime_dir": str(resolved.resolved_runtime_dir),
            "manifest": str(resolved.manifest_path),
        }
    return {
        "running": HtcClient._pid_is_alive(manifest.pid),
        "pid": manifest.pid,
        "host": manifest.host,
        "port": manifest.port,
        "runtime_dir": str(resolved.resolved_runtime_dir),
        "manifest": str(resolved.manifest_path),
    }
