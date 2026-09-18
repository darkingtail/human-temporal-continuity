---
type: test
work: FR-002
stage: test
created: 2026-09-18
updated: 2026-09-18
independent: false
agent: null
lens: null
contract: 4
result: passed
candidate: 32d13da8948c4e656f076846edb5e6600abbc74a7a49ea740feb7d3d8989f50f
claim: Add governed semantic candidate proposals
cycle: 2
sequence: 2
origin: asserted
---

# Comma scope timezone and atomicity regressions pass

## Record

Targeted RED cases failed before the fix and now pass. Full core verification reports 61 passed; Ruff reports All checks passed. The adapter now preserves comma-scoped speech acts, relative dates use the declared timezone, and failed multi-candidate insertion rolls back the observation so retry succeeds.

## Limits

- Remaining gap:
