# HTC Silent Core

This directory contains the first executable vertical slice of Human Temporal
Continuity:

```text
observe -> candidate -> decide -> memory -> recall -> explain
```

It is a Python 3.12 library backed by SQLite, plus a small JSON CLI for local
testing and governance. It deliberately has no HTTP server, LLM dependency,
vector database, or integration with private host caches.

The FR-007 database stores minimized observation evidence rather than raw chat
history. It is still plaintext SQLite and is only approved for synthetic test
data in this slice.

## Development

```powershell
cd core
uv sync --python 3.12
uv run pytest
uv run ruff check src tests
```

The CLI accepts one JSON object from a file or standard input:

```powershell
uv run htc-core --db .\demo.sqlite3 observe --input .\observation.json
uv run htc-core --db .\demo.sqlite3 decide --input .\decision.json
uv run htc-core --db .\demo.sqlite3 recall --input .\recall.json
uv run htc-core --db .\demo.sqlite3 explain --id <trace-id> --user-id <user-id>
```

Structured candidate proposals are a fixture boundary, not a claim of general
natural-language understanding. A future host or LLM extractor may propose the
same structure, but it will remain unable to write Memory directly.

## Midstream adoption and recovery

HTC is designed for users who already have history before installation. The
current core supports explicit source registration, idempotent import jobs, and
bootstrap snapshots:

```text
ImportSource -> ImportJob -> Observation -> Candidate -> decide -> Memory
```

An import is not memory authorization. Imported material enters Candidate Inbox;
only a user decision can promote it to Memory. Cross-conversation internal use is
a separate user-level permission and defaults to off.

See [Bootstrap 与记忆恢复](../docs/bootstrap-memory-recovery.md) for the
product model, boundaries, and JSON CLI flow.

## Codex Adapter MVP

The package also installs two executable entrypoints:

```powershell
uv run htc-codex-hook user-prompt-submit
uv run htc-codex-hook stop
uv run htc-mcp
uv run htc-workbench-api
```

The Hook commands read one Codex Hook JSON object from stdin. The MCP command
runs an STDIO server. They share `~/.htc/htc.sqlite3` by default and accept
`HTC_DB`, `HTC_USER_ID`, and `HTC_TIMEZONE` overrides.
Plaintext Candidate capture is off by default and requires the explicit
`HTC_ALLOW_PLAINTEXT_CANDIDATES=1` experimental override.

See [Codex Adapter MVP](../docs/codex-adapter-mvp.md) for project configuration,
tool inventory, the cross-conversation validation scenario, and limitations.

## Local Workbench API

The Workbench reads and governs the same user-local SQLite database through a
loopback-only HTTP API. Start it in a separate terminal, then start the Vite UI
as usual:

```powershell
cd core
uv run htc-workbench-api
# another terminal, from the repository root:
pnpm dev
```

The API binds to `127.0.0.1:8765` and does not read any host application's
private database. Vite proxies `/api` to that loopback process; a separately
hosted frontend can set `VITE_HTC_API_BASE`. Read routes include `/api/status`,
`/api/memories`, `/api/candidates`, `/api/conversations`, conversation detail,
and memory detail/explanation routes.
Memory responses include a minimized source projection (conversation id,
observed time, role, and stored excerpt), not raw host history. Governance routes
use `SilentCore` for candidate decisions, corrections, suppression, retraction,
and user policy changes. Inputs are strictly validated and memory writes use
revision conflict checks. Retraction is a logical state change, not physical
erasure.

`POST /api/recall-preview` accepts a prospective local query, purpose, and
simulated conversation id. It uses the server clock and returns both the full
owner-visible category view and the narrower `adapter_payload` that a host may
consume. Each preview creates an audited RecallPackage: its authorization
expires, but its minimized package and trace records are not automatically
physically deleted.

`GET /api/conversations` and `GET /api/conversations/{conversation_id}` expose a
user-scoped audit projection over HTC-owned Observations and Adapter Events.
They include activity times, object counts, minimized excerpts, Candidate state,
Memory links, and Adapter Event type/turn/time metadata. They never return the
Adapter Event payload or read host-private conversation storage. Unknown or
other-user conversation ids return 404.
