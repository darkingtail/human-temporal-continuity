# HTC Implementation Status

> Last updated: 2026-09-22

This page is the canonical implementation-status summary. Product and design documents describe intended behavior; this page distinguishes implemented, project-local, and planned capabilities.

| Capability | Status | Notes |
|---|---|---|
| Human-memory domain model | Implemented MVP | Observation, Candidate, governed Memory, RecallPackage, explanation, revision, and revocation exist in the Python Core. |
| Temporal interpretation | Implemented MVP | Relative time anchoring and intention handling exist for the current bounded Adapter paths. |
| Local SQLite persistence | Implemented | Daemon owns the runtime connection. Hook and MCP clients use HTTP; the embedded development CLI is for isolated synthetic databases. |
| Memory Workbench | Implemented local MVP | Vite UI uses the loopback Python API for review and governance. |
| Codex Hook and MCP Adapter | Implemented project-local MVP | Requires this repository's project configuration; it is not yet a safe global installation. |
| Single-writer daemon | M0 verified with synthetic data | Runtime/database ownership locks, authenticated RPC, transactional receipts, offline recovery and shutdown cleanup passed tests and independent review. |
| Cross-project global Codex activation | Planned | M1 remains a separate user-level installation and activation step. |
| Claude Code live Adapter | Planned | M2 after global Codex validation. |
| Existing-history import | Partial foundations | Import domain structures exist; automatic host-private-database scanning is not planned. |
| Encryption at rest | Not implemented | M0 uses synthetic data; full raw-text capture remains opt-in. |
| Cloud sync / multi-device | Not planned for current local MVP | The current product is single-user and local-first. |

See [HTC Global Runtime Architecture](global-memory-architecture.md) for the approved cross-project design and milestone acceptance criteria.

M0 does not activate a live user runtime. Offline default Hooks retain only
hash metadata; plaintext Candidate capture remains opt-in. The runtime token
protects `/rpc`, not the existing local Workbench `/api/*` control plane.

On September 22, 2026, both primary and independent checks passed all 95 Core
tests and Ruff. Coverage includes 64 synchronized cross-directory Hook clients,
16 offline events replayed exactly once, Hook/MCP SQLite isolation, recovered
claims, malformed queues, response-loss retries and revocation. Crash recovery
uses simulated persisted crash states, not a real power-loss test.
