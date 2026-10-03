from __future__ import annotations

import os
import subprocess
import sys

import pytest

from htc_core.client import HtcClient


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process probe")
def test_windows_probe_never_sends_a_signal(monkeypatch) -> None:
    def forbidden_kill(*args):
        raise AssertionError("A Windows liveness probe must not call os.kill")

    monkeypatch.setattr(os, "kill", forbidden_kill)
    assert HtcClient._pid_is_alive(os.getpid())
    assert not HtcClient._pid_is_alive(0)
    assert not HtcClient._pid_is_alive(-1)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process probe")
def test_windows_probe_distinguishes_running_and_exited_process(monkeypatch) -> None:
    def forbidden_kill(*args):
        raise AssertionError("A Windows liveness probe must not call os.kill")

    monkeypatch.setattr(os, "kill", forbidden_kill)
    child = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdin.read()"],
        stdin=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        assert HtcClient._pid_is_alive(child.pid)
        child.communicate(timeout=10)
        assert not HtcClient._pid_is_alive(child.pid)
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=10)
