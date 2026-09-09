# Global Memory Architecture

## Purpose

HTC is a user-level memory service, not a project-level memory folder. A user
may have many conversations across Codex, Claude, ChatGPT, and other tools, but
those conversations must converge on one local memory owner.

The core boundary is:

```text
many conversation sources -> one HTC user runtime -> one governed memory graph
```

## Product Shape

### HTC Global Runtime

One local process owns the user's HTC database:

```text
~/.htc/
  htc.sqlite3
  runtime.json
  sources/
```

The runtime is started once per user session and is independent of the current
repository. Project configuration may point an adapter at the runtime, but a
project must never own the canonical memory database.

### Source Adapters

Each source implements the same narrow contract:

```text
connect() -> source registration
submit_observation(observation) -> observation id
recall(query, purpose) -> short-lived recall package
```

The first adapters are:

| Source | Live path | Historical path |
|---|---|---|
| Codex | project or global hook -> HTC runtime | exported JSON/JSONL |
| Claude | explicit hook/plugin -> HTC runtime | exported transcript |
| ChatGPT | explicit export/import | exported archive |
| Manual | Workbench capture | text/markdown/JSON |

An adapter may send observations and request a recall package. It may not
decide that a candidate is a durable memory.

## Global Retrieval

“检索所有对话” means searching HTC's normalized observation and memory index,
not opening every host application's private database.

The flow is:

1. A source is explicitly registered for the user.
2. The user grants a scope: live capture, historical import, or both.
3. The adapter normalizes each message into an observation with source,
   conversation id, turn id, observed time, and timezone.
4. HTC deduplicates by `(source_id, source_record_id)` and content hash.
5. The core extracts candidates, preserves time precision, and applies user
   governance.
6. Every future conversation queries the same user-level runtime.

The result is cross-conversation retrieval without pretending that a host
conversation database is an HTC API.

## Bootstrap Existing History

HTC must support a deliberate bootstrap flow:

```text
choose export -> preview source metadata -> import observations
-> review candidates -> establish initial memory snapshot
```

The first import is not silently “all history”. The user sees source name,
date range, conversation count, and candidate count before accepting it.
Rejected or sensitive candidates remain out of the active memory projection.

## Privacy and Control

- No background scanning of Codex, Claude, or ChatGPT private storage.
- No source is active until the user explicitly registers it.
- Raw message text is retained only when the selected source policy allows it.
- Adapter events store hashes and minimum metadata by default.
- Memory belongs to the user; conversations are evidence containers.
- Deleting a memory must also revoke its derived recall projections.
- A source can be paused or disconnected without deleting unrelated memories.

## MVP Sequence

1. Move the existing runtime contract into a documented user-level service.
2. Add a `SourceRegistry` backed by the existing SQLite repository.
3. Add a JSONL historical importer with preview, deduplication, and dry-run.
4. Update the Codex adapter to resolve the global runtime instead of a
   project-local database.
5. Add a Workbench source page showing registered sources, import jobs, and
   memory ownership.
6. Validate with two synthetic conversations from two different sources and
   one cross-source recall scenario.

## Non-Goals

- Reading undocumented host databases.
- Uploading a user's history to a hosted service.
- Replacing the chat UI.
- Treating every imported sentence as a permanent memory.
