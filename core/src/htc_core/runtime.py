from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .core import SilentCore
from .repository import SQLiteRepository


@dataclass(frozen=True)
class RuntimeSettings:
    database_path: Path
    user_id: str
    timezone: str
    allow_plaintext_candidates: bool = False
    runtime_dir: Path | None = None

    @property
    def resolved_runtime_dir(self) -> Path:
        return (self.runtime_dir or self.database_path.parent).expanduser()

    @property
    def manifest_path(self) -> Path:
        return self.resolved_runtime_dir / "runtime.json"

    @property
    def spool_dir(self) -> Path:
        return self.resolved_runtime_dir / "spool"


def settings_from_env() -> RuntimeSettings:
    data_home = Path(
        os.environ.get("HTC_DATA_HOME", str(Path.home() / ".htc"))
    ).expanduser()
    database = Path(
        os.environ.get("HTC_DB", str(data_home / "htc.sqlite3"))
    ).expanduser()
    identity_path = data_home / "identity.json"
    user_id = os.environ.get("HTC_USER_ID")
    if not user_id and identity_path.is_file():
        try:
            import json

            identity = json.loads(identity_path.read_text(encoding="utf-8"))
            if isinstance(identity, dict) and isinstance(identity.get("user_id"), str):
                user_id = identity["user_id"]
        except (OSError, UnicodeDecodeError, ValueError):
            user_id = None
    return RuntimeSettings(
        database_path=database,
        user_id=user_id or "local-user",
        timezone=os.environ.get("HTC_TIMEZONE", "Asia/Shanghai"),
        allow_plaintext_candidates=os.environ.get("HTC_ALLOW_PLAINTEXT_CANDIDATES") == "1",
        runtime_dir=(
            Path(os.environ["HTC_RUNTIME_DIR"]).expanduser()
            if os.environ.get("HTC_RUNTIME_DIR")
            else data_home
        ),
    )


def open_runtime(settings: RuntimeSettings | None = None) -> SilentCore:
    resolved = settings or settings_from_env()
    resolved.database_path.parent.mkdir(parents=True, exist_ok=True)
    return SilentCore(SQLiteRepository(resolved.database_path))
