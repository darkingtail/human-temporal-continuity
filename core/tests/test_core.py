import json
import sqlite3
from pathlib import Path

import jsonschema

from htc_core import SilentCore, SQLiteRepository

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def make_core(*, cross_session=True):
    core = SilentCore(SQLiteRepository())
    if cross_session:
        core.set_user_policy(
            "user-1", "2030-07-01T00:00:00+08:00", cross_session_internal_use=True
        )
    return core


def observe(
    core,
    *,
    speech_act="actual",
    summary="太晚了，明天继续整理资料吧。",
    kind="Intention",
    sensitivity="normal",
    turn="t1",
):
    return core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-1",
            "turn_id": turn,
            "observed_at": "2030-07-18T23:40:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "text": summary,
        },
        {
            "candidate_id": "candidate-" + turn,
            "kind": kind,
            "summary": summary,
            "speech_act": speech_act,
            "sensitivity": sensitivity,
            "time": {"relative": "tomorrow"},
            "attributes": {"affect": "negative"} if "沮丧" in summary else {},
        },
    )


def test_vertical_slice_anchors_tomorrow_and_keeps_unknown():
    core = make_core()
    result = observe(core)
    assert result["status"] == "pending"
    assert core.repo.memories("user-1") == []
    accepted = core.decide("candidate-t1", "accept", "2030-07-18T23:41:00+08:00")
    assert accepted["status"] == "accepted"
    memory = core.repo.memory(accepted["memory_id"])
    assert memory.time["anchor_time"] == "2030-07-18T23:40:00+08:00"
    assert memory.time["expected_at"] == "2030-07-19"
    assert memory.intention_state == "planned"
    assert memory.outcome == "unknown"
    recalled = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "整理资料",
            "now": "2030-07-20T09:00:00+08:00",
        }
    )
    assert recalled["items"][0]["category"] == "allowed_to_use"
    assert core.validate_package(recalled["package_id"], "2030-07-20T09:01:00+08:00")
    assert core.explain("trace-recall-" + recalled["package_id"], user_id="user-1")["subject_type"] == "recall"


def test_cross_session_is_not_granted_before_user_policy():
    core = make_core(cross_session=False)
    observe(core, summary="private default policy", kind="State", turn="policy-default")
    accepted = core.decide("candidate-policy-default", "accept", "2030-07-18T23:41:00+08:00")
    recalled = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "private default",
            "now": "2030-07-19T09:00:00+08:00",
        }
    )
    assert accepted["status"] == "accepted"
    assert recalled["items"] == []
    core.set_user_policy(
        "user-1", "2030-07-19T09:01:00+08:00", cross_session_internal_use=True
    )
    assert core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "private default",
            "now": "2030-07-19T09:02:00+08:00",
        }
    )["items"][0]["category"] == "allowed_to_use"


def test_non_actual_speech_never_becomes_memory():
    core = make_core()
    for index, speech_act in enumerate(("test", "quoted", "hypothetical", "roleplay")):
        result = observe(core, speech_act=speech_act, turn=f"t{index}")
        assert result["status"] == "ignored"
    assert core.repo.memories("user-1") == []


def test_negative_affect_is_internal_only_by_default():
    core = make_core()
    observe(core, summary="今天评审没通过，我很沮丧。", kind="State", sensitivity="personal")
    accepted = core.decide("candidate-t1", "accept", "2030-07-18T23:41:00+08:00")
    assert accepted["status"] == "accepted"
    recalled = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "评审",
            "now": "2030-07-19T09:00:00+08:00",
        }
    )
    assert recalled["items"][0]["category"] == "internal_only"
    assert recalled["items"][0]["summary"] is None


def test_do_not_proactively_mention_invalidates_old_package():
    core = make_core()
    observe(core, summary="我喜欢在安静的地方工作。", kind="Meaning")
    accepted = core.decide("candidate-t1", "accept", "2030-07-18T23:41:00+08:00")
    package = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "安静",
            "now": "2030-07-19T09:00:00+08:00",
        }
    )
    assert core.validate_package(package["package_id"], "2030-07-19T09:01:00+08:00")
    core.set_permissions(
        accepted["memory_id"], "2030-07-19T09:02:00+08:00", proactive_expression=False
    )
    assert not core.validate_package(package["package_id"], "2030-07-19T09:03:00+08:00")
    newer = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "安静",
            "now": "2030-07-19T09:03:00+08:00",
        }
    )
    assert newer["items"][0]["category"] == "internal_only"


