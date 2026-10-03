---
type: test
work: FR-006
stage: test
created: 2026-09-22
updated: 2026-09-22
independent: false
agent: null
lens: null
contract: 4
result: passed
candidate: dc6cd0adfe427876b2d4bfe04637f8cc9ca23bf1883ddba096a2a20e20a79072
claim: "M1 用户级 Codex 安装、注册与回滚"
cycle: 1
sequence: 2
origin: asserted
---

# M1 final regression and temporary CLI smoke

## Record

Acceptance: M1 用户级 Codex 安装、注册与回滚。

Current candidate: dc6cd0adfe427876b2d4bfe04637f8cc9ca23bf1883ddba096a2a20e20a79072.

Executed verification:
- uv run --no-sync --project core pytest -q -> 127 passed, 1 skipped in 544.19s.
- uv run --no-sync --project core ruff check src tests -> All checks passed.
- pnpm run build -> Vite production build passed; only the existing large-chunk warning was emitted.
- Temporary-only CLI smoke -> install dry-run/apply, doctor, rollback preview/apply passed. The temporary session hash was unchanged, the original config hash was restored, identity.json remained, and the temporary bin root was removed. Doctor returned only the expected codex_hook_trust_pending warning.
- Regression coverage includes unknown HTC command conflicts, TOML dotted-key MCP forms, source/dependency reparse rejection, manifest/index installation binding drift, rollback snapshot cleanup failure, version inventory drift, and rollback recovery.

Boundary: no command targeted the real C:\Users\WANGX\.codex, session database, or rollout files. The smoke used only a unique TEMP root.

## Limits

- Remaining gap:
