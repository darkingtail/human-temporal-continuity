from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load(value: str | None, default: Any = None) -> Any:
    return default if value is None else json.loads(value)


@dataclass(frozen=True)
class Observation:
    id: str
    user_id: str
    conversation_id: str
    turn_id: str
    observed_at: str
    timezone: str
    role: str
    content_hash: str
    excerpt: str
    speech_act: str = "actual"


@dataclass(frozen=True)
class Candidate:
    id: str
    observation_id: str
    user_id: str
    kind: str
    summary: str
    speech_act: str
    status: str = "pending"
    confidence: float = 1.0
    time: dict[str, Any] = field(default_factory=dict)
    sensitivity: str = "normal"
    permissions: dict[str, bool] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Memory:
    id: str
    user_id: str
    kind: str
    summary: str
    epistemic_status: str
    speech_act: str
    time: dict[str, Any]
    sensitivity: str
    intention_state: str | None
    outcome: str | None
    persist_consent: bool
    cross_session_consent: bool
    proactive_consent: bool
    revision: int
    revocation_epoch: int
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecallItem:
    memory_id: str
    category: str
    summary: str | None
    guidance: str | None
    source_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class RecallPackage:
    id: str
    user_id: str
    conversation_id: str
    purpose: str
    issued_at: str
    expires_at: str
    package_version: int
    revocation_epoch: int
    items: tuple[RecallItem, ...]


@dataclass(frozen=True)
class ImportSource:
    id: str
    user_id: str
    kind: str
    locator: str
    authorization_scope: str
    content_hash: str | None
    created_at: str


@dataclass(frozen=True)
class ImportJob:
    id: str
    source_id: str
    user_id: str
    status: str
    total_records: int
    processed_records: int
    candidate_ids: tuple[str, ...]
    started_at: str | None
    finished_at: str | None
    error: str | None


@dataclass(frozen=True)
class BootstrapSnapshot:
    id: str
    user_id: str
    mode: str
    source_ids: tuple[str, ...]
    job_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    established_at: str
