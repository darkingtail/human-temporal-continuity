---
id: FR-005
type: feature
mode: tracked
status: done
stage: reflect
created: 2026-09-19
updated: 2026-09-19
closed: 2026-09-19
contract: 4
acceptance: "修复 Windows PID 探测中断 Codex 后台进程"
scope: "."
owner: primary
cycle: 1
candidate: 49823153b0d82c7b1e08f5efbbe2e16961b86c33835779a43d339e67b772f49e
---

# FR-005: 修复 Windows PID 探测中断 Codex 后台进程

## Progress

<!-- catpaw:work-progress:start -->
- Phase: Finish
- Next: Completed
<!-- catpaw:work-progress:end -->

## Scope

- In scope: Windows process liveness check in `core/src/htc_core/client.py`
  and focused regression tests.
- Out of scope: conversation history, Codex installation/configuration,
  existing FR-004 implementation, daemon activation and Git publication.

## Approach

- Desktop logs show backend exit code 3221225786 (0xC000013A) at
  2026-09-18T15:18:46Z and 2026-09-18T17:07:27Z. The latter follows
  `test_client_spools_and_replays_exactly_once` invocation at 17:07:24Z.
- The test starts a daemon in the pytest process; spool replay checks that
  process with `os.kill(pid, 0)`. On Windows, zero is CTRL_C_EVENT,
  not the POSIX no-signal existence check. Do not reproduce by signaling
  the shared host console.
- RED: intercepting os.kill makes both focused tests fail at client.py:153.
- Fix: Windows uses OpenProcess(SYNCHRONIZE), a zero-timeout wait and
  CloseHandle; POSIX retains its existing implementation.
- GREEN: both process-probe tests and all five global-runtime tests pass.
  The original failing test now finishes without interrupting Codex.
- Ruff passes for the changed client and new tests. Full suite:
  `core/.venv/Scripts/python.exe -m pytest`, 68 passed in 78.10 seconds.
- Recovery: revert only this Work's Windows branch and new test file;
  never discard pre-existing uncommitted FR-004 changes.

## Links

- Plan: inline above.
