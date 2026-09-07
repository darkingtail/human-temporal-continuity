from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from .codex_adapter import now_iso
from .runtime import open_runtime, settings_from_env

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


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    return {
        "candidate_id": candidate.id,
        "kind": candidate.kind,
        "status": candidate.status,
        "confidence": candidate.confidence,
        "time": candidate.time,
        "sensitivity": candidate.sensitivity,
        "source_observation_id": candidate.observation_id,
        "content_available_in_local_workbench": True,
    }


@server.tool(
    description="List redacted HTC Candidate metadata without returning candidate text.",
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True),
)
def htc_list_candidates(status: str = "pending", limit: int = 50) -> dict[str, Any]:
    settings = settings_from_env()
    runtime = open_runtime(settings)
    candidates = runtime.repo.candidates(settings.user_id, status=status or None, limit=limit)
    return {"candidates": [_candidate_payload(candidate) for candidate in candidates]}


@server.tool(
    description="Show redacted HTC runtime status without returning memory content.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True),
)
def htc_status() -> dict[str, Any]:
    settings = settings_from_env()
    runtime = open_runtime(settings)
    return {
        "user_id": settings.user_id,
        "timezone": settings.timezone,
        "cross_session_internal_use": runtime.repo.user_policy(settings.user_id)[
            "cross_session_internal_use"
        ],
        "pending_candidates": len(runtime.repo.candidates(settings.user_id, status="pending", limit=200)),
        "current_memories": len(runtime.repo.memories(settings.user_id)),
        "plaintext_candidate_capture": settings.allow_plaintext_candidates,
    }


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
    runtime = open_runtime(settings)
    package = runtime.recall(
        {
            "user_id": settings.user_id,
            "conversation_id": conversation_id,
            "purpose": purpose,
            "query": query,
            "now": now_iso(settings.timezone),
            "ttl_minutes": max(1, min(ttl_minutes, 60)),
        }
    )
    return {
        "package_id": package["package_id"],
        "purpose": package["purpose"],
        "issued_at": package["issued_at"],
        "expires_at": package["expires_at"],
        "adapter_payload": package["adapter_payload"],
    }


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
