from __future__ import annotations

import os
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .client import HtcClient
from .codex_adapter import now_iso
from .runtime import settings_from_env

server = MCPServer(
    name="htc",
    title="Human Temporal Continuity",
    description="Local user-level temporal memory governance for AI conversations.",
    instructions=(
        "Use HTC to inspect policy-approved memory. Never treat a Candidate "
        "as Memory, and never reveal internal-only audit content."
    ),
version="0.1.0",
)


def _client() -> HtcClient:
    settings = settings_from_env()
    if os.environ.get("HTC_AUTO_START") == "1":
        from .launcher import ensure_runtime

        ensure_runtime(settings)
    return HtcClient(settings)


@server.tool(
    description="List redacted HTC Candidate metadata without returning candidate text.",
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True),
)
def htc_list_candidates(status: str = "pending", limit: int = 50) -> dict[str, Any]:
    result = _client().call(
        "mcp.list_candidates",
        {"status": status, "limit": limit},
    )
    return result or {"candidates": []}


@server.tool(
    description="Show redacted HTC runtime status without returning memory content.",
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True),
)
def htc_status() -> dict[str, Any]:
    return _client().call("mcp.status", {}) or {}


@server.tool(
    description="Recall policy-approved memory for one conversation and purpose.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False),
)
def htc_recall(
    conversation_id: str,
    query: str,
    purpose: str = "reply",
    ttl_minutes: int = 10,
) -> dict[str, Any]:
    settings = settings_from_env()
    if os.environ.get("HTC_AUTO_START") == "1":
        from .launcher import ensure_runtime

        ensure_runtime(settings)
    package = HtcClient(settings).call(
        "recall.request",
        {
            "conversation_id": conversation_id,
            "purpose": purpose,
            "query": query,
            "now": now_iso(settings.timezone),
            "ttl_minutes": max(1, min(ttl_minutes, 60)),
        },
    )
    return package or {}


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
