---
type: test
work: FR-006
stage: test
created: 2026-09-23
updated: 2026-09-23
independent: false
agent: null
lens: null
contract: 4
result: passed
candidate: ee60ea65e96098c88a97bc7f736eac240cfaca8ce7613c271488766cbd9c9828
claim: "M1 用户级 Codex 安装、注册与回滚"
cycle: 1
sequence: 1
origin: asserted
---

# M1 regression and temporary CLI smoke

## Record

Acceptance: M1 用户级 Codex 安装、注册与回滚。

Executed verification:
- uv run --no-sync --project core pytest -q -> 119 passed in 143.48s.
- uv run --no-sync --project core ruff check src tests -> All checks passed.
- pnpm run build -> Vite production build passed.
- Temporary-only CLI smoke -> install dry-run/apply, doctor, rollback preview/apply passed. The temporary session file hash was unchanged, the original config hash was restored, identity.json remained, and the temporary bin root was removed. Doctor returned only the expected codex_hook_trust_pending warning.

Boundary: no command targeted the real C:\Users\WANGX\.codex, session database, or rollout files.

## Limits

- Remaining gap:
