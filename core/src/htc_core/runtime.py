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


def settings_from_env() -> RuntimeSettings:
    database = Path(
        os.environ.get("HTC_DB", str(Path.home() / ".htc" / "htc.sqlite3"))
    ).expanduser()
    return RuntimeSettings(
        database_path=database,
        user_id=os.environ.get("HTC_USER_ID", "local-user"),
        timezone=os.environ.get("HTC_TIMEZONE", "Asia/Shanghai"),
        allow_plaintext_candidates=os.environ.get("HTC_ALLOW_PLAINTEXT_CANDIDATES") == "1",
    )


def open_runtime(settings: RuntimeSettings | None = None) -> SilentCore:
    resolved = settings or settings_from_env()
    resolved.database_path.parent.mkdir(parents=True, exist_ok=True)
    return SilentCore(SQLiteRepository(resolved.database_path))
