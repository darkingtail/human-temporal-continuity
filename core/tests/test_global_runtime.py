from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from htc_core.client import HtcClient, RuntimeManifest
from htc_core.codex_adapter import handle_stop, handle_user_prompt_submit
from htc_core.daemon import create_daemon_server, replay_spool
from htc_core.repository import SQLiteRepository
from htc_core.runtime import RuntimeSettings


def _settings(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        tmp_path / "htc.sqlite3",
        "global-user",
        "Asia/Shanghai",
        True,
        runtime_dir=tmp_path / "runtime",
    )


def _start_daemon(settings: RuntimeSettings):
    server = create_daemon_server(settings, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop_daemon(server, thread: threading.Thread) -> None:
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_client_spools_and_replays_exactly_once(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    client = HtcClient(settings)

    for index in range(16):
        result = client.call(
            "codex.user_prompt_submit",
            {
                "event": {
                    "session_id": "offline-session",
                    "turn_id": f"offline-{index}",
                    "prompt": f"明天继续离线任务 {index}",
                },
                "observed_at": "2030-07-18T23:40:00+08:00",
            },
            spool_on_failure=True,
        )
        assert result is None

    spool_files = list(settings.spool_dir.glob("*.jsonl"))
    assert len(spool_files) == 16
    duplicate = client.call(
        "codex.user_prompt_submit",
        {
            "event": {
                "session_id": "offline-session",
                "turn_id": "offline-0",
                "prompt": "明天继续离线任务 0",
            },
            "observed_at": "2030-07-18T23:41:00+08:00",
        },
        spool_on_failure=True,
    )
    assert duplicate is None
    assert len(list(settings.spool_dir.glob("*.jsonl"))) == 16
    assert not settings.database_path.exists()

    server, thread = _start_daemon(settings)
    try:
        assert replay_spool(settings) == 16
        assert replay_spool(settings) == 0
        assert list(settings.spool_dir.glob("*.jsonl")) == []
    finally:
        _stop_daemon(server, thread)

    repository = SQLiteRepository(settings.database_path)
    observation_count = repository.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert observation_count == 16


def test_hook_runs_from_two_unrelated_working_directories_without_direct_db_access(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    server, thread = _start_daemon(settings)
    cwd_a = tmp_path / "project-a"
    cwd_b = tmp_path / "project-b"
    cwd_a.mkdir()
    cwd_b.mkdir()
    environment = {
        **os.environ,
        "HTC_DB": str(tmp_path / "client-must-not-create" / "forbidden.sqlite3"),
        "HTC_RUNTIME_DIR": str(settings.resolved_runtime_dir),
        "HTC_USER_ID": settings.user_id,
        "HTC_TIMEZONE": settings.timezone,
        "HTC_ALLOW_PLAINTEXT_CANDIDATES": "1",
    }

    start = threading.Barrier(64)

    def invoke(index: int) -> subprocess.CompletedProcess[str]:
        start.wait(timeout=30)
        return subprocess.run(
            [sys.executable, "-m", "htc_core.codex_adapter", "user-prompt-submit"],
            cwd=cwd_a if index % 2 == 0 else cwd_b,
            env=environment,
            input=json.dumps(
                {
                    "session_id": f"cross-cwd-{index % 2}",
                    "turn_id": f"turn-{index}",
                    "prompt": f"明天继续跨目录任务 {index}",
                }
            ),
            text=True,
            capture_output=True,
            # Concurrent Windows CreateProcess calls otherwise inherit each
            # other's handles and can leave hook children stuck at shutdown.
            close_fds=True,
            timeout=60,
        )

    try:
        with ThreadPoolExecutor(max_workers=64) as pool:
            completed = list(pool.map(invoke, range(64)))
        assert all(item.returncode == 0 for item in completed)
        assert all("OperationalError" not in item.stderr for item in completed)
        assert all("database is locked" not in item.stdout for item in completed)
        assert all("systemMessage" not in item.stdout for item in completed)
        assert list(settings.spool_dir.glob("*.jsonl")) == []
        assert not Path(environment["HTC_DB"]).exists()
    finally:
        _stop_daemon(server, thread)

    repository = SQLiteRepository(settings.database_path)
    observation_count = repository.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    adapter_event_count = repository.db.execute(
        "SELECT COUNT(*) FROM adapter_events WHERE event_type='user_prompt_submit'"
    ).fetchone()[0]
    assert observation_count == 64
    assert adapter_event_count == 64


def test_same_codex_turn_with_a_new_wall_clock_is_deduplicated(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    server, thread = _start_daemon(settings)
    client = HtcClient(settings)
    event = {
        "session_id": "same-session",
        "turn_id": "same-turn",
        "prompt": "明天继续同一个任务",
    }
    try:
        first = client.call(
            "codex.user_prompt_submit",
            {"event": event, "observed_at": "2030-07-18T23:40:00+08:00"},
        )
        second = client.call(
            "codex.user_prompt_submit",
            {"event": event, "observed_at": "2030-07-18T23:41:00+08:00"},
        )
        assert first == {}
        assert second == {}
    finally:
        _stop_daemon(server, thread)
    repository = SQLiteRepository(settings.database_path)
    assert repository.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
    assert repository.db.execute("SELECT COUNT(*) FROM rpc_receipts").fetchone()[0] == 1


def test_second_daemon_for_same_runtime_is_rejected(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    server, thread = _start_daemon(settings)
    try:
        with pytest.raises(RuntimeError, match="htc_daemon_already_running"):
            create_daemon_server(settings, host="127.0.0.1", port=0)
    finally:
        _stop_daemon(server, thread)


def test_ensure_runtime_waits_for_bootstrap_owner_to_publish_manifest(tmp_path: Path, monkeypatch) -> None:
    import htc_core.launcher as launcher

    settings = _settings(tmp_path)
    states = iter((False, False, True))
    monkeypatch.setattr(launcher, "_manifest_is_live", lambda resolved: next(states))

    def lock_is_owned(self):
        raise OSError("bootstrap lock is held")

    monkeypatch.setattr(launcher._BootstrapLock, "acquire", lock_is_owned)
    monkeypatch.setattr(launcher.time, "sleep", lambda _: None)

    assert launcher.ensure_runtime(settings, timeout=0.2) is True


def test_ensure_runtime_can_take_over_after_bootstrap_lock_release(tmp_path: Path, monkeypatch) -> None:
    import htc_core.launcher as launcher

    settings = _settings(tmp_path)
    states = iter((False, False, False, True))
    monkeypatch.setattr(launcher, "_manifest_is_live", lambda resolved: next(states))
    acquire_calls = 0

    def acquire(self):
        nonlocal acquire_calls
        acquire_calls += 1
        if acquire_calls == 1:
            raise OSError("bootstrap lock is held")

    class FakeProcess:
        def poll(self):
            return None

    monkeypatch.setattr(launcher._BootstrapLock, "acquire", acquire)
    monkeypatch.setattr(launcher._BootstrapLock, "release", lambda self: None)
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(launcher.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(launcher.time, "sleep", lambda _: None)

    assert launcher.ensure_runtime(settings, timeout=0.2) is True
    assert acquire_calls == 2


def test_rpc_rejects_wrong_runtime_token_without_spooling(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    server, thread = _start_daemon(settings)
    manifest = RuntimeManifest.load(settings.manifest_path)
    RuntimeManifest(
        version=manifest.version,
        host=manifest.host,
        port=manifest.port,
        pid=manifest.pid,
        token="wrong-token",
        started_at=manifest.started_at,
    ).write(settings.manifest_path)
    try:
        with pytest.raises(RuntimeError, match="http_401"):
            HtcClient(settings).call("mcp.status", {}, spool_on_failure=True)
        assert list(settings.spool_dir.glob("*.jsonl")) == []
    finally:
        # Restore the real manifest so server_close can identify and remove it.
        manifest.write(settings.manifest_path)
        _stop_daemon(server, thread)


def test_default_offline_hooks_store_no_plaintext_and_replay_metadata(tmp_path):
    settings = RuntimeSettings(tmp_path / "memory.sqlite3", "private-user", "Asia/Shanghai")
    event = {
        "session_id": "private-session",
        "turn_id": "private-turn",
        "prompt": "明天继续私人计划",
        "last_assistant_message": "私人回复不进入事实",
    }
    assert handle_user_prompt_submit(event, settings=settings) == {}
    assert handle_stop(event, settings=settings) == {}
    files = list(settings.spool_dir.glob("*.jsonl"))
    assert len(files) == 2
    for path in files:
        content = path.read_text(encoding="utf-8")
        assert event["prompt"] not in content
        assert event["last_assistant_message"] not in content
    assert not settings.database_path.exists()
    server = create_daemon_server(settings, port=0)
    try:
        assert replay_spool(settings, dispatcher=server.RequestHandlerClass.dispatcher) == 2
        db = server.RequestHandlerClass.service.core.repo.db
        assert db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM adapter_events").fetchone()[0] == 2
    finally:
        server.server_close()


def test_hook_and_mcp_paths_never_open_sqlite(tmp_path, monkeypatch):
    import htc_core.mcp_server as mcp

    settings = _settings(tmp_path)
    server, thread = _start_daemon(settings)
    monkeypatch.setattr(mcp, "settings_from_env", lambda: settings)

    def forbidden_connect(*args, **kwargs):
        raise AssertionError("Host client attempted direct database access")

    monkeypatch.setattr(sqlite3, "connect", forbidden_connect)
    try:
        assert handle_user_prompt_submit(
            {"session_id": "pure-client", "turn_id": "one", "prompt": "明天继续"},
            settings=settings,
        ) == {}
        assert handle_stop(
            {"session_id": "pure-client", "turn_id": "one", "last_assistant_message": "ok"},
            settings=settings,
        ) == {}
        assert mcp.htc_status()["daemon_pid"] == os.getpid()
        assert len(mcp.htc_list_candidates()["candidates"]) == 1
        assert "adapter_payload" in mcp.htc_recall("pure-client", "continue")
    finally:
        _stop_daemon(server, thread)
