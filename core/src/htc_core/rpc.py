from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .client import HtcClient
from .codex_adapter import (
    MAX_PROMPT_CHARS,
    _required_text,
    handle_stop,
    handle_user_prompt_submit,
    render_recall_context,
)
from .core import SilentCore
from .runtime import RuntimeSettings


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


class RpcDispatcher:
    def __init__(self, core: SilentCore, settings: RuntimeSettings) -> None:
        self.core = core
        self.settings = settings

    def dispatch(self, envelope: dict[str, Any]) -> dict[str, Any]:
        try:
            version = envelope.get("v")
            operation = envelope.get("op")
            idempotency_key = envelope.get("idempotency_key")
            payload = envelope.get("payload")
            if version != 1:
                raise ValueError("unsupported_rpc_version")
            if not isinstance(operation, str) or not operation:
                raise ValueError("invalid_rpc_operation")
            if (
                not isinstance(idempotency_key, str)
                or not idempotency_key
                or len(idempotency_key) > 128
            ):
                raise ValueError("invalid_idempotency_key")
            if not isinstance(payload, dict):
                raise ValueError("invalid_rpc_payload")
            expected_key = self._expected_idempotency_key(operation, payload)
            if expected_key is not None and idempotency_key != expected_key:
                raise ValueError("invalid_idempotency_key")
            canonical_payload = dict(payload)
            if operation in {
                "codex.user_prompt_submit",
                "codex.stop",
                "codex.user_prompt_hash",
                "codex.stop_hash",
            }:
                canonical_payload.pop("observed_at", None)
                canonical_payload.pop("occurred_at", None)
            request_hash = hashlib.sha256(
                json.dumps(
                    {"op": operation, "payload": canonical_payload},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if operation not in {
                "codex.user_prompt_submit",
                "codex.stop",
                "codex.user_prompt_hash",
                "codex.stop_hash",
                "recall.request",
            }:
                return {"ok": True, "result": self._execute(operation, payload)}
            with self.core.repo.tx():
                cutoff = (
                    datetime.now(ZoneInfo(self.settings.timezone)) - timedelta(hours=24)
                ).isoformat(timespec="seconds")
                self.core.repo.prune_rpc_receipts(cutoff)
                receipt = self.core.repo.rpc_receipt(idempotency_key)
                if receipt:
                    if (
                        receipt["operation"] != operation
                        or receipt["request_hash"] != request_hash
                    ):
                        raise ValueError("idempotency_conflict")
                    return {
                        "ok": True,
                        "result": self._replay_response(operation, payload, receipt["response"]),
                    }
                previous = (
                    self._previous_prompt_response(payload)
                    if operation == "codex.user_prompt_submit" else None
                )
                if previous is not None:
                    result = self._replay_response(operation, payload, previous)
                    response = previous
                else:
                    result = self._execute(operation, payload)
                    response = self._receipt_response(operation, payload, result)
                self.core.repo.save_rpc_receipt(
                    idempotency_key=idempotency_key,
                    operation=operation,
                    request_hash=request_hash,
                    response=response,
                    created_at=datetime.now(ZoneInfo(self.settings.timezone)).isoformat(
                        timespec="seconds"
                    ),
                )
            return {"ok": True, "result": result}
        except (KeyError, TypeError, ValueError) as error:
            return {
                "ok": False,
                "error": {
                    "code": str(error) or type(error).__name__,
                    "message": str(error) or type(error).__name__,
                    "retryable": False,
                },
            }
        except sqlite3.OperationalError as error:
            return {
                "ok": False,
                "error": {
                    "code": "sqlite_operational_error",
                    "message": type(error).__name__,
                    "retryable": True,
                },
            }
        except Exception as error:
            return {
                "ok": False,
                "error": {
                    "code": "internal_error",
                    "message": type(error).__name__,
                    "retryable": True,
                },
            }

    def _previous_prompt_response(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        event = payload["event"]
        conversation_id = _required_text(event, "session_id")
        turn_id = _required_text(event, "turn_id")
        row = self.core.repo.db.execute(
            "SELECT * FROM adapter_events WHERE id=?",
            (f"codex-user-{conversation_id}-{turn_id}",),
        ).fetchone()
        if row is None:
            return None
        previous = json.loads(row["payload_json"])
        prompt = _required_text(event, "prompt", limit=MAX_PROMPT_CHARS)
        if (
            row["user_id"] != self.settings.user_id
            or row["conversation_id"] != conversation_id
            or row["turn_id"] != turn_id
            or previous.get("prompt_sha256") != hashlib.sha256(prompt.encode()).hexdigest()
        ):
            raise ValueError("adapter_event_content_conflict")
        if previous.get("recall_package_id"):
            return {"package_id": previous["recall_package_id"]}
        return None

    def _receipt_response(
        self, operation: str, payload: dict[str, Any], result: dict[str, Any],
    ) -> dict[str, Any]:
        # Persist references only; recall_packages already owns governed content.
        if operation == "recall.request":
            return {"package_id": result["package_id"]}
        if operation == "codex.user_prompt_submit":
            event = payload["event"]
            conversation_id = event["session_id"].strip()[:500]
            turn_id = event["turn_id"].strip()[:500]
            row = self.core.repo.db.execute(
                "SELECT payload_json FROM adapter_events WHERE id=? AND user_id=?",
                (f"codex-user-{conversation_id}-{turn_id}", self.settings.user_id),
            ).fetchone()
            return {"package_id": json.loads(row[0])["recall_package_id"]}
        return {}

    def _replay_response(
        self, operation: str, payload: dict[str, Any], response: dict[str, Any],
    ) -> dict[str, Any]:
        package_id = response.get("package_id")
        if not package_id:
            return {}
        if operation == "codex.user_prompt_submit":
            conversation_id = payload["event"]["session_id"].strip()[:500]
            purpose = "reply"
        else:
            conversation_id = payload["conversation_id"]
            purpose = payload.get("purpose", "reply")
        package = self.core.repo.package(package_id)
        valid = package.user_id == self.settings.user_id and self.core.validate_package(
            package_id, datetime.now(ZoneInfo(self.settings.timezone)).isoformat(),
            purpose=purpose, conversation_id=conversation_id,
        )
        if not valid:
            if operation == "codex.user_prompt_submit":
                return {}
            raise ValueError("recall_package_expired_or_revoked")
        result = self.core.package_payload(package)
        if operation == "codex.user_prompt_submit":
            context = render_recall_context(result)
            return (
                {"hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit", "additionalContext": context,
                }}
                if context else {}
            )
        return self._host_package(result)

    @staticmethod
    def _host_package(package: dict[str, Any]) -> dict[str, Any]:
        return {
            key: package[key]
            for key in ("package_id", "purpose", "issued_at", "expires_at", "adapter_payload")
        }

    def _expected_idempotency_key(
        self,
        operation: str,
        payload: dict[str, Any],
    ) -> str | None:
        client = HtcClient(self.settings)
        if operation == "codex.user_prompt_submit":
            event = payload.get("event")
            if not isinstance(event, dict) or not isinstance(event.get("prompt"), str):
                raise ValueError("invalid_codex_event")
            return client.codex_event_idempotency_key(
                operation,
                event,
                role="user",
                content=event["prompt"],
            )
        if operation == "codex.stop":
            event = payload.get("event")
            if not isinstance(event, dict):
                raise ValueError("invalid_codex_event")
            message = event.get("last_assistant_message") or ""
            if not isinstance(message, str):
                raise ValueError("invalid_last_assistant_message")
            return client.codex_event_idempotency_key(
                operation,
                event,
                role="assistant",
                content=message,
            )
        if operation in {"codex.user_prompt_hash", "codex.stop_hash"}:
            event = payload.get("event")
            if not isinstance(event, dict) or not isinstance(payload.get("content_hash"), str):
                raise ValueError("invalid_codex_event")
            return client.codex_event_idempotency_key(
                operation,
                event,
                role="user" if operation == "codex.user_prompt_hash" else "assistant",
                content_hash=payload["content_hash"],
            )
        return None

    def _execute(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "codex.user_prompt_submit":
            event = payload.get("event")
            if not isinstance(event, dict):
                raise ValueError("invalid_codex_event")
            return handle_user_prompt_submit(
                event,
                core=self.core,
                settings=self.settings,
                observed_at=payload.get("observed_at"),
            )
        if operation == "codex.stop":
            event = payload.get("event")
            if not isinstance(event, dict):
                raise ValueError("invalid_codex_event")
            return handle_stop(
                event,
                core=self.core,
                settings=self.settings,
                occurred_at=payload.get("occurred_at"),
            )
        if operation == "codex.user_prompt_hash":
            return self._record_hash_only_event(
                payload,
                event_type="user_prompt_submit",
                hash_field="prompt_sha256",
                chars_field="prompt_chars",
            )
        if operation == "codex.stop_hash":
            return self._record_hash_only_event(
                payload,
                event_type="assistant_stop",
                hash_field="message_sha256",
                chars_field="message_chars",
            )
        if operation == "mcp.status" or operation == "health.get":
            policy = self.core.repo.user_policy(self.settings.user_id)
            return {
                "user_id": self.settings.user_id,
                "timezone": self.settings.timezone,
                "cross_session_internal_use": policy["cross_session_internal_use"],
                "pending_candidates": len(
                    self.core.repo.candidates(
                        self.settings.user_id,
                        status="pending",
                        limit=200,
                    )
                ),
                "current_memories": len(self.core.repo.memories(self.settings.user_id)),
                "plaintext_candidate_capture": self.settings.allow_plaintext_candidates,
                "daemon_pid": os.getpid(),
            }
        if operation == "mcp.list_candidates":
            status = payload.get("status", "pending")
            limit = max(1, min(int(payload.get("limit", 50)), 200))
            candidates = self.core.repo.candidates(
                self.settings.user_id,
                status=status or None,
                limit=limit,
            )
            return {"candidates": [_candidate_payload(candidate) for candidate in candidates]}
        if operation == "recall.request":
            request = dict(payload)
            request["user_id"] = self.settings.user_id
            package = self.core.recall(request)
            return self._host_package(package)
        raise ValueError("unsupported_rpc_operation")

    def _record_hash_only_event(
        self,
        payload: dict[str, Any],
        *,
        event_type: str,
        hash_field: str,
        chars_field: str,
    ) -> dict[str, Any]:
        event = payload.get("event")
        if not isinstance(event, dict):
            raise ValueError("invalid_codex_event")
        conversation_id = str(event.get("session_id", "")).strip()
        turn_id = str(event.get("turn_id", "")).strip()
        content_hash = payload.get("content_hash")
        content_chars = payload.get("content_chars")
        if not conversation_id or not turn_id or not isinstance(content_hash, str):
            raise ValueError("invalid_codex_event")
        if isinstance(content_chars, bool) or not isinstance(content_chars, int):
            raise ValueError("invalid_content_chars")
        occurred_at = payload.get("occurred_at") or datetime.now(
            ZoneInfo(self.settings.timezone)
        ).isoformat(timespec="seconds")
        event_id_prefix = "codex-user" if event_type == "user_prompt_submit" else "codex-stop"
        event_payload: dict[str, Any] = {
            hash_field: content_hash,
            chars_field: content_chars,
            "offline_deferred": True,
        }
        if event_type == "assistant_stop":
            event_payload["authority"] = "assistant_output_not_user_fact"
        else:
            event_payload["context_injected"] = False
        self.core.repo.record_adapter_event(
            event_id=f"{event_id_prefix}-{conversation_id}-{turn_id}",
            user_id=self.settings.user_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            event_type=event_type,
            occurred_at=str(occurred_at),
            payload=event_payload,
        )
        return {}
