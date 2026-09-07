from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tomllib
from pathlib import Path

import jsonschema
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from htc_core.codex_adapter import handle_stop, handle_user_prompt_submit
from htc_core.runtime import RuntimeSettings, open_runtime

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = REPOSITORY_ROOT / "core"


def settings(tmp_path, *, user_id="adapter-user"):
    return RuntimeSettings(tmp_path / "htc.sqlite3", user_id, "Asia/Shanghai", True)


def test_codex_hook_cross_conversation_continuity(tmp_path):
    configured = settings(tmp_path)
    core = open_runtime(configured)
    core.set_user_policy(
        configured.user_id,
        "2030-07-18T20:00:00+08:00",
        cross_session_internal_use=True,
    )
    first = handle_user_prompt_submit(
        {
            "session_id": "session-a",
            "turn_id": "turn-a",
            "prompt": "太晚了，明天继续实现导入功能。",
        },
        core=core,
        settings=configured,
        observed_at="2030-07-18T23:40:00+08:00",
    )
    assert first == {}
    pending = core.repo.candidates(configured.user_id, status="pending")
    assert len(pending) == 1
    assert pending[0].time["expected_at"] == "2030-07-19"
    core.decide(pending[0].id, "accept", "2030-07-18T23:41:00+08:00")

    continued = handle_user_prompt_submit(
        {"session_id": "session-b", "turn_id": "turn-b", "prompt": "继续吧"},
        core=core,
        settings=configured,
        observed_at="2030-07-19T10:00:00+08:00",
    )
    context = continued["hookSpecificOutput"]["additionalContext"]
    assert "明天继续实现导入功能" in context
    assert len(core.repo.candidates(configured.user_id, status="pending")) == 0


def test_hook_never_injects_internal_only_raw_summary(tmp_path):
    configured = settings(tmp_path)
    core = open_runtime(configured)
    core.set_user_policy(
        configured.user_id,
        "2030-07-18T20:00:00+08:00",
        cross_session_internal_use=True,
    )
    observed = core.observe(
        {
            "user_id": configured.user_id,
            "conversation_id": "private-a",
            "turn_id": "private-turn",
            "observed_at": "2030-07-18T21:00:00+08:00",
            "timezone": configured.timezone,
            "role": "user",
            "text": "我对那次秘密评审仍然很难过",
        },
        {
            "candidate_id": "private-candidate",
            "kind": "State",
            "summary": "我对那次秘密评审仍然很难过",
            "speech_act": "actual",
            "sensitivity": "personal",
            "attributes": {"affect": "negative"},
        },
    )
    core.decide(observed["candidate_ids"][0], "accept", "2030-07-18T21:01:00+08:00")
    result = handle_user_prompt_submit(
        {"session_id": "private-b", "turn_id": "private-next", "prompt": "评审的事情呢"},
        core=core,
        settings=configured,
        observed_at="2030-07-19T10:00:00+08:00",
    )
    context = result["hookSpecificOutput"]["additionalContext"]
    assert "秘密评审" not in context
    assert "respond gently" in context


def test_stop_records_hash_only_and_does_not_create_candidate(tmp_path):
    configured = settings(tmp_path)
    core = open_runtime(configured)
    result = handle_stop(
        {
            "session_id": "session-stop",
            "turn_id": "turn-stop",
            "last_assistant_message": "This is assistant output, not a user fact.",
        },
        core=core,
        settings=configured,
        occurred_at="2030-07-19T10:05:00+08:00",
    )
    assert result == {}
    assert core.repo.candidates(configured.user_id) == []
    event = core.repo.adapter_events(configured.user_id)[0]
    assert event["payload"]["authority"] == "assistant_output_not_user_fact"
    assert "assistant output" not in event["payload_json"]


def test_hook_command_reads_stdin_and_emits_valid_json(tmp_path):
    environment = {
        **os.environ,
        "HTC_DB": str(tmp_path / "command.sqlite3"),
        "HTC_USER_ID": "command-user",
        "HTC_TIMEZONE": "Asia/Shanghai",
        "HTC_ALLOW_PLAINTEXT_CANDIDATES": "1",
    }
    completed = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "--project",
            str(CORE_ROOT),
            "python",
            "-m",
            "htc_core.codex_adapter",
            "user-prompt-submit",
        ],
        input=json.dumps(
            {"session_id": "command-session", "turn_id": "command-turn", "prompt": "明天继续"}
        ),
        text=True,
        capture_output=True,
        env=environment,
        cwd=REPOSITORY_ROOT / "docs",
        check=True,
    )
    assert json.loads(completed.stdout) == {}


def test_hook_command_is_unicode_safe_under_legacy_windows_stdout(tmp_path):
    configured = settings(tmp_path, user_id="unicode-user")
    core = open_runtime(configured)
    core.set_user_policy(
        configured.user_id,
        "2030-07-18T20:00:00+08:00",
        cross_session_internal_use=True,
    )
    observed = core.observe(
        {
            "user_id": configured.user_id,
            "conversation_id": "unicode-source",
            "turn_id": "unicode-source-turn",
            "observed_at": "2030-07-18T20:01:00+08:00",
            "timezone": configured.timezone,
            "role": "user",
            "text": "示例导师是以前的前端负责人",
        },
        {
            "candidate_id": "unicode-candidate",
            "kind": "Person",
            "summary": "示例导师是以前的前端负责人",
            "speech_act": "actual",
            "sensitivity": "normal",
        },
    )
    core.decide(observed["candidate_ids"][0], "accept", "2030-07-18T20:02:00+08:00")
    environment = {
        **os.environ,
        "HTC_DB": str(configured.database_path),
        "HTC_USER_ID": configured.user_id,
        "HTC_TIMEZONE": configured.timezone,
        "PYTHONIOENCODING": "cp1252",
    }
    completed = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "--project",
            str(CORE_ROOT),
            "python",
            "-m",
            "htc_core.codex_adapter",
            "user-prompt-submit",
        ],
        input=json.dumps(
            {
                "session_id": "unicode-target",
                "turn_id": "unicode-target-turn",
                "prompt": "你还记得示例导师吗？",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        capture_output=True,
        env=environment,
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    result = json.loads(completed.stdout.decode("ascii"))
    assert "示例导师" in result["hookSpecificOutput"]["additionalContext"]


async def _mcp_smoke(tmp_path):
    environment = {
        **os.environ,
        "HTC_DB": str(tmp_path / "mcp.sqlite3"),
        "HTC_USER_ID": "mcp-user",
        "HTC_TIMEZONE": "Asia/Shanghai",
    }
    params = StdioServerParameters(
        command="uv",
        args=[
            "run",
            "--no-sync",
            "--project",
            str(CORE_ROOT),
            "python",
            "-m",
            "htc_core.mcp_server",
        ],
        env=environment,
        cwd=REPOSITORY_ROOT / "docs",
    )
    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        assert {
            "htc_list_candidates",
            "htc_recall",
            "htc_status",
        } <= names
        assert names == {"htc_list_candidates", "htc_recall", "htc_status"}
        result = await session.call_tool(
            "htc_list_candidates", {"status": "pending", "limit": 10}
        )
        assert not result.is_error
        assert result.structured_content == {"candidates": []}


def test_mcp_stdio_initialize_list_and_call(tmp_path):
    asyncio.run(_mcp_smoke(tmp_path))


def test_project_codex_configuration_and_hook_contract():
    hooks = json.loads((REPOSITORY_ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    config = tomllib.loads((REPOSITORY_ROOT / ".codex" / "config.toml").read_text(encoding="utf-8"))
    assert "UserPromptSubmit" in hooks["hooks"]
    assert any(
        "htc_core.codex_adapter stop" in hook["commandWindows"]
        for group in hooks["hooks"]["Stop"]
        for hook in group["hooks"]
        if "commandWindows" in hook
    )
    assert config["mcp_servers"]["htc"]["args"][-2:] == ["-m", "htc_core.mcp_server"]
    agents = (REPOSITORY_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Before answering each user message" in agents
    assert "Never search repository source, tests, fixtures" in agents
    assert "htc_recall" in agents
    schema = json.loads(
        (REPOSITORY_ROOT / "contracts" / "codex-hook-event.schema.json").read_text(
            encoding="utf-8"
        )
    )
    jsonschema.validate(
        {
            "session_id": "schema-session",
            "turn_id": "schema-turn",
            "hook_event_name": "UserPromptSubmit",
            "prompt": "明天继续",
        },
        schema,
    )


def test_default_hook_capture_is_hash_only(tmp_path):
    configured = RuntimeSettings(tmp_path / "default.sqlite3", "default-user", "Asia/Shanghai")
    core = open_runtime(configured)
    handle_user_prompt_submit(
        {
            "session_id": "default-session",
            "turn_id": "default-turn",
            "hook_event_name": "UserPromptSubmit",
            "prompt": "明天继续一个私人计划",
        },
        core=core,
        settings=configured,
        observed_at="2030-07-18T23:00:00+08:00",
    )
    assert core.repo.candidates(configured.user_id) == []
    events = core.repo.adapter_events(configured.user_id)
    assert len(events) == 1
    assert "私人计划" not in events[0]["payload_json"]
    serialized_database_text = "\n".join(
        str(value)
        for table in ("observations", "candidates", "decision_traces", "adapter_events")
        for row in core.repo.db.execute(f"SELECT * FROM {table}")
        for value in row
    )
    assert "私人计划" not in serialized_database_text
