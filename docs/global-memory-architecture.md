# HTC Global Runtime Architecture

> Status: approved design; M0 verified with synthetic data, M1-M3 planned
>
> Last updated: 2026-09-22
>
> First delivery milestone: M0 — daemon-owned single writer and Codex thin client

## 1. Decision

HTC adopts a **hybrid per-user runtime**:

- one long-lived user process, `htcd`, owns the canonical memory store and all memory semantics;
- Codex, Claude Code, Workbench, CLI, and importers are thin clients;
- all enabled hosts and all working directories connect to the same HTC user;
- a conversation remains a distinct evidence source even though its confirmed memories belong to the user-level graph.

```text
Codex hooks / MCP ---------+
Claude Code hooks / MCP ---+--> HtcClient --> htcd --> one SQLite database
Workbench -----------------+                  |
Importer / CLI ------------+                  +--> governed Memory Graph
```

The product invariant is:

> Threads are many, but the person is one. HTC memory is user-scoped, while conversations remain source-scoped.

## 2. What “global across all projects” means

When an enabled host is opened in any folder:

1. the host-level hook or MCP process discovers the same user runtime;
2. it submits observations using the same `user_id`;
3. HTC keeps the original host, conversation, turn, time, and source metadata;
4. recall is evaluated against the user's governed memory graph;
5. a memory confirmed from project A can be relevant in project B without treating the two host conversations as one conversation.

The current working directory must not determine identity, database location, or runtime routing. No project owns the canonical HTC database.

Global does **not** mean:

- scanning source trees, Git history, build artifacts, or arbitrary files;
- opening Codex or Claude Code private databases and caches;
- automatically importing existing conversation history;
- recording every conversation by default;
- collapsing all host sessions into one giant transcript;
- sharing memories between different operating-system users;
- exposing the runtime over a network interface.

Historical conversations enter HTC only through an explicit, previewable import chosen by the user.

## 3. Current state and migration reason

Before M0, the repository defaulted to a user-level database path,
`~/.htc/htc.sqlite3`, without a single-writer runtime:

- each Hook or MCP process opens SQLite directly;
- repository initialization performs schema and migration work per process;
- read-like operations such as recall also write audit and usage records;
- concurrent short-lived clients can compete for the same SQLite write lock;
- project-local Codex configuration is still required for activation.

Installing that Adapter globally would multiply lock contention across every
project. The M0 implementation now routes Hook and MCP traffic through the
daemon and has passed synthetic-data tests and independent review. Global registration
remains a separate M1 operation, not an effect of building M0.

## 4. Process boundaries

### 4.1 `htcd`

One process runs for one operating-system user. It owns:

- the only SQLite write connection;
- schema creation and versioned migrations;
- all memory-domain operations and governance;
- RPC idempotency receipts;
- the loopback HTTP API used by Workbench and initial M0 clients;
- later, the Windows named-pipe endpoint;
- offline spool replay, WAL checkpointing, backups, and scheduled maintenance.

It never reads project files as personal memory, reads undocumented host storage, invokes Codex or Claude Code, or binds a non-loopback network address.

### 4.2 Host clients

Hook and MCP processes only:

- parse the host event;
- normalize source and conversation identity;
- send one request to `htcd`;
- render the safe response expected by the host;
- append an offline spool record when the daemon is unavailable.

They never open SQLite, run migrations, or make durable-memory decisions.

### 4.3 Workbench

Workbench remains the user's visibility and governance surface. It talks to the loopback HTTP routes owned by `htcd`; it is not the memory core itself.

### 4.4 Importer

The importer parses only files explicitly selected by the user, previews the source and time range, and sends normalized records to the daemon. It never owns the canonical database.

## 5. Runtime layout

```text
~/.htc/
  identity.json
  config.json
  runtime.json
  install-manifest.json
  htc.sqlite3
  htc.sqlite3-wal
  htc.sqlite3-shm
  spool/
  backups/
  logs/
  sources/
```

- `identity.json`: stable local `user_id` and installation identity;
- `config.json`: capture modes, host enablement, exclusions, and runtime policy;
- `runtime.json`: current daemon PID, protocol version, loopback port, token location, and startup timestamp;
- `install-manifest.json`: installed version, host registrations, and rollback information;
- `spool/`: append-only requests waiting for idempotent replay;
- `sources/`: explicitly registered import-source metadata, not scanned history.

Program files and user data are separate. Upgrading or rolling back the program must not replace the memory database.

## 6. Identity and provenance

```text
user_id          ~/.htc/identity.json
source_id        codex | claude-code | workbench | manual | import:<id>
conversation_id  <source_id>:<host_session_id>
turn_id          host-provided, or deterministically derived when absent
```

The raw host session ID is retained separately. Host source, conversation, and turn provenance must never be inferred from a project path.

The Codex task identifier used by an MCP call and the session identifier used by a Hook must be normalized through one host identity contract; otherwise one host session can accidentally split into two HTC conversations.

## 7. RPC and idempotency

The initial transport is loopback HTTP. A later Windows production transport may use a per-user named pipe while preserving the same request envelope.

```json
{
  "v": 1,
  "op": "observe.submit",
  "idempotency_key": "...",
  "payload": {}
}
```

Every side-effecting request uses a key derived from:

```text
sha256(user_id | operation | source_id | conversation_id | turn_id | role | content_hash)
```

The daemon stores a short-lived `rpc_receipts` record. Replaying the same key and
request returns the original response; reusing a key for different content is an
idempotency conflict and writes nothing. Receipt rows store package references,
not copies of recalled text. A retry must pass the current package TTL,
user/conversation/purpose binding, and revocation checks. An invalidated package
is never replayed: Hooks receive empty context and recall RPC returns an error.

SQLite write transactions use `BEGIN IMMEDIATE`. Candidate decisions and other state transitions check and update their precondition inside the same transaction.

## 8. Offline behavior

The client discovery ladder is:

```text
runtime manifest -> loopback HTTP -> append JSONL spool -> return host-safe output
```

When the daemon is unavailable:

- observation events are written to the spool with their idempotency key;
- hooks do not block the host indefinitely;
- no memory context is invented;
- daemon startup replays pending entries transactionally;
- successful replay removes or checkpoints the entry only after receipt.

Recall cannot be reconstructed offline. A failed recall produces honest silence, while an observation can be queued for later processing.

M0 defaults to hash-only offline Hook metadata. Reconstructing prompt-derived
Candidates requires explicit plaintext opt-in and synthetic data in this slice.
Replay claims live in `spool/replaying`; after interruption they are retried
under a single replay lock. Malformed or nonretryable records move to
`spool/failed`, and recoverable failures keep their claims for the next attempt.

## 9. Privacy and user control

Capture and installation are separate decisions. A globally installed runtime does not imply that every host or project is observed.

Recommended capture modes:

| Mode | Behavior |
|---|---|
| `off` | No observation is submitted. |
| `signals` | Submit only bounded temporal, intention, relationship, and explicit-memory signals; avoid retaining full raw prompts. |
| `full` | Permit raw-text Candidates under explicit user opt-in and storage policy. |

Rules:

- default global activation uses `signals`, not `full`;
- M0 engineering tests use synthetic data only;
- each host is enabled separately;
- project allow/deny decisions are enforced in the client before any request or daemon audit record is created;
- the user can pause all capture or disconnect one host;
- sensitive memory remains subject to recall and expression governance;
- no telemetry is required for the local product;
- real verbatim memory capture remains opt-in until encryption-at-rest policy is explicitly implemented or accepted.

## 10. Host integration

### Codex

The production installation uses user-level configuration:

- `~/.codex/config.toml` for MCP registration;
- user-level Hooks for prompt and stop events when supported;
- `~/.codex/AGENTS.md` as an MCP recall/bootstrap fallback;
- absolute versioned shims, never repository-relative commands.

### Claude Code

The production installation uses user-level configuration:

- `~/.claude/settings.json` Hooks;
- user-level MCP registration;
- `UserPromptSubmit`, `Stop`, `SessionStart`, and `PreCompact` integration;
- the same RPC contract and Memory Graph used by Codex.

Host delivery gaps must be measured and reported. HTC never claims to remember an event that the host did not deliver and the user did not explicitly import.

## 11. Delivery milestones

### M0 — daemon single writer and Codex thin client

Scope:

- extract database ownership and migration from per-client initialization;
- add `htcd` with loopback HTTP;
- add `runtime.json` discovery;
- add `HtcClient` and offline JSONL spool;
- convert Codex Hook and MCP paths into clients;
- preserve current Hook and Workbench external behavior;
- prove cross-working-directory concurrency.

Acceptance:

1. two unrelated working directories invoke 64 concurrent Codex Hook requests;
2. zero `OperationalError: database is locked` events occur;
3. every turn produces exactly one Observation;
4. with the daemon stopped, 16 requests enter the spool and create no database observations;
5. after restart, all 16 requests replay exactly once;
6. no Hook or MCP client opens SQLite;
7. the existing Core tests continue to pass.

Explicitly out of scope for M0:

- global host registration;
- Claude Code Adapter;
- Windows named pipes;
- installer and login autostart;
- encryption at rest;
- new Workbench visual design.

### M1 — global Codex installation

- versioned per-user program installation;
- user-level Codex Hook and MCP registration;
- user-level instruction fallback;
- install, doctor, uninstall, and rollback manifests.

### M2 — Claude Code integration

- user-level Hooks and MCP;
- shared identity, RPC, governance, and graph;
- cross-host recall validation.

### M3 — operational hardening

- Windows named pipe and per-user access controls;
- login or on-demand startup;
- backup, restore, upgrade, and rollback;
- capture-mode and source-control UI;
- encryption-at-rest decision and implementation.

## 12. Architectural invariants

1. Only `htcd` writes the canonical SQLite database.
2. Project paths never select the user identity or memory database.
3. Memory belongs to the user; observations belong to identifiable sources.
4. Host clients cannot accept or mutate durable memory without governed user interaction.
5. A retry cannot create duplicate observations, candidates, or decisions.
6. Excluded sources leave no daemon-side observation or audit payload.
7. A degraded path fails silently but honestly: no blocking chat and no invented memory.
8. Existing history is imported explicitly, previewed, and deduplicated.
9. Program upgrades are reversible without rewriting user data.
10. Workbench is a control surface, not a second memory authority.

## 13. Immediate implementation order

1. characterize current transaction and Adapter behavior with regression tests;
2. introduce a daemon-owned Store and versioned migration ledger;
3. add runtime discovery, HTTP client, spool, and replay;
4. run Workbench routes through the daemon dispatcher;
5. convert Codex Hook and MCP paths to pure clients;
6. execute M0 concurrency, outage, replay, and deduplication acceptance tests;
7. only then begin global Codex registration.
