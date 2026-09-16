from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from htc_core import SilentCore, SQLiteRepository


def observe(
    core: SilentCore,
    *,
    candidate_id: str = "candidate-1",
    kind: str = "Fact",
    summary: str = "我喜欢在安静的地方工作",
    time: dict | None = None,
    attributes: dict | None = None,
) -> str:
    result = core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "source-conversation",
            "turn_id": candidate_id,
            "observed_at": "2030-07-18T23:40:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "text": summary,
        },
        {
            "candidate_id": candidate_id,
            "kind": kind,
            "summary": summary,
            "speech_act": "actual",
            "sensitivity": "normal",
            "time": time or {},
            "attributes": attributes or {},
        },
    )
    return result["candidate_ids"][0]


def recall(
    core: SilentCore,
    query: str,
    *,
    now: str = "2030-07-19T09:00:00+08:00",
    conversation_id: str = "recall-conversation",
    turn_index: int | None = None,
):
    request = {
        "user_id": "user-1",
        "conversation_id": conversation_id,
        "purpose": "reply",
        "query": query,
        "now": now,
    }
    if turn_index is not None:
        request["turn_index"] = turn_index
    return core.recall(request)


def test_default_policy_remembers_without_proactive_surface() -> None:
    core = SilentCore(SQLiteRepository())
    accepted = core.decide(observe(core), "accept", "2030-07-18T23:41:00+08:00")
    memory = core.repo.memory(accepted["memory_id"])

    assert core.repo.user_policy("user-1")["cross_session_internal_use"] is True
    assert memory.cross_session_consent is True
    assert memory.proactive_consent is False
    assert memory.recall_allowed is True
    assert memory.surface_mode == "on_user_topic"
    assert recall(core, "安静工作")["items"][0]["category"] == "allowed_to_use"


def test_negative_state_is_available_when_user_asks_about_topic() -> None:
    core = SilentCore(SQLiteRepository())
    core.decide(
        observe(
            core,
            kind="State",
            summary="那次评审没有通过，我很沮丧",
            attributes={"affect": "negative"},
        ),
        "accept",
        "2030-07-18T23:41:00+08:00",
    )

    result = recall(core, "评审的事情呢")

    assert result["items"][0]["category"] == "allowed_to_use"
    assert result["items"][0]["summary"] == "那次评审没有通过，我很沮丧"
    assert "user_topic_matches_surface_policy" in result["items"][0]["reason_codes"]


def test_empty_query_never_recalls_everything() -> None:
    core = SilentCore(SQLiteRepository())
    core.decide(observe(core), "accept", "2030-07-18T23:41:00+08:00")

    result = recall(core, "   ")

    assert result["items"] == []
    assert result["reason_codes"] == ["empty_query"]


def test_policy_disabled_and_no_match_have_distinct_reasons() -> None:
    core = SilentCore(SQLiteRepository())
    core.decide(observe(core), "accept", "2030-07-18T23:41:00+08:00")

    assert recall(core, "完全不相关")["reason_codes"] == ["no_matching_memory"]
    core.set_user_policy(
        "user-1", "2030-07-19T09:01:00+08:00", cross_session_internal_use=False
    )
    assert recall(core, "安静")["reason_codes"] == ["cross_session_policy_disabled"]


def test_intention_state_machine_validates_outcome_revision_and_terminal_state() -> None:
    core = SilentCore(SQLiteRepository())
    accepted = core.decide(
        observe(
            core,
            kind="Intention",
            summary="明天整理资料",
            time={"expected_at": "2030-07-19", "precision": "day"},
        ),
        "accept",
        "2030-07-18T23:41:00+08:00",
    )
    memory_id = accepted["memory_id"]

    active = core.update_intention(
        memory_id,
        "2030-07-19T08:00:00+08:00",
        expected_revision=1,
        intention_state="active",
    )
    assert active["intention_state"] == "active"
    assert active["outcome"] == "unknown"

    with pytest.raises(ValueError, match="invalid_intention_outcome"):
        core.update_intention(
            memory_id,
            "2030-07-19T08:01:00+08:00",
            expected_revision=2,
            intention_state="completed",
            outcome="cancelled",
        )
    with pytest.raises(ValueError, match="revision_conflict"):
        core.update_intention(
            memory_id,
            "2030-07-19T08:02:00+08:00",
            expected_revision=1,
            intention_state="paused",
        )

    completed = core.update_intention(
        memory_id,
        "2030-07-19T08:03:00+08:00",
        expected_revision=2,
        intention_state="completed",
    )
    assert completed["outcome"] == "completed"
    assert completed["closed_at"] == "2030-07-19T08:03:00+08:00"
    with pytest.raises(ValueError, match="intention_state_terminal"):
        core.update_intention(
            memory_id,
            "2030-07-19T08:04:00+08:00",
            expected_revision=3,
            intention_state="active",
        )


@pytest.mark.parametrize("closed_state", ["completed", "cancelled"])
def test_overdue_open_loop_stops_after_intention_is_closed(closed_state: str) -> None:
    core = SilentCore(SQLiteRepository())
    accepted = core.decide(
        observe(
            core,
            kind="Intention",
            summary="整理资料",
            time={"expected_at": "2030-07-19", "precision": "day"},
        ),
        "accept",
        "2030-07-18T23:41:00+08:00",
    )
    memory_id = accepted["memory_id"]

    overdue = recall(core, "整理资料", now="2030-07-20T09:00:00+08:00")
    assert "intention_overdue_open_loop" in overdue["items"][0]["reason_codes"]

    core.update_intention(
        memory_id,
        "2030-07-20T09:01:00+08:00",
        expected_revision=1,
        intention_state=closed_state,
    )
    closed = recall(core, "整理资料", now="2030-07-20T09:02:00+08:00")
    assert "intention_overdue_open_loop" not in closed["items"][0]["reason_codes"]


def test_current_state_is_editable_and_ages_without_becoming_memory() -> None:
    core = SilentCore(SQLiteRepository())
    created = core.set_current_state(
        "user-1",
        label="专注收尾",
        tone="strained",
        since="2030-07-01T09:00:00+08:00",
        source_memory_ids=(),
        now="2030-07-01T09:00:00+08:00",
    )
    assert created["revision"] == 1
    assert core.repo.memories("user-1") == []
    assert core.current_state("user-1", now="2030-07-20T09:00:00+08:00")["status"] == "aged"

    edited = core.set_current_state(
        "user-1",
        label="重新有了节奏",
        tone="steady",
        since="2030-07-20T08:00:00+08:00",
        source_memory_ids=(),
        now="2030-07-20T09:00:00+08:00",
        expected_revision=1,
    )
    assert edited["revision"] == 2
    assert edited["status"] == "current"
    assert edited["label"] == "重新有了节奏"


def test_current_state_rejects_invalid_since_and_tolerates_legacy_bad_data() -> None:
    core = SilentCore(SQLiteRepository())

    with pytest.raises(ValueError, match="invalid_current_state_since"):
        core.set_current_state(
            "user-1",
            label="无法解析的状态",
            tone="uncertain",
            since="not-a-date",
            now="2030-07-20T09:00:00+08:00",
        )

    core.repo.ensure_user("user-1")
    core.repo.db.execute(
        """INSERT INTO states(
               user_id,label,tone,since,status,source_memory_ids_json,revision,updated_at
           ) VALUES (?,?,?,?,?,?,?,?)""",
        (
            "user-1",
            "历史坏数据",
            "uncertain",
            "not-a-date",
            "current",
            "[]",
            1,
            "2030-07-20T09:00:00+08:00",
        ),
    )
    state = core.current_state("user-1", now="2030-07-20T09:01:00+08:00")

    assert state["status"] == "invalid"
    assert state["age_days"] is None
    assert state["reason_codes"] == ["invalid_state_since"]


def test_surface_policy_max_per_conversation_is_enforced() -> None:
    core = SilentCore(SQLiteRepository())
    memory_id = core.decide(
        observe(core, summary="我喜欢安静工作"),
        "accept",
        "2030-07-18T23:41:00+08:00",
    )["memory_id"]
    core.set_permissions(
        memory_id,
        "2030-07-18T23:42:00+08:00",
        max_per_conversation=0,
    )

    blocked = recall(core, "安静工作", turn_index=1)

    assert blocked["items"] == []
    assert blocked["reason_codes"] == ["memory_max_per_conversation_reached"]
    assert core.repo.memory_recall_usage(memory_id, "recall-conversation")[
        "recall_count"
    ] == 0


def test_surface_policy_turn_gap_and_count_are_scoped_to_conversation() -> None:
    core = SilentCore(SQLiteRepository())
    memory_id = core.decide(
        observe(core, summary="我喜欢安静工作"),
        "accept",
        "2030-07-18T23:41:00+08:00",
    )["memory_id"]
    core.set_permissions(
        memory_id,
        "2030-07-18T23:42:00+08:00",
        max_per_conversation=2,
        min_gap_turns=3,
    )

    first = recall(core, "安静工作", turn_index=10)
    too_close = recall(core, "安静工作", turn_index=11)
    second = recall(core, "安静工作", turn_index=13)
    exhausted = recall(core, "安静工作", turn_index=20)
    other_conversation = recall(
        core,
        "安静工作",
        conversation_id="another-conversation",
        turn_index=1,
    )

    assert first["items"][0]["memory_id"] == memory_id
    assert too_close["items"] == []
    assert too_close["reason_codes"] == ["memory_min_gap_turns_not_elapsed"]
    assert second["items"][0]["memory_id"] == memory_id
    assert exhausted["items"] == []
    assert exhausted["reason_codes"] == ["memory_max_per_conversation_reached"]
    assert other_conversation["items"][0]["memory_id"] == memory_id
    assert core.repo.memory_recall_usage(memory_id, "recall-conversation")[
        "recall_count"
    ] == 2
    assert core.repo.memory_recall_usage(memory_id, "another-conversation")[
        "recall_count"
    ] == 1


def test_additive_migration_adds_lifecycle_and_surface_columns(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE users (id TEXT PRIMARY KEY, revocation_epoch INTEGER NOT NULL DEFAULT 0,
          package_version INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE memories (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL,
          summary TEXT NOT NULL, epistemic_status TEXT NOT NULL, speech_act TEXT NOT NULL,
          time_json TEXT NOT NULL, sensitivity TEXT NOT NULL, intention_state TEXT, outcome TEXT,
          persist_consent INTEGER NOT NULL, cross_session_consent INTEGER NOT NULL,
          proactive_consent INTEGER NOT NULL, revision INTEGER NOT NULL,
          revocation_epoch INTEGER NOT NULL, current INTEGER NOT NULL DEFAULT 1);
        """
    )
    connection.execute("INSERT INTO users(id) VALUES ('legacy-user')")
    connection.commit()
    connection.close()

    repository = SQLiteRepository(database)

    memory_columns = {
        row[1] for row in repository.db.execute("PRAGMA table_info(memories)").fetchall()
    }
    assert {
        "closed_at",
        "recall_allowed",
        "surface_mode",
        "max_per_conversation",
        "min_gap_turns",
    }.issubset(memory_columns)
    assert repository.db.execute(
        "SELECT cross_session_consent FROM users WHERE id='legacy-user'"
    ).fetchone()[0] == 1
    assert repository.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='states'"
    ).fetchone()
    assert repository.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_recall_usage'"
    ).fetchone()


def test_additive_migration_upgrades_complete_pre_lifecycle_database(tmp_path: Path) -> None:
    database = tmp_path / "complete-legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        PRAGMA user_version=3;
        CREATE TABLE users (id TEXT PRIMARY KEY, revocation_epoch INTEGER NOT NULL DEFAULT 0,
          package_version INTEGER NOT NULL DEFAULT 0, cross_session_consent INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE conversations (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id));
        CREATE TABLE observations (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          conversation_id TEXT NOT NULL REFERENCES conversations(id), turn_id TEXT NOT NULL,
          observed_at TEXT NOT NULL, timezone TEXT NOT NULL, role TEXT NOT NULL,
          content_hash TEXT NOT NULL, excerpt TEXT NOT NULL, speech_act TEXT NOT NULL,
          UNIQUE(conversation_id, turn_id));
        CREATE TABLE candidates (id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observations(id),
          user_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL, summary TEXT NOT NULL,
          speech_act TEXT NOT NULL, status TEXT NOT NULL, confidence REAL NOT NULL,
          time_json TEXT NOT NULL, sensitivity TEXT NOT NULL, permissions_json TEXT NOT NULL,
          attributes_json TEXT NOT NULL);
        CREATE TABLE memories (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          kind TEXT NOT NULL, summary TEXT NOT NULL, epistemic_status TEXT NOT NULL,
          speech_act TEXT NOT NULL, time_json TEXT NOT NULL, sensitivity TEXT NOT NULL,
          intention_state TEXT, outcome TEXT, persist_consent INTEGER NOT NULL,
          cross_session_consent INTEGER NOT NULL, proactive_consent INTEGER NOT NULL,
          revision INTEGER NOT NULL, revocation_epoch INTEGER NOT NULL,
          current INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE memory_sources (memory_id TEXT NOT NULL REFERENCES memories(id),
          source_id TEXT NOT NULL, PRIMARY KEY(memory_id, source_id));
        CREATE TABLE memory_events (id INTEGER PRIMARY KEY AUTOINCREMENT,
          memory_id TEXT NOT NULL REFERENCES memories(id), event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE decision_traces (id TEXT PRIMARY KEY, subject_type TEXT NOT NULL,
          subject_id TEXT NOT NULL, reason_codes_json TEXT NOT NULL, input_summary TEXT NOT NULL,
          created_at TEXT NOT NULL, user_id TEXT REFERENCES users(id));
        CREATE TABLE recall_packages (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          conversation_id TEXT NOT NULL, purpose TEXT NOT NULL, issued_at TEXT NOT NULL,
          expires_at TEXT NOT NULL, package_version INTEGER NOT NULL, revocation_epoch INTEGER NOT NULL);
        CREATE TABLE recall_items (package_id TEXT NOT NULL REFERENCES recall_packages(id),
          memory_id TEXT NOT NULL REFERENCES memories(id), category TEXT NOT NULL, summary TEXT,
          guidance TEXT, source_ids_json TEXT NOT NULL, reason_codes_json TEXT NOT NULL,
          PRIMARY KEY(package_id, memory_id));
        CREATE TABLE entities (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          canonical_name TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, UNIQUE(user_id, canonical_name));
        CREATE TABLE entity_aliases (entity_id TEXT NOT NULL REFERENCES entities(id), alias TEXT NOT NULL,
          status TEXT NOT NULL, source_id TEXT NOT NULL, PRIMARY KEY(entity_id, alias));
        CREATE TABLE lived_contexts (user_id TEXT PRIMARY KEY REFERENCES users(id), context TEXT NOT NULL,
          status TEXT NOT NULL, observed_at TEXT NOT NULL, timezone TEXT NOT NULL,
          source_id TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE import_sources (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          kind TEXT NOT NULL, locator TEXT NOT NULL, authorization_scope TEXT NOT NULL,
          content_hash TEXT, created_at TEXT NOT NULL);
        CREATE TABLE import_jobs (id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES import_sources(id),
          user_id TEXT NOT NULL REFERENCES users(id), status TEXT NOT NULL,
          total_records INTEGER NOT NULL DEFAULT 0, processed_records INTEGER NOT NULL DEFAULT 0,
          candidate_ids_json TEXT NOT NULL DEFAULT '[]', started_at TEXT, finished_at TEXT, error TEXT);
        CREATE TABLE import_records (job_id TEXT NOT NULL REFERENCES import_jobs(id),
          source_record_id TEXT NOT NULL, observation_id TEXT, candidate_id TEXT,
          status TEXT NOT NULL, PRIMARY KEY(job_id, source_record_id));
        CREATE TABLE bootstrap_snapshots (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          mode TEXT NOT NULL, source_ids_json TEXT NOT NULL, job_ids_json TEXT NOT NULL,
          candidate_ids_json TEXT NOT NULL, established_at TEXT NOT NULL);
        CREATE TABLE adapter_events (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
          conversation_id TEXT NOT NULL, turn_id TEXT NOT NULL, event_type TEXT NOT NULL,
          occurred_at TEXT NOT NULL, payload_json TEXT NOT NULL);
        """
    )
    connection.execute("INSERT INTO users(id,cross_session_consent) VALUES ('legacy-user',0)")
    connection.execute("INSERT INTO conversations VALUES ('legacy-conversation','legacy-user')")
    connection.execute(
        "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            "legacy-observation",
            "legacy-user",
            "legacy-conversation",
            "legacy-turn",
            "2026-09-01T09:00:00+08:00",
            "Asia/Shanghai",
            "user",
            "hash",
            "legacy memory",
            "actual",
        ),
    )
    connection.execute(
        "INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "legacy-memory",
            "legacy-user",
            "Fact",
            "legacy memory",
            "current",
            "actual",
            "{}",
            "normal",
            None,
            None,
            1,
            1,
            0,
            1,
            0,
            1,
        ),
    )
    connection.execute("INSERT INTO memory_sources VALUES ('legacy-memory','legacy-observation')")
    connection.commit()
    connection.close()

    repository = SQLiteRepository(database)
    migrated = repository.memory("legacy-memory")

    assert migrated.summary == "legacy memory"
    assert migrated.recall_allowed is True
    assert migrated.surface_mode == "on_user_topic"
    assert repository.user_policy("legacy-user") == {"cross_session_internal_use": False}
    assert repository.db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert repository.db.execute("PRAGMA user_version").fetchone()[0] == 6
    repository.db.close()

    reopened = SQLiteRepository(database)
    assert reopened.memory("legacy-memory").summary == "legacy memory"
    assert reopened.user_policy("legacy-user") == {"cross_session_internal_use": False}
    assert reopened.db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_candidate_permissions_require_explicit_confirmation() -> None:
    core = SilentCore(SQLiteRepository())
    result = core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "permission-source",
            "turn_id": "permission-turn",
            "observed_at": "2030-07-18T23:40:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "text": "记住但不要跨会话使用",
        },
        {
            "candidate_id": "permission-candidate",
            "kind": "Fact",
            "summary": "记住但不要跨会话使用",
            "permissions": {"cross_session_internal_use": False},
        },
    )

    with pytest.raises(ValueError, match="candidate_permissions_require_confirmation"):
        core.decide(result["candidate_ids"][0], "accept", "2030-07-18T23:41:00+08:00")
    with pytest.raises(ValueError, match="unconfirmed_permission_expansion"):
        core.decide(
            result["candidate_ids"][0],
            "accept",
            "2030-07-18T23:42:00+08:00",
            permissions={"cross_session_internal_use": True},
        )

    accepted = core.decide(
        result["candidate_ids"][0],
        "accept",
        "2030-07-18T23:43:00+08:00",
        permissions={"cross_session_internal_use": False},
    )
    assert core.repo.memory(accepted["memory_id"]).cross_session_consent is False


def test_candidate_permissions_are_confirmed_and_applied_when_merging() -> None:
    core = SilentCore(SQLiteRepository())
    existing_id = core.decide(
        observe(core, candidate_id="existing", summary="现有事实"),
        "accept",
        "2030-07-18T23:41:00+08:00",
    )["memory_id"]
    result = core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "merge-permission-source",
            "turn_id": "merge-permission-turn",
            "observed_at": "2030-07-18T23:42:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "text": "补充事实但不要跨会话使用",
        },
        {
            "candidate_id": "merge-permission-candidate",
            "kind": "Fact",
            "summary": "补充事实但不要跨会话使用",
            "permissions": {"cross_session_internal_use": False},
        },
    )

    with pytest.raises(ValueError, match="candidate_permissions_require_confirmation"):
        core.decide(
            result["candidate_ids"][0],
            "accept",
            "2030-07-18T23:43:00+08:00",
            merge_into_memory_id=existing_id,
            merge_expected_revision=1,
        )

    merged = core.decide(
        result["candidate_ids"][0],
        "accept",
        "2030-07-18T23:44:00+08:00",
        permissions={"cross_session_internal_use": False},
        merge_into_memory_id=existing_id,
        merge_expected_revision=1,
    )
    assert merged["status"] == "merged"
    assert core.repo.memory(existing_id).cross_session_consent is False
