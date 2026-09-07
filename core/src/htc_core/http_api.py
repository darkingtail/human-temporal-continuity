"""Small local HTTP surface for the Memory Workbench.

The API is intentionally thin: all state transitions still go through
``SilentCore`` and the process opens the same SQLite database as the adapters.
It is a local control plane, not a network service or an authentication layer.
"""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .codex_adapter import now_iso
from .core import SilentCore
from .runtime import RuntimeSettings, open_runtime, settings_from_env


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message or code


def _json(value: Any) -> Any:
    """Convert Core values to JSON without leaking implementation objects."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    raise TypeError(f"unsupported_json_value:{type(value).__name__}")


def memory_dto(memory: Any, sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": memory.id,
        "kind": memory.kind,
        "summary": memory.summary,
        "epistemic_status": memory.epistemic_status,
        "speech_act": memory.speech_act,
        "time": _json(memory.time),
        "sensitivity": memory.sensitivity,
        "intention_state": memory.intention_state,
        "outcome": memory.outcome,
        "persist_consent": memory.persist_consent,
        "cross_session_consent": memory.cross_session_consent,
        "proactive_consent": memory.proactive_consent,
        "revision": memory.revision,
        "source_ids": list(memory.source_ids),
        "sources": _json(sources or []),
    }


def candidate_dto(candidate: Any) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "observation_id": candidate.observation_id,
        "kind": candidate.kind,
        "summary": candidate.summary,
        "speech_act": candidate.speech_act,
        "status": candidate.status,
        "confidence": candidate.confidence,
        "time": _json(candidate.time),
        "sensitivity": candidate.sensitivity,
        "permissions": _json(candidate.permissions),
        "attributes": _json(candidate.attributes),
    }


def _now(settings: RuntimeSettings, body: dict[str, Any] | None = None) -> str:
    supplied = body.get("now") if body else None
    return supplied if isinstance(supplied, str) and supplied else now_iso(settings.timezone)


class WorkbenchService:
    def __init__(self, core: SilentCore, settings: RuntimeSettings) -> None:
        self.core = core
        self.settings = settings
        self.user_id = settings.user_id
        self.core.repo.ensure_user(self.user_id)

    def _memory(self, memory_id: str) -> Any:
        try:
            memory = self.core.repo.memory(memory_id)
        except KeyError as exc:
            raise ApiError(404, "memory_not_found") from exc
        if memory.user_id != self.user_id:
            raise ApiError(404, "memory_not_found")
        return memory

    def _candidate(self, candidate_id: str) -> Any:
        try:
            candidate = self.core.repo.candidate(candidate_id)
        except KeyError as exc:
            raise ApiError(404, "candidate_not_found") from exc
        if candidate.user_id != self.user_id:
            raise ApiError(404, "candidate_not_found")
        return candidate

    def status(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "timezone": self.settings.timezone,
            "cross_session_internal_use": self.core.repo.user_policy(self.user_id)[
                "cross_session_internal_use"
            ],
            "current_memories": len(self.core.repo.memories(self.user_id)),
            "pending_candidates": len(
                self.core.repo.candidates(self.user_id, status="pending", limit=200)
            ),
        }

    def memories(self) -> list[dict[str, Any]]:
        memories = self.core.repo.memories(self.user_id)
        memories.sort(key=self._memory_sort_key, reverse=True)
        return [self._memory_dto(item) for item in memories]

    def memory(self, memory_id: str) -> dict[str, Any]:
        return self._memory_dto(self._memory(memory_id))

    def _memory_dto(self, memory: Any) -> dict[str, Any]:
        return memory_dto(
            memory,
            self.core.repo.memory_source_views(memory.id, user_id=self.user_id),
        )

    def _memory_sort_key(self, memory: Any) -> tuple[str, str]:
        for key in ("occurred_at", "start_at", "end_at", "expected_at", "anchor_time"):
            value = memory.time.get(key)
            if isinstance(value, str) and value:
                return value, memory.id
        history = self.core.repo.memory_history(memory.id, user_id=self.user_id)
        return (history[-1]["created_at"] if history else "", memory.id)

    def candidates(self, status: str | None = "pending", limit: int = 50) -> list[dict[str, Any]]:
        if status == "all":
            status = None
        return [
            candidate_dto(item)
            for item in self.core.repo.candidates(self.user_id, status=status, limit=limit)
        ]

    def conversations(self) -> list[dict[str, Any]]:
        return self.core.repo.conversation_summaries(self.user_id)

    def conversation(self, conversation_id: str) -> dict[str, Any]:
        try:
            return self.core.repo.conversation_detail(conversation_id, user_id=self.user_id)
        except KeyError as exc:
            raise ApiError(404, "conversation_not_found") from exc

    def candidate(self, candidate_id: str) -> dict[str, Any]:
        return candidate_dto(self._candidate(candidate_id))

    def explain(self, subject_id: str) -> dict[str, Any]:
        try:
            self._memory(subject_id)
            return self.core.explain_memory(subject_id, user_id=self.user_id)
        except KeyError as exc:
            raise ApiError(404, "memory_not_found") from exc

    def decide(self, candidate_id: str, body: dict[str, Any]) -> dict[str, Any]:
        candidate = self._candidate(candidate_id)
        if candidate.status != "pending":
            raise ApiError(409, "candidate_not_pending")
        decision = body.get("decision")
        if decision not in {"accept", "reject"}:
            raise ApiError(400, "invalid_decision")
        summary = body.get("summary")
        if summary is not None and (
            not isinstance(summary, str) or not summary.strip() or len(summary) > 4_000
        ):
            raise ApiError(400, "invalid_summary")
        merge_target = body.get("merge_into_memory_id")
        merge_expected_revision = body.get("expected_memory_revision")
        if merge_target is not None:
            if (
                decision != "accept"
                or not isinstance(merge_target, str)
                or not merge_target
                or len(merge_target) > 200
            ):
                raise ApiError(400, "invalid_merge_target")
            merge_memory = self._memory(merge_target)
            if (
                isinstance(merge_expected_revision, bool)
                or not isinstance(merge_expected_revision, int)
                or merge_expected_revision < 1
            ):
                raise ApiError(400, "invalid_expected_memory_revision")
            if summary is None:
                summary = merge_memory.summary
        requested_memory_id = body.get("memory_id")
        if requested_memory_id is not None and (
            not isinstance(requested_memory_id, str)
            or not requested_memory_id
            or len(requested_memory_id) > 200
        ):
            raise ApiError(400, "invalid_memory_id")
        permissions = body.get("permissions")
        if permissions is not None and (
            not isinstance(permissions, dict)
            or any(
                key not in {"persist", "cross_session_internal_use", "proactive_expression"}
                or not isinstance(value, bool)
                for key, value in permissions.items()
            )
        ):
            raise ApiError(400, "invalid_permissions")
        try:
            return self.core.decide(
                candidate_id,
                decision,
                _now(self.settings, body),
                summary=summary.strip() if isinstance(summary, str) else None,
                permissions=permissions,
                memory_id=requested_memory_id,
                merge_into_memory_id=merge_target,
                merge_expected_revision=merge_expected_revision,
            )
        except KeyError as exc:
            raise ApiError(404, "related_memory_not_found") from exc
        except ValueError as exc:
            code = str(exc)
            raise ApiError(
                409 if code in {"revision_conflict", "memory_not_current"} else 400,
                code,
            ) from exc

    def revise(self, memory_id: str, body: dict[str, Any]) -> dict[str, Any]:
        memory = self._memory(memory_id)
        source_id = body.get("source_id") or (memory.source_ids[0] if memory.source_ids else "workbench")
        try:
            return self.core.revise(
                memory_id,
                _now(self.settings, body),
                expected_revision=int(body.get("expected_revision", memory.revision)),
                action=body.get("action", "correct"),
                source_id=source_id,
                summary=body.get("summary"),
                time=body.get("time"),
            )
        except KeyError as exc:
            raise ApiError(404, "memory_not_found") from exc
        except ValueError as exc:
            code = str(exc)
            raise ApiError(409 if code == "revision_conflict" else 400, code) from exc

    def permissions(self, memory_id: str, body: dict[str, Any]) -> dict[str, Any]:
        memory = self._memory(memory_id)
        for key in ("proactive_expression", "cross_session_internal_use"):
            if key in body and not isinstance(body[key], bool):
                raise ApiError(400, f"invalid_{key}")
        try:
            return self.core.set_permissions(
                memory_id,
                _now(self.settings, body),
                expected_revision=int(body.get("expected_revision", memory.revision)),
                proactive_expression=body.get("proactive_expression"),
                cross_session_internal_use=body.get("cross_session_internal_use"),
            )
        except ValueError as exc:
            code = str(exc)
            raise ApiError(409 if code == "revision_conflict" else 400, code) from exc

    def policy(self, body: dict[str, Any]) -> dict[str, Any]:
        if "cross_session_internal_use" not in body:
            raise ApiError(400, "missing_cross_session_internal_use")
        if not isinstance(body["cross_session_internal_use"], bool):
            raise ApiError(400, "invalid_cross_session_internal_use")
        return self.core.set_user_policy(
            self.user_id,
            _now(self.settings, body),
            cross_session_internal_use=body["cross_session_internal_use"],
        )

    def recall_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        query = body.get("query")
        conversation_id = body.get("conversation_id", "workbench-preview")
        purpose = body.get("purpose", "reply")
        ttl_minutes = body.get("ttl_minutes", 10)
        if not isinstance(query, str) or not query.strip() or len(query) > 4_000:
            raise ApiError(400, "invalid_query")
        if (
            not isinstance(conversation_id, str)
            or not conversation_id.strip()
            or len(conversation_id) > 200
        ):
            raise ApiError(400, "invalid_conversation_id")
        if not isinstance(purpose, str) or purpose not in {"reply", "reflection", "planning"}:
            raise ApiError(400, "invalid_purpose")
        if isinstance(ttl_minutes, bool) or not isinstance(ttl_minutes, int):
            raise ApiError(400, "invalid_ttl_minutes")
        if not 1 <= ttl_minutes <= 60:
            raise ApiError(400, "invalid_ttl_minutes")
        result = self.core.recall(
            {
                "user_id": self.user_id,
                "conversation_id": conversation_id.strip(),
                "purpose": purpose,
                "query": query.strip(),
                # Preview semantics depend on the actual moment. Browser input
                # must not be able to forge whether an intention has elapsed.
                "now": now_iso(self.settings.timezone),
                "ttl_minutes": ttl_minutes,
            }
        )
        for item in result["items"]:
            item["display_summary"] = self._memory(item["memory_id"]).summary
        return result


class WorkbenchRequestHandler(BaseHTTPRequestHandler):
    service: WorkbenchService
    server_version = "HTCWorkbench/0.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin", "")
        if re.fullmatch(r"http://(?:127\.0\.0\.1|localhost):\d+", origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if status != 204:
            self.wfile.write(encoded)

    def _read_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0:
                raise ApiError(400, "invalid_content_length")
            if length > 128_000:
                raise ApiError(413, "request_too_large")
            value = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            raise ApiError(400, "invalid_json") from exc
        if not isinstance(value, dict):
            raise ApiError(400, "json_object_required")
        return value

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        try:
            self._send(200, {"data": self._route_get()})
        except ApiError as exc:
            self._send(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            self._send(500, {"error": {"code": "internal_error", "message": "internal_error"}})

    def do_POST(self) -> None:
        try:
            self._send(200, {"data": self._route_post(self._read_body())})
        except ApiError as exc:
            self._send(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            self._send(500, {"error": {"code": "internal_error", "message": "internal_error"}})

    def _route_get(self) -> Any:
        parsed = urlparse(self.path)
        path = [part for part in parsed.path.split("/") if part]
        query = parse_qs(parsed.query)
        if path == ["api", "status"]:
            return self.service.status()
        if path == ["api", "memories"]:
            return {"memories": self.service.memories()}
        if path == ["api", "candidates"]:
            status = query.get("status", ["pending"])[0]
            try:
                limit = max(1, min(int(query.get("limit", ["50"])[0]), 200))
            except ValueError as exc:
                raise ApiError(400, "invalid_limit") from exc
            return {"candidates": self.service.candidates(status, limit)}
        if path == ["api", "conversations"]:
            return {"conversations": self.service.conversations()}
        if len(path) == 3 and path[:2] == ["api", "conversations"]:
            return self.service.conversation(unquote(path[2]))
        if len(path) == 4 and path[:2] == ["api", "memories"] and path[3] == "explain":
            return self.service.explain(path[2])
        if len(path) == 3 and path[:2] == ["api", "memories"]:
            return self.service.memory(path[2])
        if len(path) == 3 and path[:2] == ["api", "candidates"]:
            return self.service.candidate(path[2])
        raise ApiError(404, "route_not_found")

    def _route_post(self, body: dict[str, Any]) -> Any:
        parsed = urlparse(self.path)
        path = [part for part in parsed.path.split("/") if part]
        if len(path) == 4 and path[:2] == ["api", "candidates"] and path[3] == "decide":
            return self.service.decide(path[2], body)
        if len(path) == 4 and path[:2] == ["api", "memories"] and path[3] == "revise":
            return self.service.revise(path[2], body)
        if len(path) == 4 and path[:2] == ["api", "memories"] and path[3] == "permissions":
            return self.service.permissions(path[2], body)
        if len(path) == 4 and path[:2] == ["api", "memories"] and path[3] == "suppress":
            return self.service.permissions(path[2], {**body, "proactive_expression": False})
        if len(path) == 4 and path[:2] == ["api", "memories"] and path[3] == "delete":
            return self.service.revise(path[2], {**body, "action": "retract"})
        if path == ["api", "policy"]:
            return self.service.policy(body)
        if path == ["api", "recall-preview"]:
            return self.service.recall_preview(body)
        raise ApiError(404, "route_not_found")


def create_server(
    settings: RuntimeSettings | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> HTTPServer:
    resolved = settings or settings_from_env()
    service = WorkbenchService(open_runtime(resolved), resolved)

    class Handler(WorkbenchRequestHandler):
        pass

    Handler.service = service
    # SQLiteRepository owns one connection. A single-threaded local server
    # keeps requests on the creating thread and makes transaction boundaries
    # deterministic without weakening SQLite's thread check.
    return HTTPServer((host, port), Handler)


def main() -> None:
    server = create_server()
    print(
        f"HTC Workbench API listening on http://{server.server_address[0]}:{server.server_address[1]}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
