---
type: test
work: FR-004
stage: test
created: 2026-09-22
updated: 2026-09-22
independent: false
agent: null
lens: null
contract: 4
result: passed
candidate: 5b106e26731debcdbc1d305d8421a8df81e74d6a22df3bc79d6a30fd1d302ff5
claim: "M0 daemon 单写者与 Codex 纯客户端"
cycle: 1
sequence: 1
origin: asserted
---

# M0 final synthetic-data acceptance passes

## Record

Acceptance: daemon-owned single writer and Codex thin clients. From core, .venv/Scripts/python.exe -m pytest: 95 passed in 22.14s, exit 0; python -m ruff check src tests: All checks passed. git diff --check exits 0 (existing CRLF notices only). Tests cover synchronized 64-worker Hooks from two unrelated directories, 16 offline events replayed once, no client SQLite access, MCP stdio all three tools with forbidden client DB, hash-only privacy, same DB through different runtime dirs, interrupted claims before/after commit, malformed queue quarantine, startup and close cleanup, normalized prompts, response-loss recovery, expiry/revocation, receipt retention and conflict rollback. RED observed before fixes: recovery 7 failed/2 passed, RPC 8 failed/2 passed, ownership+hash transition 2 failed, conflict and receipt-retention failures. Final code/test SHA256 b476e93437b97198911ab143b86bf46285ad639b376cba6084c08d5d9af9fab6 unchanged since successful run. Synthetic temporary stores only; no real power-loss test, live runtime activation, personal migration or global configuration changes. Existing Workbench /api auth hardening remains outside M0.

## Limits

- Remaining gap:
