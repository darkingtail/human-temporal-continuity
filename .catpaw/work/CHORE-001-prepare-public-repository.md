---
id: CHORE-001
type: chore
mode: gated
status: done
stage: reflect
created: 2026-09-06
updated: 2026-09-18
closed: 2026-09-18
---

# CHORE-001: Prepare privacy-safe public repository

## Goal

Publish a reusable HTC codebase without private autobiographical material,
machine-specific identifiers, private task references, or prior private commit history.

## Acceptance

- [x] Current tree contains only synthetic examples and portable configuration.
- [x] Common secret and personal-identifier scans pass.
- [x] Tests, build, and CatPaw doctor pass.
- [x] Independent public-readiness review passes.
- [x] Public remote contains only the sanitized `main` history and no legacy branch or PR refs.
- [x] Repository visibility is PUBLIC.

## Links

- Plan: [CHORE-001 Plan](../plans/CHORE-001-prepare-public-repository.md)

## Current state

The repository is public. The remote `main` now matches the sanitized local
lineage, exposes no other branch, tag, or pull-request refs, and passed the
post-push privacy and secret-scanning checks.

## Follow-up

Global user-level runtime design is documented in
`docs/global-memory-architecture.md`. The next implementation milestone is a
Source Registry plus an explicit JSONL historical importer.

## Progress

<!-- catpaw:work-progress:start -->
- Phase: Finish
- Next: Completed
<!-- catpaw:work-progress:end -->
