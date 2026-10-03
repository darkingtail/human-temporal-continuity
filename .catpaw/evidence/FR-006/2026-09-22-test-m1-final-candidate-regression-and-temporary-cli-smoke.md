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
candidate: d1cc264845a812c091396fa0898b406f1b12070c4bc01b7f62b16b99b3701c2c
claim: "M1 用户级 Codex 安装、注册与回滚"
cycle: 1
sequence: 4
origin: asserted
---

# M1 final candidate regression and temporary CLI smoke

## Record

Acceptance: M1 用户级 Codex 安装、注册与回滚。

Current candidate: d1cc264845a812c091396fa0898b406f1b12070c4bc01b7f62b16b99b3701c2c.

Executed verification for this candidate:
- uv run --no-sync --project core pytest -q -> 128 passed, 1 skipped in 559.34s.
- uv run --no-sync --project core ruff check src tests -> All checks passed.
- pnpm run build -> Vite production build passed; only the existing large-chunk warning was emitted.
- Temporary-only CLI smoke -> install dry-run/apply, doctor, rollback preview/apply passed. The temporary session hash was unchanged, the original config hash was restored, identity.json remained, and the temporary bin root was removed. Doctor returned only the expected codex_hook_trust_pending warning.
- Final regression coverage includes unknown HTC command conflicts, TOML dotted-key MCP forms, source/dependency reparse rejection, manifest/index installation binding drift, arbitrary user-command migration refusal, rollback snapshot cleanup failure, version inventory drift, and rollback recovery.

Boundary: no command targeted the real C:\Users\WANGX\.codex, session database, or rollout files. The smoke used only a unique TEMP root.

## Limits

- Remaining gap:
