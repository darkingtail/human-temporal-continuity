---
id: CHORE-001
type: chore
mode: gated
status: done
stage: reflect
created: 2026-09-06
updated: 2026-09-06
closed: 2026-09-08
---

# CHORE-001: Prepare privacy-safe public repository

## Goal

Publish a reusable HTC codebase without private autobiographical material,
machine-specific identifiers, private task references, or prior commit history.

## Acceptance

- [ ] Current tree contains only synthetic examples and portable configuration.
- [ ] Common secret and personal-identifier scans pass.
- [ ] Tests, build, and CatPaw doctor pass.
- [ ] Independent public-readiness review passes.
- [ ] Public remote contains one sanitized root commit and no legacy branch or PR history.
- [ ] Repository visibility is PUBLIC.

## Links

- Plan: [CHORE-001 Plan](../plans/CHORE-001-prepare-public-repository.md)

## Completion

The original repository was deleted and recreated as a public repository. The
remote now contains only the sanitized `main` root commit.

## Follow-up

Global user-level runtime design is documented in
`docs/global-memory-architecture.md`. The next implementation milestone is a
Source Registry plus an explicit JSONL historical importer.
