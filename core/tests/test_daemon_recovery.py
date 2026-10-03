from __future__ import annotations

import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from htc_core.client import HtcClient, RuntimeManifest
from htc_core.daemon import InstanceLock, create_daemon_server, replay_spool
from htc_core.runtime import RuntimeSettings


def settings_for(tmp_path: Path) -> RuntimeSettings:
    return RuntimeSettings(
        tmp_path / "memory.sqlite3", "recovery-user", "Asia/Shanghai", True,
        runtime_dir=tmp_path / "runtime",
    )


def enqueue(settings: RuntimeSettings, turn: str = "one") -> Path:
    client = HtcClient(settings)
    payload = {
        "event": {
            "session_id": "recovery-session",
            "turn_id": turn,
            "prompt": "\u660e\u5929\u7ee7\u7eed",
        },
        "observed_at": "2030-07-18T23:40:00+08:00",
    }
    key = client.codex_event_idempotency_key(
        "codex.user_prompt_submit", payload["event"],
        role="user", content=payload["event"]["prompt"],
    )
    return client.spool_envelope("codex.user_prompt_submit", payload, idempotency_key=key)


@pytest.mark.parametrize("already_committed", [False, True])
def test_restart_recovers_claimed_spool_exactly_once(tmp_path, already_committed):
    settings = settings_for(tmp_path)
    path = enqueue(settings)
    server = create_daemon_server(settings, port=0)
    try:
        dispatcher = server.RequestHandlerClass.dispatcher
        if already_committed:
            assert dispatcher.dispatch(json.loads(path.read_text(encoding="utf-8")))["ok"]
        staging = settings.spool_dir / "replaying" / path.name
        staging.parent.mkdir()
        path.replace(staging)
    finally:
        server.server_close()

    restarted = create_daemon_server(settings, port=0)
    try:
        assert replay_spool(settings, dispatcher=restarted.RequestHandlerClass.dispatcher) == 1
        assert replay_spool(settings, dispatcher=restarted.RequestHandlerClass.dispatcher) == 0
        assert not staging.exists()
        core = restarted.RequestHandlerClass.service.core
        assert core.repo.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
    finally:
        restarted.server_close()


@pytest.mark.parametrize("content", ["", "[]", "{broken", '{"v": 1}', '{}\n{}\n'])
def test_bad_spool_is_quarantined_without_blocking_valid_entries(tmp_path, content):
    settings = settings_for(tmp_path)
    enqueue(settings)
    bad = settings.spool_dir / "bad.jsonl"
    bad.write_text(content, encoding="utf-8")
    server = create_daemon_server(settings, port=0)
    try:
        assert replay_spool(settings, dispatcher=server.RequestHandlerClass.dispatcher) == 1
        assert not bad.exists()
        assert (settings.spool_dir / "failed" / bad.name).read_text(encoding="utf-8") == content
    finally:
        server.server_close()


def test_manifest_publication_failure_releases_server_and_lock(tmp_path, monkeypatch):
    settings = settings_for(tmp_path)
    import htc_core.daemon as daemon

    real_create = daemon.create_server
    servers = []

    def track_server(*args, **kwargs):
        server = real_create(*args, **kwargs)
        servers.append(server)
        return server

    def fail_write(self, path):
        raise OSError("synthetic manifest failure")

    monkeypatch.setattr(daemon, "create_server", track_server)
    with monkeypatch.context() as patch:
        patch.setattr(RuntimeManifest, "write", fail_write)
        with pytest.raises(OSError, match="synthetic manifest failure"):
            create_daemon_server(settings, port=0)
    try:
        assert servers[0].socket.fileno() == -1
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            servers[0].RequestHandlerClass.service.core.repo.db.execute("SELECT 1")
        lock = InstanceLock(settings.resolved_runtime_dir / "htcd.lock")
        lock.acquire()
        lock.release()
    finally:
        servers[0].server_close()


def test_close_releases_database_connection(tmp_path):
    server = create_daemon_server(settings_for(tmp_path), port=0)
    db = server.RequestHandlerClass.service.core.repo.db
    server.server_close()
    server.server_close()
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.execute("SELECT 1")


def test_concurrent_replay_does_not_steal_an_inflight_claim(tmp_path):
    settings = settings_for(tmp_path)
    enqueue(settings)
    entered = threading.Event()
    release = threading.Event()
    calls = []

    class Dispatcher:
        def dispatch(self, envelope):
            calls.append(envelope)
            entered.set()
            assert release.wait(5)
            return {"ok": True, "result": {}}

    dispatcher = Dispatcher()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(replay_spool, settings, dispatcher=dispatcher)
        try:
            assert entered.wait(5)
            assert replay_spool(settings, dispatcher=dispatcher) == 0
            assert len(calls) == 1
        finally:
            release.set()
        assert first.result(timeout=5) == 1
    assert list((settings.spool_dir / "replaying").glob("*.jsonl")) == []


def test_retryable_replay_failure_preserves_claim(tmp_path):
    settings = settings_for(tmp_path)
    path = enqueue(settings)

    class Dispatcher:
        def dispatch(self, envelope):
            return {"ok": False, "error": {"code": "busy", "retryable": True}}

    assert replay_spool(settings, dispatcher=Dispatcher()) == 0
    assert (settings.spool_dir / "replaying" / path.name).exists()
    server = create_daemon_server(settings, port=0)
    try:
        assert replay_spool(settings, dispatcher=server.RequestHandlerClass.dispatcher) == 1
    finally:
        server.server_close()


def test_one_database_cannot_have_two_runtime_owners(tmp_path):
    settings = settings_for(tmp_path)
    other = replace(settings, runtime_dir=tmp_path / "other-runtime")
    first = create_daemon_server(settings, port=0)
    try:
        with pytest.raises(RuntimeError, match="htc_daemon_already_running"):
            second = create_daemon_server(other, port=0)
            second.server_close()
    finally:
        first.server_close()
    restarted = create_daemon_server(other, port=0)
    restarted.server_close()
