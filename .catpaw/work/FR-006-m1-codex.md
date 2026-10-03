---
id: FR-006
type: feature
mode: gated
status: active
stage: test
created: 2026-09-22
updated: 2026-09-22
closed: null
contract: 4
acceptance: "M1 用户级 Codex 安装、注册与回滚"
scope: "."
owner: primary
cycle: 1
candidate: null
---

# FR-006: M1 用户级 Codex 安装、注册与回滚

## Progress

<!-- catpaw:work-progress:start -->
- Phase: Check
- Next: 最终 candidate 已完成完整 pytest、ruff、前端 build 与临时 CLI smoke；Hume 独立审查正文不可读，保留 independent-proof gap；真实 ~/.codex 与会话文件未触碰
<!-- catpaw:work-progress:end -->

## Scope

- In scope: user-level install, Codex hooks/MCP/AGENTS registration, runtime ensure,
  read-only doctor, exact rollback/uninstall, path and preimage safety.
- Out of scope: changing real `~/.codex` or session storage, trust approval, push/PR,
  and production activation.

## Approach

- Keep install dry-run by default and write only explicit `--apply` targets.
- Copy the runtime into a versioned user program root; keep identity/data separate.
- Treat Codex files as merge targets and reject ambiguous ownership or drift.
- Rollback validates postimages, backup hashes, fixed target scope, and version inventory
  before restoring; use a temporary current snapshot to recover a partial restore.
- Verify only temporary directories; never use the real user Codex/session paths.

## Verification

- `uv run --no-sync --project core pytest -q`: 128 passed, 1 skipped.
- `uv run --no-sync --project core ruff check src tests`: passed.
- `pnpm run build`: passed (Vite emitted only the existing large-chunk warning).
- Temporary CLI smoke: install dry-run/apply, doctor, rollback preview/apply; session
  hash unchanged, config preimage restored, identity retained, and bin root removed.
- The final regression set also covers refusing arbitrary user-command migration from
  a tampered manifest.
- Independent review gap: the latest Hume task completed, but the Codex thread API
  returned no readable review body; older review findings were not reused as
  current-candidate proof.

## Links

- Plan: [FR-006 Plan](../plans/FR-006-m1-codex.md)