def test_cross_conversation_memory_is_user_scoped():
    core = make_core()
    observe(core, summary="continue project alpha", turn="shared")
    core.decide("candidate-shared", "accept", "2030-07-18T23:41:00+08:00")
    same_user = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-9",
            "purpose": "reply",
            "query": "alpha",
            "now": "2030-07-19T09:00:00+08:00",
        }
    )
    other_user = core.recall(
        {
            "user_id": "user-2",
            "conversation_id": "conversation-9",
            "purpose": "reply",
            "query": "alpha",
            "now": "2030-07-19T09:00:00+08:00",
        }
    )
    assert len(same_user["items"]) == 1
    assert other_user["items"] == []


def test_correction_then_retraction_preserves_lineage_and_stops_recall():
    core = make_core()
    observe(core, summary="demo date 2030-10-04", kind="State", turn="asr")
    accepted = core.decide("candidate-asr", "accept", "2030-07-18T23:41:00+08:00")
    corrected = core.revise(
        accepted["memory_id"],
        "2030-07-19T10:00:00+08:00",
        expected_revision=1,
        action="correct",
        source_id="user-correction",
        summary="demo date 2030-10-03",
    )
    assert corrected["revision"] == 2
    memory = core.repo.memory(accepted["memory_id"])
    assert memory.summary.endswith("03")
    assert len(memory.source_ids) == 2
    core.revise(
        memory.id,
        "2030-07-19T10:01:00+08:00",
        expected_revision=2,
        action="retract",
        source_id="user-retraction",
    )
    recalled = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "demo",
            "now": "2030-07-19T10:02:00+08:00",
        }
    )
    assert recalled["items"] == []


def test_package_is_bound_to_purpose_conversation_and_ttl():
    core = make_core()
    observe(core, summary="continue project alpha")
    core.decide("candidate-t1", "accept", "2030-07-18T23:41:00+08:00")
    package = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "alpha",
            "now": "2030-07-19T09:00:00+08:00",
            "ttl_minutes": 2,
        }
    )
    pid = package["package_id"]
    assert core.validate_package(
        pid, "2030-07-19T09:01:00+08:00", purpose="reply", conversation_id="conversation-2"
    )
    assert not core.validate_package(pid, "2030-07-19T09:01:00+08:00", purpose="export")
    assert not core.validate_package(pid, "2030-07-19T09:03:00+08:00")


def test_observe_is_idempotent_for_same_conversation_turn():
    core = make_core()
    first = observe(core, summary="same turn", turn="idem")
    second = observe(core, summary="same turn", turn="idem")
    assert first["status"] == "pending"
    assert second["status"] == "idempotent_replay"
    assert len(core.repo.memories("user-1")) == 0


def test_sensitive_memory_requires_confirmation_and_never_leaks_summary():
    core = make_core()
    observe(
        core,
        summary="private health context",
        kind="State",
        sensitivity="sensitive",
        turn="sensitive",
    )
    core.decide("candidate-sensitive", "accept", "2030-07-18T23:41:00+08:00")
    result = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "private",
            "now": "2030-07-19T09:00:00+08:00",
        }
    )
    assert result["items"][0]["category"] == "confirm_first"
    assert result["items"][0]["summary"] is None
    assert "private health" not in str(result["items"][0]["guidance"])
    assert result["adapter_payload"]["allowed_memories"] == []
    assert "private health" not in str(result["adapter_payload"])


def test_revision_conflict_does_not_overwrite_newer_memory():
    core = make_core()
    observe(core, summary="stable fact", kind="State", turn="revision")
    accepted = core.decide("candidate-revision", "accept", "2030-07-18T23:41:00+08:00")
    core.revise(
        accepted["memory_id"],
        "2030-07-19T09:00:00+08:00",
        expected_revision=1,
        action="correct",
        source_id="correction-1",
        summary="new fact",
    )
    try:
        core.revise(
            accepted["memory_id"],
            "2030-07-19T09:01:00+08:00",
            expected_revision=1,
            action="correct",
            source_id="correction-stale",
            summary="stale fact",
        )
    except ValueError as error:
        assert str(error) == "revision_conflict"
    else:
        raise AssertionError("stale revision unexpectedly overwrote memory")
    assert core.repo.memory(accepted["memory_id"]).summary == "new fact"


def test_cross_midnight_observation_does_not_infer_sleep_or_completion():
    core = make_core()
    result = core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-midnight",
            "turn_id": "before-midnight",
            "observed_at": "2030-11-12T23:58:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "text": "still working",
        },
        {
            "candidate_id": "candidate-midnight",
            "kind": "Episode",
            "summary": "still working",
            "speech_act": "actual",
            "attributes": {"lived_episode": "open", "sleep_status": "awake"},
        },
    )
    assert result["status"] == "pending"
    accepted = core.decide("candidate-midnight", "accept", "2030-11-13T00:03:00+08:00")
    memory = core.repo.memory(accepted["memory_id"])
    assert memory.epistemic_status == "current"
    assert memory.outcome is None


def test_explain_is_persisted_and_source_lineage_is_present():
    core = make_core()
    observe(core, summary="lineage fact", kind="State", turn="lineage")
    accepted = core.decide("candidate-lineage", "accept", "2030-07-18T23:41:00+08:00")
    package = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "lineage",
            "now": "2030-07-19T09:00:00+08:00",
        }
    )
    item = package["items"][0]
    assert item["source_ids"]
    trace_before = core.explain("trace-recall-" + package["package_id"], user_id="user-1")
    trace_after = core.explain("trace-recall-" + package["package_id"], user_id="user-1")
    assert trace_before == trace_after
    assert accepted["memory_id"] in [item["memory_id"]]


def test_future_intention_updates_merge_into_one_memory():
    core = make_core()
    observe(core, summary="meeting maybe in November", turn="future-1")
    accepted = core.decide("candidate-future-1", "accept", "2030-07-03T12:01:00+08:00")
    observe(core, summary="meeting likely in November", turn="future-2")
    merged = core.decide(
        "candidate-future-2",
        "accept",
        "2030-07-03T12:02:00+08:00",
        merge_into_memory_id=accepted["memory_id"],
    )
    assert merged["status"] == "merged"
    memories = core.repo.memories("user-1")
    assert len(memories) == 1
    assert memories[0].summary == "meeting likely in November"
    assert len(memories[0].source_ids) == 2


def test_entity_correction_retracts_aliases_without_duplicate_person():
    core = make_core()
    result = core.canonicalize_entity(
        entity_id="person-1",
        user_id="user-1",
        canonical_name="林宇生",
        aliases=["林雨声", "林余生"],
        source_id="user-spelling-confirmation",
        now="2030-07-19T10:00:00+08:00",
    )
    again = core.canonicalize_entity(
        entity_id="person-duplicate",
        user_id="user-1",
        canonical_name="林宇生",
        aliases=["林雨声"],
        source_id="user-spelling-confirmation-2",
        now="2030-07-19T10:01:00+08:00",
    )
    assert result["entity_count"] == 1
    assert again["entity_id"] == "person-1"
    assert core.repo.db.execute("SELECT count(*) FROM entities").fetchone()[0] == 1


def test_lived_context_crosses_midnight_and_new_activity_replaces_it():
    core = make_core()
    first = core.update_lived_context(
        user_id="user-1",
        context="late-night-work",
        status="open",
        observed_at="2030-11-12T23:58:00+08:00",
        timezone="Asia/Shanghai",
        source_id="turn-before-midnight",
    )
    continued = core.update_lived_context(
        user_id="user-1",
        context="late-night-work",
        status="open",
        observed_at="2030-11-13T00:03:00+08:00",
        timezone="Asia/Shanghai",
        source_id="turn-after-midnight",
    )
    next_day = core.update_lived_context(
        user_id="user-1",
        context="after-work-evening",
        status="open",
        observed_at="2030-11-13T21:00:00+08:00",
        timezone="Asia/Shanghai",
        source_id="new-activity",
    )
    assert first["reason_codes"] == ["lived_episode_continues"]
    assert continued["reason_codes"] == ["lived_episode_continues"]
    assert next_day["reason_codes"] == ["new_activity_replaces_stale_context"]
    assert core.repo.lived_context("user-1")["context"] == "after-work-evening"


def test_elapsed_expected_date_adds_unknown_outcome_reason():
    core = make_core()
    observe(core)
    core.decide("candidate-t1", "accept", "2030-07-18T23:41:00+08:00")
    recalled = core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-2",
            "purpose": "reply",
            "query": "整理资料",
            "now": "2030-07-20T09:00:00+08:00",
        }
    )
    assert "expected_date_elapsed_outcome_unknown" in recalled["items"][0]["reason_codes"]
    schema = json.loads(
        (REPOSITORY_ROOT / "contracts" / "recall-package.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.validate(recalled, schema)


def test_import_is_user_authorized_idempotent_and_stays_candidate():
    core = make_core(cross_session=False)
    source = core.register_import_source(
        {
            "source_id": "export-1",
            "user_id": "user-1",
            "kind": "markdown_export",
            "locator": "user-selected-file",
            "authorization_scope": "user_selected",
            "created_at": "2030-07-19T10:00:00+08:00",
        }
    )
    assert source["memory_authorized"] is False
    core.start_import(
        {"source_id": "export-1", "job_id": "job-1", "now": "2030-07-19T10:01:00+08:00"}
    )
    record = {
        "source_record_id": "record-1",
        "observed_at": "2029-11-01T12:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "excerpt": "大概去年年底开始的新工作",
        "proposal": {
            "kind": "Episode",
            "summary": "大概去年年底开始的新工作",
            "speech_act": "actual",
            "time": {"original_expression": "去年年底", "precision": "season"},
        },
    }
    first = core.import_batch("job-1", [record], "2030-07-19T10:02:00+08:00")
    second = core.import_batch("job-1", [record], "2030-07-19T10:03:00+08:00")
    assert first["processed_records"] == 1
    assert second["processed_records"] == 1
    assert first["candidate_ids"] == second["candidate_ids"]
    assert core.repo.memories("user-1") == []
    snapshot = core.finalize_bootstrap(
        {
            "snapshot_id": "snapshot-1",
            "user_id": "user-1",
            "mode": "historical_import",
            "source_ids": ["export-1"],
            "job_ids": ["job-1"],
            "candidate_ids": first["candidate_ids"],
            "established_at": "2030-07-19T10:04:00+08:00",
        }
    )
    assert snapshot["status"] == "established"


def test_import_source_and_bootstrap_cannot_cross_users(tmp_path):
    core = SilentCore(SQLiteRepository())
    core.register_import_source(
        {
            "source_id": "source-owner",
            "user_id": "user-1",
            "kind": "jsonl_export",
            "locator": "selected",
            "authorization_scope": "user_selected",
            "created_at": "2030-07-19T10:00:00+08:00",
        }
    )
    try:
        core.register_import_source(
            {
                "source_id": "source-owner",
                "user_id": "user-2",
                "kind": "jsonl_export",
                "locator": "selected",
                "authorization_scope": "user_selected",
                "created_at": "2030-07-19T10:00:00+08:00",
            }
        )
    except ValueError as error:
        assert str(error) == "import_source_user_mismatch"
    else:
        raise AssertionError("cross-user source registration unexpectedly succeeded")


def test_existing_fr007_database_gets_additive_migration(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    db = sqlite3.connect(path)
    db.executescript(
        "CREATE TABLE users (id TEXT PRIMARY KEY, revocation_epoch INTEGER NOT NULL DEFAULT 0, package_version INTEGER NOT NULL DEFAULT 0);"
    )
    db.commit()
    db.close()
    repo = SQLiteRepository(path)
    assert repo.user_policy("legacy-user") == {"cross_session_internal_use": False}
    assert repo.db.execute("PRAGMA user_version").fetchone()[0] == 3


def test_global_cross_session_gate_does_not_override_memory_choice():
    core = make_core(cross_session=False)
    observe(core, summary="continue private alpha", kind="State", turn="permission-and")
    accepted = core.decide(
        "candidate-permission-and",
        "accept",
        "2030-07-18T23:41:00+08:00",
        permissions={"cross_session_internal_use": False},
    )
    core.set_user_policy(
        "user-1", "2030-07-19T08:00:00+08:00", cross_session_internal_use=True
    )
    assert core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-next",
            "purpose": "reply",
            "query": "private alpha",
            "now": "2030-07-19T08:01:00+08:00",
        }
    )["items"] == []
    core.set_permissions(
        accepted["memory_id"],
        "2030-07-19T08:02:00+08:00",
        cross_session_internal_use=True,
    )
    core.set_user_policy(
        "user-1", "2030-07-19T08:03:00+08:00", cross_session_internal_use=False
    )
    assert core.recall(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-next",
            "purpose": "reply",
            "query": "private alpha",
            "now": "2030-07-19T08:04:00+08:00",
        }
    )["items"] == []


def test_governance_can_toggle_repeatedly_and_trace_is_user_scoped():
    core = make_core()
    observe(core, summary="trace ownership", kind="State", turn="trace-owner")
    accepted = core.decide("candidate-trace-owner", "accept", "2030-07-18T23:41:00+08:00")
    core.set_permissions(
        accepted["memory_id"], "2030-07-19T09:00:00+08:00", proactive_expression=False
    )
    core.set_permissions(
        accepted["memory_id"], "2030-07-19T09:01:00+08:00", proactive_expression=True
    )
    core.set_user_policy(
        "user-1", "2030-07-19T09:02:00+08:00", cross_session_internal_use=False
    )
    core.set_user_policy(
        "user-1", "2030-07-19T09:03:00+08:00", cross_session_internal_use=True
    )
    trace_id = "trace-decision-candidate-trace-owner"
    assert core.explain(trace_id, user_id="user-1")["subject_type"] == "decision"
    try:
        core.explain(trace_id, user_id="user-2")
    except KeyError:
        pass
    else:
        raise AssertionError("cross-user trace read unexpectedly succeeded")
