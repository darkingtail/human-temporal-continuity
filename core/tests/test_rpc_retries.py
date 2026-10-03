from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from htc_core.client import HtcClient
from htc_core.codex_adapter import handle_user_prompt_submit
from htc_core.daemon import create_daemon_server
from htc_core.runtime import RuntimeSettings


@pytest.fixture
def runtime(tmp_path: Path):
    settings = RuntimeSettings(tmp_path / "memory.sqlite3", "retry-user", "Asia/Shanghai", True)
    server = create_daemon_server(settings, port=0)
    try:
        yield settings, server.RequestHandlerClass.dispatcher
    finally:
        server.server_close()


def seed_memory(settings, dispatcher):
    now = datetime.now(ZoneInfo(settings.timezone)).isoformat()
    core = dispatcher.core
    result = core.observe(
        {
            "user_id": settings.user_id, "conversation_id": "source", "turn_id": "source",
            "observed_at": now, "role": "user", "text": "remember a synthetic preference",
        },
        {
            "candidate_id": "retry-candidate", "kind": "Meaning",
            "summary": "synthetic preference", "speech_act": "actual",
        },
    )
    return core.decide(result["candidate_ids"][0], "accept", now)["memory_id"]


def envelope_for(settings, operation):
    client = HtcClient(settings)
    now = datetime.now(ZoneInfo(settings.timezone)).isoformat()
    if operation == "recall.request":
        payload = {
            "conversation_id": "retry-target", "query": "synthetic preference",
            "purpose": "reply", "now": now, "ttl_minutes": 10,
        }
        key = client.idempotency_key(operation, payload)
    else:
        payload = {
            "event": {
                "session_id": "retry-target", "turn_id": "one",
                "prompt": "synthetic preference",
            },
            "observed_at": now,
        }
        key = client.codex_event_idempotency_key(
            operation, payload["event"], role="user", content=payload["event"]["prompt"],
        )
    return {"v": 1, "op": operation, "payload": payload, "idempotency_key": key}


@pytest.mark.parametrize(
    "prompt", [" tomorrow", "tomorrow\n", "x" * 10001],
    ids=["leading-space", "trailing-newline", "over-limit"],
)
def test_hook_normalization_matches_rpc_key(runtime, monkeypatch, prompt):
    settings, dispatcher = runtime

    def call(self, operation, payload, *, idempotency_key):
        reply = dispatcher.dispatch(
            {"v": 1, "op": operation, "payload": payload, "idempotency_key": idempotency_key}
        )
        assert reply["ok"], reply
        return reply["result"]

    monkeypatch.setattr(HtcClient, "call", call)
    assert handle_user_prompt_submit(
        {"session_id": "normalized", "turn_id": "one", "prompt": prompt}, settings=settings,
    ) == {}
    assert dispatcher.core.repo.db.execute("SELECT COUNT(*) FROM adapter_events").fetchone()[0] == 1


@pytest.mark.parametrize("operation", ["recall.request", "codex.user_prompt_submit"])
def test_response_loss_retry_returns_original_context_without_duplicate_usage(runtime, operation):
    settings, dispatcher = runtime
    memory_id = seed_memory(settings, dispatcher)
    envelope = envelope_for(settings, operation)
    first = dispatcher.dispatch(envelope)
    assert first["ok"] and "synthetic preference" in str(first["result"])
    retry = dispatcher.dispatch(envelope)
    assert retry == first
    db = dispatcher.core.repo.db
    assert db.execute("SELECT COUNT(*) FROM recall_packages").fetchone()[0] == 1
    usage = dispatcher.core.repo.memory_recall_usage(memory_id, "retry-target")
    assert usage["recall_count"] == 1
    receipt_text = db.execute("SELECT response_json FROM rpc_receipts").fetchone()[0]
    assert "synthetic preference" not in receipt_text


def test_recall_retry_rejects_same_key_for_different_request(runtime):
    settings, dispatcher = runtime
    envelope = envelope_for(settings, "recall.request")
    assert dispatcher.dispatch(envelope)["ok"]
    envelope["payload"]["query"] = "different query"
    retry = dispatcher.dispatch(envelope)
    assert retry["error"]["code"] == "idempotency_conflict"
    assert dispatcher.core.repo.db.execute("SELECT COUNT(*) FROM recall_packages").fetchone()[0] == 1


@pytest.mark.parametrize("operation", ["recall.request", "codex.user_prompt_submit"])
@pytest.mark.parametrize("invalidate", ["revoke", "expire"])
def test_retry_never_returns_revoked_or_expired_memory(runtime, operation, invalidate):
    settings, dispatcher = runtime
    memory_id = seed_memory(settings, dispatcher)
    envelope = envelope_for(settings, operation)
    assert "synthetic preference" in str(dispatcher.dispatch(envelope))
    now = datetime.now(ZoneInfo(settings.timezone))
    if invalidate == "revoke":
        dispatcher.core.set_permissions(memory_id, now.isoformat(), recall_allowed=False)
    else:
        dispatcher.core.repo.db.execute(
            "UPDATE recall_packages SET expires_at=?", ((now - timedelta(seconds=1)).isoformat(),),
        )
    retry = dispatcher.dispatch(envelope)
    assert "synthetic preference" not in str(retry)
    assert dispatcher.core.repo.db.execute("SELECT COUNT(*) FROM recall_packages").fetchone()[0] == 1


def test_hash_only_predecessor_can_be_retried_online(runtime):
    settings, dispatcher = runtime
    seed_memory(settings, dispatcher)
    envelope = envelope_for(settings, "codex.user_prompt_submit")
    event = envelope["payload"]["event"]
    content_hash = hashlib.sha256(event["prompt"].encode()).hexdigest()
    operation = "codex.user_prompt_hash"
    payload = {
        "event": {"session_id": event["session_id"], "turn_id": event["turn_id"]},
        "content_hash": content_hash, "content_chars": len(event["prompt"]),
    }
    offline = {
        "v": 1, "op": operation, "payload": payload,
        "idempotency_key": HtcClient(settings).codex_event_idempotency_key(
            operation, event, role="user", content_hash=content_hash,
        ),
    }
    assert dispatcher.dispatch(offline)["ok"]
    online = dispatcher.dispatch(envelope)
    assert online["ok"], online
    assert "synthetic preference" in str(online["result"])
    assert dispatcher.dispatch(envelope) == online
    assert dispatcher.dispatch(offline)["ok"]
    assert dispatcher.dispatch(envelope) == online
    events = dispatcher.core.repo.adapter_events(settings.user_id)
    assert len(events) == 1
    assert events[0]["payload"]["recall_package_id"]
    assert dispatcher.core.repo.db.execute("SELECT COUNT(*) FROM recall_packages").fetchone()[0] == 1


def test_same_turn_different_content_cannot_rebind_adapter_event(runtime):
    settings, dispatcher = runtime
    envelope = envelope_for(settings, "codex.user_prompt_submit")
    assert dispatcher.dispatch(envelope)["ok"]
    original = dispatcher.core.repo.adapter_events(settings.user_id)
    envelope["payload"]["event"]["prompt"] = "different synthetic content"
    envelope["idempotency_key"] = HtcClient(settings).codex_event_idempotency_key(
        envelope["op"], envelope["payload"]["event"],
        role="user", content="different synthetic content",
    )
    reply = dispatcher.dispatch(envelope)
    assert reply["error"]["code"] == "adapter_event_content_conflict"
    assert dispatcher.core.repo.adapter_events(settings.user_id) == original
    assert dispatcher.core.repo.db.execute("SELECT COUNT(*) FROM recall_packages").fetchone()[0] == 1


def test_hook_retry_after_receipt_retention_does_not_repeat_side_effects(runtime):
    settings, dispatcher = runtime
    seed_memory(settings, dispatcher)
    envelope = envelope_for(settings, "codex.user_prompt_submit")
    first = dispatcher.dispatch(envelope)
    assert first["ok"] and "synthetic preference" in str(first["result"])
    db = dispatcher.core.repo.db
    db.execute("UPDATE rpc_receipts SET created_at='2000-01-01T00:00:00+08:00'")
    assert dispatcher.dispatch(envelope) == first
    assert db.execute("SELECT COUNT(*) FROM recall_packages").fetchone()[0] == 1
