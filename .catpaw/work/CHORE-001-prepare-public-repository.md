---
id: CHORE-001
type: chore
mode: gated
status: active
stage: test
created: 2026-09-06
updated: 2026-09-18
closed: null
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
- [ ] Public remote contains only the sanitized `main` history and no legacy branch or PR refs.
- [ ] Repository visibility is PUBLIC.

## Links

- Plan: [CHORE-001 Plan](../plans/CHORE-001-prepare-public-repository.md)

## Current state

The repository is public. The local `main` candidate has sanitized metadata and
content, while the remote still awaits the authorized force-with-lease update
and post-push verification.

## Follow-up

Global user-level runtime design is documented in
`docs/global-memory-architecture.md`. The next implementation milestone is a
Source Registry plus an explicit JSONL historical importer.

## Progress

<!-- catpaw:work-progress:start -->
- Phase: Check
- Next: Record current privacy scan and independent public-readiness review.
<!-- catpaw:work-progress:end -->
