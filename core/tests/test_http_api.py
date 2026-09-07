from __future__ import annotations

import json
import queue
import threading
import urllib.error
import urllib.request
from pathlib import Path

from htc_core.core import SilentCore
from htc_core.http_api import create_server
from htc_core.repository import SQLiteRepository
from htc_core.runtime import RuntimeSettings


def _settings(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(tmp_path / "htc.sqlite3", "user-1", "Asia/Shanghai")


def _request(base: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base + path,
        data=data,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def test_http_api_reads_real_core_and_governs_memory(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    core = SilentCore(SQLiteRepository(settings.database_path))
    core.set_user_policy("user-1", "2030-01-01T00:00:00+08:00", cross_session_internal_use=True)
    core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-1",
            "turn_id": "turn-1",
            "observed_at": "2030-07-18T23:40:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "excerpt": "明天继续整理资料",
        },
        {"candidate_id": "candidate-1", "kind": "Intention", "summary": "明天继续整理资料", "time": {"relative": "tomorrow"}},
    )
    # Open the API using the same database, as the real Workbench process does.
    ready: queue.Queue = queue.Queue()

    def serve() -> None:
        server = create_server(settings, host="127.0.0.1", port=0)
        ready.put(server)
        server.serve_forever()
        server.server_close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    server = ready.get(timeout=2)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _request(base, "/api/status")
        assert status == 200
        assert payload["data"]["pending_candidates"] == 1

        status, payload = _request(base, "/api/candidates?status=pending")
        assert status == 200
        candidate = payload["data"]["candidates"][0]
        assert candidate["id"] == "candidate-1"
        assert candidate["summary"] == "明天继续整理资料"

        status, payload = _request(base, "/api/candidates/candidate-1/decide", {"decision": "accept", "now": "2030-07-18T23:41:00+08:00"})
        assert status == 200
        memory_id = payload["data"]["memory_id"]

        status, payload = _request(base, "/api/memories")
        assert status == 200
        assert payload["data"]["memories"][0]["id"] == memory_id

        status, payload = _request(base, f"/api/memories/{memory_id}/explain")
        assert status == 200
        assert payload["data"]["memory_id"] == memory_id
        assert payload["data"]["source_ids"] == [candidate["observation_id"]]
        assert payload["data"]["events"][0]["event_type"] == "accepted"

        status, payload = _request(base, f"/api/memories/{memory_id}")
        assert status == 200
        assert payload["data"]["sources"][0]["conversation_id"] == "conversation-1"
        assert payload["data"]["sources"][0]["excerpt"] == "明天继续整理资料"

        status, payload = _request(
            base,
            "/api/recall-preview",
            {"query": "继续整理", "conversation_id": "preview-1", "now": "2030-07-18T23:42:00+08:00"},
        )
        assert status == 200
        assert payload["data"]["items"][0]["category"] == "allowed_to_use"
        assert payload["data"]["items"][0]["display_summary"] == "明天继续整理资料"
        assert payload["data"]["adapter_payload"]["allowed_memories"][0]["summary"] == "明天继续整理资料"

        status, payload = _request(base, f"/api/memories/{memory_id}/suppress", {})
        assert status == 200
        assert payload["data"]["proactive_expression"] is False
        assert core.repo.memory(memory_id).proactive_consent is False

        status, payload = _request(base, f"/api/memories/{memory_id}/explain")
        assert status == 200
        assert payload["data"]["governance_traces"][-1]["reason_codes"] == [
            "proactive_expression_revoked"
        ]

        status, payload = _request(
            base,
            "/api/recall-preview",
            {"query": "继续整理", "conversation_id": "preview-2", "now": "2030-07-18T23:43:00+08:00"},
        )
        assert status == 200
        assert payload["data"]["items"][0]["category"] == "internal_only"
        assert payload["data"]["items"][0]["summary"] is None
        assert payload["data"]["items"][0]["display_summary"] == "明天继续整理资料"
        assert payload["data"]["adapter_payload"]["allowed_memories"] == []

        status, payload = _request(
            base,
            f"/api/memories/{memory_id}/permissions",
            {"expected_revision": 1, "proactive_expression": True},
        )
        assert status == 409
        assert payload["error"]["code"] == "revision_conflict"

        status, payload = _request(base, "/api/policy", {"cross_session_internal_use": False})
        assert status == 200
        assert payload["data"]["cross_session_internal_use"] is False
        status, payload = _request(base, "/api/status")
        assert payload["data"]["cross_session_internal_use"] is False

        status, payload = _request(base, "/api/policy", {"cross_session_internal_use": "false"})
        assert status == 400
        assert payload["error"]["code"] == "invalid_cross_session_internal_use"

        package_count = core.repo.db.execute("SELECT COUNT(*) FROM recall_packages").fetchone()[0]
        trace_count = core.repo.db.execute("SELECT COUNT(*) FROM decision_traces").fetchone()[0]
        invalid_requests = (
            ({"query": ""}, "invalid_query"),
            ({"query": "继续", "purpose": []}, "invalid_purpose"),
            ({"query": "继续", "conversation_id": 42}, "invalid_conversation_id"),
            ({"query": "继续", "ttl_minutes": 0}, "invalid_ttl_minutes"),
        )
        for request_body, error_code in invalid_requests:
            status, payload = _request(base, "/api/recall-preview", request_body)
            assert status == 400
            assert payload["error"]["code"] == error_code
            assert core.repo.db.execute("SELECT COUNT(*) FROM recall_packages").fetchone()[0] == package_count
            assert core.repo.db.execute("SELECT COUNT(*) FROM decision_traces").fetchone()[0] == trace_count
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_http_api_rejects_invalid_decision_and_orders_memories_by_time(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    core = SilentCore(SQLiteRepository(settings.database_path))
    for index, occurred_at in enumerate(("2030-01-02T00:00:00+08:00", "2030-01-01T00:00:00+08:00"), 1):
        candidate_id = f"candidate-{index}"
        core.observe(
            {
                "user_id": "user-1",
                "conversation_id": f"conversation-{index}",
                "turn_id": f"turn-{index}",
                "observed_at": occurred_at,
                "timezone": "Asia/Shanghai",
                "role": "user",
                "excerpt": f"事实 {index}",
            },
            {
                "candidate_id": candidate_id,
                "kind": "Fact",
                "summary": f"事实 {index}",
                "time": {"occurred_at": occurred_at},
            },
        )
    ready: queue.Queue = queue.Queue()

    def serve() -> None:
        server = create_server(settings, host="127.0.0.1", port=0)
        ready.put(server)
        server.serve_forever()
        server.server_close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    server = ready.get(timeout=2)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _request(base, "/api/candidates/candidate-1/decide", {"decision": "typo"})
        assert status == 400
        assert payload["error"]["code"] == "invalid_decision"
        for candidate_id in ("candidate-1", "candidate-2"):
            status, _ = _request(base, f"/api/candidates/{candidate_id}/decide", {"decision": "accept"})
            assert status == 200
        status, payload = _request(base, "/api/memories")
        assert status == 200
        assert [item["summary"] for item in payload["data"]["memories"]] == ["事实 1", "事实 2"]
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_recall_preview_keeps_sensitive_memory_out_of_adapter_payload(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    core = SilentCore(SQLiteRepository(settings.database_path))
    core.set_user_policy("user-1", "2030-01-01T00:00:00+08:00", cross_session_internal_use=True)
    observed = core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "sensitive-source",
            "turn_id": "turn-1",
            "observed_at": "2030-01-01T00:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "excerpt": "家庭经历仍会影响安全感",
        },
        {
            "candidate_id": "sensitive-candidate",
            "kind": "Meaning",
            "summary": "家庭经历仍会影响安全感",
            "sensitivity": "sensitive",
        },
    )
    core.decide(observed["candidate_ids"][0], "accept", "2030-01-01T00:01:00+08:00")
    ready: queue.Queue = queue.Queue()

    def serve() -> None:
        server = create_server(settings, host="127.0.0.1", port=0)
        ready.put(server)
        server.serve_forever()
        server.server_close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    server = ready.get(timeout=2)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _request(
            base,
            "/api/recall-preview",
            {"query": "家庭安全感", "conversation_id": "preview-sensitive"},
        )
        assert status == 200
        data = payload["data"]
        assert data["items"][0]["category"] == "confirm_first"
        assert data["items"][0]["summary"] is None
        assert data["items"][0]["display_summary"] == "家庭经历仍会影响安全感"
        serialized_adapter = json.dumps(data["adapter_payload"], ensure_ascii=False)
        assert data["adapter_payload"]["allowed_memories"] == []
        assert data["adapter_payload"]["confirmation_prompts"] == [
            "Ask whether the user wants to discuss a relevant sensitive topic."
        ]
        assert "家庭经历仍会影响安全感" not in serialized_adapter
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_candidate_merge_preserves_lineage_and_rejects_invalid_targets(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    core = SilentCore(SQLiteRepository(settings.database_path))

    def observe(user_id: str, candidate_id: str, summary: str) -> None:
        core.observe(
            {
                "user_id": user_id,
                "conversation_id": f"conversation-{candidate_id}",
                "turn_id": f"turn-{candidate_id}",
                "observed_at": "2030-01-01T00:00:00+08:00",
                "timezone": "Asia/Shanghai",
                "role": "user",
                "excerpt": summary,
            },
            {"candidate_id": candidate_id, "kind": "Person", "summary": summary},
        )

    observe("user-1", "existing", "示例导师是以前的技术负责人")
    core.decide("existing", "accept", "2030-01-01T00:01:00+08:00")
    memory_id = core.repo.memories("user-1")[0].id
    observe("user-1", "update", "示例导师曾陪我一起走过中央换乘站")
    observe("user-1", "preserve", "这是新增的一条来源")
    observe("user-1", "conflict", "这是来自旧页面的合并")
    observe("user-2", "other", "另一个用户的记忆")
    core.decide("other", "accept", "2030-01-01T00:01:00+08:00")
    other_memory_id = core.repo.memories("user-2")[0].id
    observe("user-2", "other-pending", "另一个用户的候选")

    dead_targets: list[tuple[str, str, str]] = []
    for action in ("retract", "supersede"):
        target_candidate = f"{action}-target"
        update_candidate = f"{action}-update"
        observe("user-1", target_candidate, f"将被 {action} 的记忆")
        accepted = core.decide(target_candidate, "accept", "2030-01-01T00:01:00+08:00")
        dead_memory_id = accepted["memory_id"]
        core.revise(
            dead_memory_id,
            "2030-01-01T00:02:00+08:00",
            expected_revision=1,
            action=action,
            source_id=core.repo.memory(dead_memory_id).source_ids[0],
        )
        observe("user-1", update_candidate, f"不应复活 {action} 记忆")
        dead_targets.append((action, dead_memory_id, update_candidate))
    original_versions = tuple(
        core.repo.db.execute(
            "SELECT revocation_epoch,package_version FROM users WHERE id='user-1'"
        ).fetchone()
    )
    ready: queue.Queue = queue.Queue()

    def serve() -> None:
        server = create_server(settings, host="127.0.0.1", port=0)
        ready.put(server)
        server.serve_forever()
        server.server_close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    server = ready.get(timeout=2)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        original = core.repo.memory(memory_id)
        original_events = core.repo.db.execute(
            "SELECT COUNT(*) FROM memory_events WHERE memory_id=?", (memory_id,)
        ).fetchone()[0]
        invalid_merges = (
            ({"decision": "accept", "merge_into_memory_id": "", "expected_memory_revision": 1}, "invalid_merge_target"),
            ({"decision": "accept", "merge_into_memory_id": 42, "expected_memory_revision": 1}, "invalid_merge_target"),
            ({"decision": "accept", "merge_into_memory_id": memory_id}, "invalid_expected_memory_revision"),
            ({"decision": "accept", "merge_into_memory_id": memory_id, "expected_memory_revision": True}, "invalid_expected_memory_revision"),
            ({"decision": "accept", "merge_into_memory_id": memory_id, "expected_memory_revision": 1, "summary": " "}, "invalid_summary"),
            ({"decision": "accept", "merge_into_memory_id": memory_id, "expected_memory_revision": 1, "summary": 42}, "invalid_summary"),
            ({"decision": "accept", "merge_into_memory_id": "missing", "expected_memory_revision": 1}, "memory_not_found"),
        )
        for request_body, code in invalid_merges:
            status, payload = _request(base, "/api/candidates/update/decide", request_body)
            assert status in {400, 404}
            assert payload["error"]["code"] == code
            unchanged = core.repo.memory(memory_id)
            assert (unchanged.summary, unchanged.revision, unchanged.source_ids) == (
                original.summary,
                original.revision,
                original.source_ids,
            )
            assert core.repo.candidate("update").status == "pending"
            assert tuple(
                core.repo.db.execute(
                    "SELECT revocation_epoch,package_version FROM users WHERE id='user-1'"
                ).fetchone()
            ) == original_versions
            assert core.repo.db.execute(
                "SELECT COUNT(*) FROM memory_events WHERE memory_id=?", (memory_id,)
            ).fetchone()[0] == original_events

        status, payload = _request(
            base,
            "/api/candidates/other-pending/decide",
            {"decision": "accept", "merge_into_memory_id": memory_id, "expected_memory_revision": 1},
        )
        assert status == 404
        assert payload["error"]["code"] == "candidate_not_found"
        assert core.repo.candidate("other-pending").status == "pending"

        status, payload = _request(
            base,
            "/api/candidates/update/decide",
            {"decision": "accept", "merge_into_memory_id": other_memory_id, "expected_memory_revision": 1},
        )
        assert status == 404
        assert payload["error"]["code"] == "memory_not_found"
        assert core.repo.candidate("update").status == "pending"

        status, payload = _request(
            base,
            "/api/candidates/update/decide",
            {
                "decision": "accept",
                "merge_into_memory_id": memory_id,
                "expected_memory_revision": 1,
                "summary": "示例导师是以前的技术负责人，也曾陪我一起走过中央换乘站",
            },
        )
        assert status == 200
        assert payload["data"]["status"] == "merged"
        merged = core.repo.memory(memory_id)
        assert merged.revision == 2
        assert merged.summary == "示例导师是以前的技术负责人，也曾陪我一起走过中央换乘站"
        assert len(merged.source_ids) == 2
        assert core.repo.candidate("update").status == "accepted"

        status, payload = _request(
            base,
            "/api/candidates/preserve/decide",
            {
                "decision": "accept",
                "merge_into_memory_id": memory_id,
                "expected_memory_revision": 2,
            },
        )
        assert status == 200
        preserved = core.repo.memory(memory_id)
        assert preserved.revision == 3
        assert preserved.summary == merged.summary
        assert len(preserved.source_ids) == 3

        status, payload = _request(
            base,
            "/api/candidates/conflict/decide",
            {
                "decision": "accept",
                "merge_into_memory_id": memory_id,
                "expected_memory_revision": 2,
                "summary": "不应覆盖最新摘要",
            },
        )
        assert status == 409
        assert payload["error"]["code"] == "revision_conflict"
        assert core.repo.candidate("conflict").status == "pending"
        assert core.repo.memory(memory_id) == preserved

        for _action, dead_memory_id, update_candidate in dead_targets:
            before = core.repo.memory(dead_memory_id)
            event_count = core.repo.db.execute(
                "SELECT COUNT(*) FROM memory_events WHERE memory_id=?", (dead_memory_id,)
            ).fetchone()[0]
            status, payload = _request(
                base,
                f"/api/candidates/{update_candidate}/decide",
                {
                    "decision": "accept",
                    "merge_into_memory_id": dead_memory_id,
                    "expected_memory_revision": before.revision,
                },
            )
            assert status == 409
            assert payload["error"]["code"] == "memory_not_current"
            assert core.repo.memory(dead_memory_id) == before
            assert not core.repo.memory_is_current(dead_memory_id)
            assert core.repo.candidate(update_candidate).status == "pending"
            assert core.repo.db.execute(
                "SELECT COUNT(*) FROM memory_events WHERE memory_id=?", (dead_memory_id,)
            ).fetchone()[0] == event_count

        status, payload = _request(
            base,
            "/api/candidates/update/decide",
            {"decision": "accept", "merge_into_memory_id": memory_id, "expected_memory_revision": 3},
        )
        assert status == 409
        assert payload["error"]["code"] == "candidate_not_pending"
        assert core.repo.memory(memory_id).revision == 3
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_http_api_hides_other_users_and_reports_revision_conflict(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    core = SilentCore(SQLiteRepository(settings.database_path))
    core.set_user_policy("user-1", "2030-01-01T00:00:00+08:00", cross_session_internal_use=True)
    core.observe(
        {"user_id": "user-1", "conversation_id": "c", "turn_id": "t", "observed_at": "2030-01-01T00:00:00+08:00", "role": "user", "excerpt": "事实"},
        {"candidate_id": "candidate-1", "kind": "Fact", "summary": "事实"},
    )
    core.decide("candidate-1", "accept", "2030-01-01T00:01:00+08:00")
    memory_id = core.repo.memories("user-1")[0].id
    ready = queue.Queue()

    def serve() -> None:
        server = create_server(settings, host="127.0.0.1", port=0)
        ready.put(server)
        server.serve_forever()
        server.server_close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    server = ready.get(timeout=2)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, _ = _request(base, "/api/memories/not-a-memory")
        assert status == 404
        status, payload = _request(base, f"/api/memories/{memory_id}/revise", {"expected_revision": 0, "summary": "stale"})
        assert status == 409
        assert payload["error"]["code"] == "revision_conflict"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_conversation_audit_projects_sources_and_adapter_only_sessions(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    core = SilentCore(SQLiteRepository(settings.database_path))
    core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-a",
            "turn_id": "turn-a",
            "observed_at": "2030-01-01T10:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "excerpt": "示例导师曾陪我走过中央换乘站",
        },
        {"candidate_id": "conversation-candidate-a", "kind": "Person", "summary": "示例导师曾陪我走过中央换乘站"},
    )
    core.decide("conversation-candidate-a", "accept", "2030-01-01T10:01:00+08:00")
    core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-b",
            "turn_id": "turn-b",
            "observed_at": "2030-01-02T10:00:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "excerpt": "明天继续工作",
        },
        {"candidate_id": "conversation-candidate-b", "kind": "Intention", "summary": "明天继续工作"},
    )
    memory_id = core.repo.memories("user-1")[0].id
    core.decide(
        "conversation-candidate-b",
        "accept",
        "2030-01-02T10:01:00+08:00",
        merge_into_memory_id=memory_id,
        merge_expected_revision=1,
        summary="示例导师曾陪我走过中央换乘站；另一个会话补充了后续安排",
    )
    core.observe(
        {
            "user_id": "user-1",
            "conversation_id": "conversation-b",
            "turn_id": "turn-b-pending",
            "observed_at": "2030-01-02T10:05:00+08:00",
            "timezone": "Asia/Shanghai",
            "role": "user",
            "excerpt": "还有一件未确认的事",
        },
        {"candidate_id": "conversation-candidate-pending", "kind": "Fact", "summary": "还有一件未确认的事"},
    )
    core.repo.record_adapter_event(
        event_id="adapter-event-1",
        user_id="user-1",
        conversation_id="adapter-only",
        turn_id="stop-1",
        event_type="assistant_stop",
        occurred_at="2030-01-03T10:00:00+08:00",
        payload={"private_payload": "must-not-leak"},
    )
    core.repo.record_adapter_event(
        event_id="adapter-event-mixed",
        user_id="user-1",
        conversation_id="conversation-a",
        turn_id="stop-a",
        event_type="assistant_stop",
        occurred_at="2030-01-01T02:30:00+00:00",
        payload={"private_payload": "mixed-secret"},
    )
    core.repo.record_adapter_event(
        event_id="adapter-event-other",
        user_id="user-2",
        conversation_id="other-user-conversation",
        turn_id="stop-other",
        event_type="assistant_stop",
        occurred_at="2030-01-04T10:00:00+08:00",
        payload={"private_payload": "other-user-secret"},
    )
    # Corrupt cross-owner joins are possible in old/manually edited SQLite
    # because ownership equality is not a foreign-key constraint. Projection
    # queries must still exclude both objects.
    other_memory_id = core.repo.memories("user-2")[0].id if core.repo.memories("user-2") else None
    if other_memory_id is None:
        core.observe(
            {
                "user_id": "user-2",
                "conversation_id": "other-memory-source",
                "turn_id": "other-memory-turn",
                "observed_at": "2030-01-04T11:00:00+08:00",
                "timezone": "Asia/Shanghai",
                "role": "user",
                "excerpt": "用户二记忆",
            },
            {"candidate_id": "other-memory-candidate", "kind": "Fact", "summary": "用户二记忆"},
        )
        other_memory_id = core.decide(
            "other-memory-candidate", "accept", "2030-01-04T11:01:00+08:00"
        )["memory_id"]
    observation_a_id = core.repo.db.execute(
        "SELECT id FROM observations WHERE user_id='user-1' AND conversation_id='conversation-a'"
    ).fetchone()[0]
    core.repo.db.execute(
        "INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "cross-owner-candidate",
            observation_a_id,
            "user-2",
            "Fact",
            "不应计入用户一",
            "actual",
            "pending",
            1.0,
            "{}",
            "normal",
            "{}",
            "{}",
        ),
    )
    core.repo.db.execute(
        "INSERT INTO memory_sources(memory_id,source_id) VALUES (?,?)",
        (other_memory_id, observation_a_id),
    )
    core.repo.db.commit()
    ready: queue.Queue = queue.Queue()

    def serve() -> None:
        server = create_server(settings, host="127.0.0.1", port=0)
        ready.put(server)
        server.serve_forever()
        server.server_close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    server = ready.get(timeout=2)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload = _request(base, "/api/conversations")
        assert status == 200
        conversations = payload["data"]["conversations"]
        assert [item["conversation_id"] for item in conversations[:3]] == [
            "adapter-only",
            "conversation-b",
            "conversation-a",
        ]
        adapter_only = conversations[0]
        assert adapter_only["source_kind"] == "adapter"
        assert adapter_only["observation_count"] == 0
        assert adapter_only["adapter_event_count"] == 1
        conversation_a = conversations[2]
        assert conversation_a["source_kind"] == "mixed"
        assert conversation_a["first_activity_at"] == "2030-01-01T10:00:00+08:00"
        assert conversation_a["last_activity_at"] == "2030-01-01T02:30:00+00:00"
        assert conversation_a["candidate_count"] == 1
        assert conversation_a["pending_candidate_count"] == 0
        assert conversation_a["memory_count"] == 1
        conversation_b = conversations[1]
        assert conversation_b["candidate_count"] == 2
        assert conversation_b["pending_candidate_count"] == 1
        assert conversation_b["memory_count"] == 1

        status, payload = _request(base, "/api/conversations/conversation-a")
        assert status == 200
        detail = payload["data"]
        assert detail["observations"][0]["excerpt"] == "示例导师曾陪我走过中央换乘站"
        assert detail["observations"][0]["candidates"][0]["status"] == "accepted"
        assert detail["observations"][0]["memories"][0]["current"] is True
        assert detail["observations"][0]["memories"][0]["id"] == memory_id

        status, payload = _request(base, "/api/conversations/conversation-b")
        assert status == 200
        assert any(
            memory["id"] == memory_id
            for observation in payload["data"]["observations"]
            for memory in observation["memories"]
        )

        status, payload = _request(base, "/api/conversations/adapter-only")
        assert status == 200
        assert payload["data"]["adapter_events"] == [
            {
                "turn_id": "stop-1",
                "event_type": "assistant_stop",
                "occurred_at": "2030-01-03T10:00:00+08:00",
            }
        ]
        serialized = json.dumps(payload, ensure_ascii=False)
        assert "must-not-leak" not in serialized

        status, payload = _request(base, "/api/conversations/other-user-conversation")
        assert status == 404
        assert payload["error"]["code"] == "conversation_not_found"
    finally:
        server.shutdown()
        thread.join(timeout=2)
