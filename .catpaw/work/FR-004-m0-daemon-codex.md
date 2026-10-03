---
id: FR-004
type: feature
mode: gated
status: done
stage: reflect
created: 2026-09-18
updated: 2026-09-22
closed: 2026-09-22
contract: 4
acceptance: "M0 daemon 单写者与 Codex 纯客户端"
scope: "."
owner: primary
cycle: 1
candidate: 5b106e26731debcdbc1d305d8421a8df81e74d6a22df3bc79d6a30fd1d302ff5
---

# FR-004: M0 daemon 单写者与 Codex 纯客户端

## Progress

<!-- catpaw:work-progress:start -->
- Phase: Finish
- Next: Completed
<!-- catpaw:work-progress:end -->

## Scope

- In scope: M0 daemon ownership, loopback RPC, runtime discovery, offline
  spool/replay, Codex Hook and MCP thin clients, existing Workbench compatibility,
  and synthetic-data concurrency tests.
- Out of scope: global installation/activation, real-memory migration, Claude
  Code integration, login autostart, encryption, Git publication, and repairing
  the old Codex task.

## Approach

Canonical acceptance: `docs/global-memory-architecture.md`, section 11, M0.

1. Verify 64 concurrent Hook requests from two unrelated directories, no SQLite
   lock errors, and exactly one Observation per turn.
2. Verify 16 offline requests and exactly-once replay without client DB access.
3. Preserve Core and Workbench behavior and review authentication, single-writer
   ownership, idempotency, spool recovery/privacy, and failure cleanup.
4. Obtain independent review for the current candidate before completion.

### Continuity: 2026-09-22

- User requested continuation here from Codex task
  `01a0b4e6-5d7b-7f30-833f-eff360ee6b5c` (人类记忆 (5)).
  Current task: `01a0b57d-2c07-72e2-b845-f6b85866904b`.
- Read the old task without opening or resuming its UI. Its final interrupted
  turn modified daemon, RPC, HTTP authentication and manifest-host validation.
- Existing uncommitted implementation is preserved. FR-005 Windows process-probe
  fix remains present; no attempt is made to rewrite old conversation history.
- Fresh baseline in `core`: `.venv/Scripts/python.exe -m pytest` reports
  **68 passed in 18.11s**; `.venv/Scripts/python.exe -m ruff check src tests`
  reports **All checks passed**.
- These are baseline results, not independent review or full M0 acceptance.
  The prior review's claimed resolutions still need current-candidate checking.
- HTC recall currently returns `htc_daemon_unavailable`; no live runtime was
  activated and no personal memory was inferred from repository content.
- Next: independent M0 contract review, reproduce material findings with
  synthetic-data regression tests, fix within scope, rerun checks and record
  candidate-bound evidence. Global installation remains outside this Work.

### Execution And Verification: 2026-09-22

- Independent checker Faraday (`01a0c70d-cd35-7a70-852e-1e15827aaced`)
  identified prompt/key normalization mismatch, missing recall idempotency and
  lost Hook responses on retry. Primary reproduced these in regression tests:
  initial `test_rpc_retries.py` result **8 failed, 2 passed**.
- Primary recovery checks reproduced abandoned replay claims, malformed queue
  crashes and startup/shutdown resource leaks: initial `test_daemon_recovery.py`
  result **7 failed, 2 passed**.
- Fixes preserve recoverable claims under a replay lock, quarantine invalid
  entries, release runtime resources, align prompt normalization and recover
  responses by governed package reference without duplicate recall usage.
- Added current-TTL/revocation checks, default offline privacy, Hook/MCP SQLite
  purity checks, and synchronized 64-worker cross-directory Hook coverage.
- Current full suite: **91 passed in 20.56s**; Ruff: **All checks passed**.
  This was the intermediate verification before the final ownership/transition
  fixes, not completion evidence.
- Independent re-review reproduced two more blockers: alternate runtime
  directories bypassed the database writer lock, and hash-only replay prevented
  later online delivery of the same turn. Both new regression cases failed
  before correction, then passed in the **23-test lifecycle/RPC run**.
- Daemon now locks both runtime directory and resolved database path. Adapter
  events refresh the package reference for matching content only; an offline
  delivery cannot downgrade it, and conflicting same-turn content rolls back.
- The same-turn conflict regression exposed an earlier duplicate-trace failure;
  a second RED test reproduced the same failure after RPC receipt retention.
  Dispatcher now validates existing events before executing side effects and
  reuses the governed package reference, including after receipt pruning.
- Final primary suite: **95 passed in 22.14s**; Ruff: **All checks passed**.
  Source/test SHA-256 audit:
  `b476e93437b97198911ab143b86bf46285ad639b376cba6084c08d5d9af9fab6`.
  Independent checker Faraday also ran the full suite: **95 passed in 21.25s**
  with `-B -p no:cacheprovider`; Ruff `--no-cache` passed.
- Independent verdict: qualified M0 pass, no remaining blockers in reviewed
  source. Additional checks cover receipt pruning plus expiry, nonretryable
  same-turn content conflict, and unchanged package/event/usage counts.
  No-write requested + audited, not enforced read-only isolation; 21 reviewed
  source/test hashes were unchanged. Primary accepts the usable check result.
- Recovery testing simulates persisted crash states; actual power loss/process
  kill was not exercised. This limitation does not claim real power-loss proof.
- Runtime installation, personal-data migration, production Workbench access
  control and global activation remain outside M0. `/api/*` retains existing
  local Host/Origin checks; the runtime token protects `/rpc` only.

## Delivery

- Current working tree only; no commit, push, installation, live runtime
  activation, or personal-data migration.
- M0 acceptance is covered by `core/tests/test_global_runtime.py`,
  `test_daemon_recovery.py`, `test_rpc_retries.py`, client process-probe,
  Codex Adapter and existing Core/HTTP tests.
- Next phase is M1 user-level Codex installation. Treat its host configuration
  changes and activation as a separate explicitly authorized operation.

## Links

- Plan: inline above; architecture contract in `docs/global-memory-architecture.md`.
