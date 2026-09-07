from __future__ import annotations

import hashlib
import re
import uuid
from contextlib import suppress
from datetime import date, datetime, timedelta
from typing import Any

from .models import (
    BootstrapSnapshot,
    Candidate,
    ImportJob,
    ImportSource,
    Memory,
    Observation,
    RecallItem,
    RecallPackage,
)
from .repository import SQLiteRepository

NON_ACTUAL = {"test", "quoted", "hypothetical", "roleplay", "uncertain"}


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SilentCore:
    def __init__(self, repository: SQLiteRepository | None = None) -> None:
        self.repo = repository or SQLiteRepository()

    def observe(self, request: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
        observed_at = request["observed_at"]
        excerpt = request.get("excerpt", request.get("text", ""))[:500]
        observation_id = request.get("observation_id", str(uuid.uuid4()))
        content_hash = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        observation = Observation(
            observation_id,
            request["user_id"],
            request["conversation_id"],
            request["turn_id"],
            observed_at,
            request.get("timezone", "UTC"),
            request.get("role", "user"),
            content_hash,
            excerpt,
            proposal.get("speech_act", "actual"),
        )
        inserted = self.repo.save_observation(observation)
        if not inserted:
            return {
                "observation_id": observation_id,
                "candidate_ids": [],
                "status": "idempotent_replay",
            }
        candidate_id = proposal.get("candidate_id", str(uuid.uuid4()))
        speech_act = proposal.get("speech_act", "actual")
        status = "ignored" if speech_act in NON_ACTUAL else "pending"
        time = dict(proposal.get("time", {}))
        if time.get("relative") == "tomorrow":
            anchor = parse_dt(observed_at)
            time.update(
                {
                    "original_expression": "明天",
                    "anchor_time": observed_at,
                    "expected_at": (anchor.date() + timedelta(days=1)).isoformat(),
                    "timezone": request.get("timezone", "UTC"),
                    "precision": "day",
                }
            )
        candidate = Candidate(
            candidate_id,
            observation_id,
            request["user_id"],
            proposal.get("kind", "Episode"),
            proposal.get("summary", excerpt),
            speech_act,
            status,
            float(proposal.get("confidence", 1.0)),
            time,
            proposal.get("sensitivity", "normal"),
            proposal.get("permissions", {}),
            proposal.get("attributes", {}),
        )
        with self.repo.tx():
            self.repo.save_candidate(candidate)
            reasons = (
                ("speech_act_not_actual",)
                if status == "ignored"
                else (
                    ("relative_time_anchored",)
                    if time.get("anchor_time")
                    else ("candidate_pending_user_decision",)
                )
            )
            self.repo.trace(
                "trace-" + candidate_id,
                "candidate",
                candidate_id,
                reasons,
                excerpt[:200],
                observed_at,
            )
        return {
            "observation_id": observation_id,
            "candidate_ids": [candidate_id],
            "status": status,
            "reason_codes": list(reasons),
        }

    def decide(
        self,
        candidate_id: str,
        decision: str,
        now: str,
        *,
        summary: str | None = None,
        permissions: dict[str, bool] | None = None,
        memory_id: str | None = None,
        merge_into_memory_id: str | None = None,
        merge_expected_revision: int | None = None,
    ) -> dict[str, Any]:
        candidate = self.repo.candidate(candidate_id)
        if candidate.status != "pending":
            return {
                "candidate_id": candidate_id,
                "status": "not_decidable",
                "reason_codes": ["candidate_not_pending"],
            }
        if decision != "accept":
            with self.repo.tx():
                self.repo.set_candidate_status(candidate_id, "rejected")
                self.repo.trace(
                    "trace-decision-" + candidate_id,
                    "decision",
                    candidate_id,
                    ("user_rejected_candidate",),
                    candidate.summary[:200],
                    now,
                )
            return {
                "candidate_id": candidate_id,
                "status": "rejected",
                "reason_codes": ["user_rejected_candidate"],
            }
        if merge_into_memory_id:
            existing = self.repo.memory(merge_into_memory_id)
            if existing.user_id != candidate.user_id:
                raise ValueError("memory_user_mismatch")
            if not self.repo.memory_is_current(existing.id):
                raise ValueError("memory_not_current")
            with self.repo.tx():
                merged = self.repo.revise_memory(
                    existing.id,
                    expected_revision=(
                        existing.revision
                        if merge_expected_revision is None
                        else merge_expected_revision
                    ),
                    event_type="candidate_merged",
                    now=now,
                    summary=summary or candidate.summary,
                    time=candidate.time or existing.time,
                    source_id=candidate.observation_id,
                )
                self.repo.set_candidate_status(candidate_id, "accepted")
                self.repo.bump_user(candidate.user_id, revoke=True)
                self.repo.trace(
                    "trace-decision-" + candidate_id,
                    "decision",
                    candidate_id,
                    ("candidate_merged_into_existing_memory",),
                    candidate.summary[:200],
                    now,
                )
            return {
                "candidate_id": candidate_id,
                "memory_id": merged.id,
                "status": "merged",
                "revision": merged.revision,
                "reason_codes": ["candidate_merged_into_existing_memory"],
            }
        perms = {
            "persist": True,
            "cross_session_internal_use": True,
            "proactive_expression": True,
        }
        if permissions:
            perms.update(permissions)
        # Candidate permissions are extractor output, not user authority. Only
        # the explicit decision payload may change consent at this boundary.
        inherited_cross_session = not (permissions and "cross_session_internal_use" in permissions)
        if candidate.sensitivity == "forbidden":
            perms["proactive_expression"] = False
        if candidate.attributes.get("affect") == "negative":
            perms["proactive_expression"] = False
            category_reason = "negative_affect_internal_only"
        else:
            category_reason = "user_accepted_candidate"
        if inherited_cross_session:
            category_reason += "+cross_session_policy_inherited"
        m = Memory(
            memory_id or "memory-" + candidate.id,
            candidate.user_id,
            candidate.kind,
            summary or candidate.summary,
            "current",
            candidate.speech_act,
            candidate.time,
            "sensitive"
            if candidate.sensitivity in {"personal", "sensitive", "forbidden"}
            else candidate.sensitivity,
            "planned" if candidate.kind.lower() == "intention" else None,
            "unknown" if candidate.kind.lower() == "intention" else None,
            bool(perms["persist"]),
            bool(perms["cross_session_internal_use"]),
            bool(perms["proactive_expression"]),
            1,
            self.repo.user_versions(candidate.user_id)[0],
            (candidate.observation_id,),
        )
        with self.repo.tx():
            self.repo.set_candidate_status(candidate_id, "accepted")
            self.repo.save_memory(m, m.source_ids, "accepted", now)
            self.repo.bump_user(candidate.user_id)
            self.repo.trace(
                "trace-decision-" + candidate_id,
                "decision",
                candidate_id,
                (category_reason,),
                candidate.summary[:200],
                now,
            )
        return {
            "candidate_id": candidate_id,
            "memory_id": m.id,
            "status": "accepted",
            "reason_codes": [category_reason],
        }

    def set_permissions(
        self,
        memory_id: str,
        now: str,
        *,
        expected_revision: int | None = None,
        proactive_expression: bool | None = None,
        cross_session_internal_use: bool | None = None,
    ) -> dict[str, Any]:
        m = self.repo.memory(memory_id)
        if expected_revision is not None and m.revision != expected_revision:
            raise ValueError("revision_conflict")
        values = {
            "proactive_expression": m.proactive_consent
            if proactive_expression is None
            else proactive_expression,
            "cross_session_internal_use": m.cross_session_consent
            if cross_session_internal_use is None
            else cross_session_internal_use,
        }
        with self.repo.tx():
            next_revision = m.revision + 1
            self.repo.db.execute(
                "UPDATE memories SET proactive_consent=?,cross_session_consent=?,revision=revision+1 WHERE id=?",
                (
                    int(values["proactive_expression"]),
                    int(values["cross_session_internal_use"]),
                    memory_id,
                ),
            )
            self.repo.bump_user(m.user_id, revoke=True)
            self.repo.trace(
                f"trace-govern-{memory_id}-{next_revision}",
                "governance",
                memory_id,
                ("proactive_expression_revoked",)
                if not values["proactive_expression"]
                else ("permission_changed",),
                "permission update",
                now,
            )
        return {"memory_id": memory_id, "status": "updated", **values}

    def set_user_policy(self, user_id: str, now: str, *, cross_session_internal_use: bool) -> dict[str, Any]:
        with self.repo.tx():
            values = self.repo.set_user_policy(
                user_id, cross_session_internal_use=cross_session_internal_use
            )
            revocation_epoch, package_version = self.repo.bump_user(user_id, revoke=True)
            self.repo.trace(
                f"trace-policy-{user_id}-{revocation_epoch}-{package_version}",
                "governance",
                user_id,
                ("cross_session_policy_granted" if cross_session_internal_use else "cross_session_policy_revoked",),
                "user-level policy update",
                now,
            )
        return {"user_id": user_id, "status": "updated", **values}

    def register_import_source(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("authorization_scope") != "user_selected":
            raise ValueError("import_source_requires_user_selected_authorization")
        source = ImportSource(
            request["source_id"], request["user_id"], request["kind"],
            request.get("locator", "user-provided"), request["authorization_scope"],
            request.get("content_hash"), request["created_at"],
        )
        with self.repo.tx():
            self.repo.save_import_source(source)
        return {"source_id": source.id, "status": "registered", "memory_authorized": False}

    def start_import(self, request: dict[str, Any]) -> dict[str, Any]:
        source = self.repo.import_source(request["source_id"])
        existing = None
        with suppress(KeyError):
            existing = self.repo.import_job(request["job_id"])
        if existing and existing.source_id != source.id:
            raise ValueError("import_job_source_mismatch")
        if existing and existing.status not in {"queued", "running"}:
            raise ValueError("import_job_not_resumable")
        if existing and existing.status == "running":
            return {"job_id": existing.id, "source_id": existing.source_id, "status": existing.status}
        job = ImportJob(request["job_id"], source.id, source.user_id, "running", 0, 0, (), request["now"], None, None)
        with self.repo.tx():
            self.repo.save_import_job(job)
        return {"job_id": job.id, "source_id": source.id, "status": job.status}

    def import_batch(self, job_id: str, records: list[dict[str, Any]], now: str) -> dict[str, Any]:
        job = self.repo.import_job(job_id)
        source = self.repo.import_source(job.source_id)
        if job.status == "completed" and all(
            self.repo.import_record(job_id, record["source_record_id"]) for record in records
        ):
            return {
                "job_id": job.id,
                "status": job.status,
                "processed_records": job.processed_records,
                "candidate_ids": list(job.candidate_ids),
            }
        if job.status not in {"running", "queued"}:
            raise ValueError("import_job_not_resumable")
        candidate_ids = list(job.candidate_ids)
        processed = job.processed_records
        for record in records:
            source_record_id = record["source_record_id"]
            if self.repo.import_record(job_id, source_record_id):
                continue
            previous = self.repo.import_record_for_source(source.id, source_record_id)
            if previous:
                with self.repo.tx():
                    self.repo.save_import_record(
                        job_id, source_record_id, previous["observation_id"],
                        previous["candidate_id"], "reused_existing_source_record",
                    )
                if previous["candidate_id"]:
                    candidate_ids.append(previous["candidate_id"])
                processed += 1
                continue
            observation_request = {
                "user_id": source.user_id,
                "conversation_id": "import:" + source.id,
                "turn_id": source_record_id,
                "observed_at": record["observed_at"],
                "timezone": record.get("timezone", "UTC"),
                "role": record.get("role", "user"),
                "excerpt": record.get("excerpt", record.get("text", "")),
            }
            proposal = dict(record["proposal"])
            result = self.observe(observation_request, proposal)
            candidate_id = (result.get("candidate_ids") or [None])[0]
            if candidate_id:
                candidate_ids.append(candidate_id)
            with self.repo.tx():
                self.repo.save_import_record(job_id, source_record_id, result["observation_id"], candidate_id or "", result["status"])
            processed += 1
        updated = ImportJob(job.id, job.source_id, job.user_id, "completed", max(job.total_records, processed), processed, tuple(dict.fromkeys(candidate_ids)), job.started_at, now, None)
        with self.repo.tx():
            self.repo.save_import_job(updated)
        return {"job_id": job.id, "status": updated.status, "processed_records": processed, "candidate_ids": list(updated.candidate_ids)}

    def finalize_bootstrap(self, request: dict[str, Any]) -> dict[str, Any]:
        self.repo.ensure_user(request["user_id"])
        for source_id in request.get("source_ids", []):
            if self.repo.import_source(source_id).user_id != request["user_id"]:
                raise ValueError("bootstrap_source_user_mismatch")
        for job_id in request.get("job_ids", []):
            job = self.repo.import_job(job_id)
            if job.user_id != request["user_id"] or job.status != "completed":
                raise ValueError("bootstrap_job_not_completed_or_user_mismatch")
        for candidate_id in request.get("candidate_ids", []):
            if self.repo.candidate(candidate_id).user_id != request["user_id"]:
                raise ValueError("bootstrap_candidate_user_mismatch")
        snapshot = BootstrapSnapshot(
            request["snapshot_id"], request["user_id"], request["mode"],
            tuple(request.get("source_ids", [])), tuple(request.get("job_ids", [])),
            tuple(request.get("candidate_ids", [])), request["established_at"],
        )
        with self.repo.tx():
            self.repo.save_bootstrap_snapshot(snapshot)
        return {"snapshot_id": snapshot.id, "mode": snapshot.mode, "status": "established", "source_ids": list(snapshot.source_ids), "job_ids": list(snapshot.job_ids), "candidate_ids": list(snapshot.candidate_ids)}

    def revise(
        self,
        memory_id: str,
        now: str,
        *,
        expected_revision: int,
        action: str,
        source_id: str,
        summary: str | None = None,
        time: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if action not in {"correct", "supersede", "retract"}:
            raise ValueError("unsupported_revision_action")
        memory = self.repo.memory(memory_id)
        status, current, reason = (
            {
                "correct": ("current", True, "user_correction_overrides_transcript"),
                "supersede": ("superseded", False, "memory_not_current"),
                "retract": ("retracted", False, "memory_not_current"),
            }
        )[action]
        with self.repo.tx():
            updated = self.repo.revise_memory(
                memory_id,
                expected_revision=expected_revision,
                event_type=action,
                now=now,
                summary=summary,
                time=time,
                epistemic_status=status,
                current=current,
                source_id=source_id,
            )
            self.repo.bump_user(memory.user_id, revoke=True)
            self.repo.trace(
                f"trace-revise-{memory_id}-{updated.revision}",
                "governance",
                memory_id,
                (reason,),
                action,
                now,
            )
        return {"memory_id": memory_id, "revision": updated.revision, "reason_codes": [reason]}

    def canonicalize_entity(
        self,
        *,
        entity_id: str,
        user_id: str,
        canonical_name: str,
        aliases: list[str],
        source_id: str,
        now: str,
    ) -> dict[str, Any]:
        with self.repo.tx():
            result = self.repo.canonicalize_entity(
                entity_id=entity_id,
                user_id=user_id,
                canonical_name=canonical_name,
                aliases=tuple(aliases),
                source_id=source_id,
            )
            self.repo.bump_user(user_id, revoke=True)
            self.repo.trace(
                f"trace-entity-{result['entity_id']}-{result['revision']}",
                "entity",
                result["entity_id"],
                ("entity_alias_retracted", "user_correction_overrides_transcript"),
                canonical_name,
                now,
            )
        return {**result, "entity_count": 1, "reason_codes": ["entity_alias_retracted"]}

    def update_lived_context(
        self,
        *,
        user_id: str,
        context: str,
        status: str,
        observed_at: str,
        timezone: str,
        source_id: str,
    ) -> dict[str, Any]:
        if status not in {"open", "closed", "stale"}:
            raise ValueError("invalid_lived_context_status")
        with self.repo.tx():
            previous = self.repo.lived_context(user_id)
            result = self.repo.update_lived_context(
                user_id=user_id,
                context=context,
                status=status,
                observed_at=observed_at,
                timezone=timezone,
                source_id=source_id,
            )
            reason = (
                "new_activity_replaces_stale_context"
                if previous and previous["context"] != context
                else "lived_episode_continues"
            )
            self.repo.trace(
                f"trace-context-{user_id}-{result['revision']}",
                "lived_context",
                user_id,
                (reason,),
                context,
                observed_at,
            )
        return {**result, "reason_codes": [reason]}

    def recall(self, request: dict[str, Any]) -> dict[str, Any]:
        now = request["now"]
        now_dt = parse_dt(now)
        revocation_epoch, package_version = self.repo.user_versions(request["user_id"])
        cross_session_enabled = self.repo.user_policy(request["user_id"])[
            "cross_session_internal_use"
        ]
        items: list[RecallItem] = []
        query = request.get("query", "").lower()
        query_terms = [token for token in re.split(r"[\s，。！？、,.!?;；:：]+", query) if token]
        for segment in tuple(query_terms):
            if re.search(r"[\u4e00-\u9fff]", segment) and len(segment) >= 3:
                query_terms.extend(
                    segment[index : index + 2] for index in range(len(segment) - 1)
                )
        for cue in ("继续", "明天", "后天", "今天", "昨天", "工作", "项目", "伴侣"):
            if cue in query and cue not in query_terms:
                query_terms.append(cue)
        for m in self.repo.memories(request["user_id"]):
            if (
                not m.persist_consent
                or not cross_session_enabled
                or not m.cross_session_consent
                or m.epistemic_status != "current"
            ):
                continue
            relevant = not query_terms or any(token in m.summary.lower() for token in query_terms)
            if not relevant:
                continue
            elapsed_reason: tuple[str, ...] = ()
            expected = m.time.get("expected_at")
            if (
                m.kind.lower() == "intention"
                and expected
                and now_dt.date() > date.fromisoformat(expected)
            ):
                elapsed_reason = ("expected_date_elapsed_outcome_unknown",)
            if not m.proactive_consent:
                category, summary, guidance, reason = (
                    "internal_only",
                    None,
                    "respond gently and avoid pressure",
                    ("proactive_expression_revoked",) + elapsed_reason,
                )
            elif m.sensitivity in {"sensitive", "forbidden"}:
                category, summary, guidance, reason = (
                    "confirm_first",
                    None,
                    "ask before mentioning this sensitive topic",
                    ("sensitive_requires_confirmation",) + elapsed_reason,
                )
            else:
                category, summary, guidance, reason = (
                    "allowed_to_use",
                    m.summary,
                    None,
                    ("memory_relevant_and_allowed",) + elapsed_reason,
                )
            items.append(RecallItem(m.id, category, summary, guidance, m.source_ids, reason))
        package_id = "package-" + uuid.uuid4().hex
        expires = (now_dt + timedelta(minutes=int(request.get("ttl_minutes", 10)))).isoformat()
        p = RecallPackage(
            package_id,
            request["user_id"],
            request["conversation_id"],
            request.get("purpose", "reply"),
            now,
            expires,
            package_version,
            revocation_epoch,
            tuple(items),
        )
        with self.repo.tx():
            self.repo.save_package(p)
            self.repo.trace(
                "trace-recall-" + package_id,
                "recall",
                package_id,
                tuple(sorted({r for i in items for r in i.reason_codes})),
                (
                    "query_sha256="
                    + hashlib.sha256(request.get("query", "").encode()).hexdigest()
                    + f";query_chars={len(request.get('query', ''))}"
                ),
                now,
            )
        adapter_payload = {
            "allowed_memories": [
                {"memory_id": i.memory_id, "summary": i.summary}
                for i in items
                if i.category == "allowed_to_use"
            ],
            "response_guidance": [
                i.guidance for i in items if i.category == "internal_only" and i.guidance
            ],
            "confirmation_prompts": [
                "Ask whether the user wants to discuss a relevant sensitive topic."
                for i in items
                if i.category == "confirm_first"
            ],
            "response_constraints": sorted(
                {
                    "Do not assume an intention was completed because its expected date elapsed."
                    for i in items
                    if "expected_date_elapsed_outcome_unknown" in i.reason_codes
                }
            ),
        }
        return {
            "package_id": package_id,
            "purpose": p.purpose,
            "issued_at": p.issued_at,
            "expires_at": p.expires_at,
            "package_version": p.package_version,
            "revocation_epoch": p.revocation_epoch,
            "items": [
                {
                    "memory_id": i.memory_id,
                    "category": i.category,
                    "summary": i.summary,
                    "guidance": i.guidance,
                    "source_ids": list(i.source_ids),
                    "reason_codes": list(i.reason_codes),
                }
                for i in items
            ],
            "adapter_payload": adapter_payload,
        }

    def validate_package(
        self,
        package_id: str,
        now: str,
        *,
        purpose: str | None = None,
        conversation_id: str | None = None,
    ) -> bool:
        p = self.repo.package(package_id)
        revocation_epoch, package_version = self.repo.user_versions(p.user_id)
        return (
            parse_dt(now) < parse_dt(p.expires_at)
            and revocation_epoch == p.revocation_epoch
            and package_version == p.package_version
            and (purpose is None or purpose == p.purpose)
            and (conversation_id is None or conversation_id == p.conversation_id)
        )

    def explain(self, subject_id: str, *, user_id: str) -> dict[str, Any]:
        return self.repo.get_trace(subject_id, user_id=user_id)

    def explain_memory(self, memory_id: str, *, user_id: str) -> dict[str, Any]:
        memory = self.repo.memory(memory_id)
        if memory.user_id != user_id:
            raise KeyError(memory_id)
        return {
            "memory_id": memory.id,
            "source_ids": list(memory.source_ids),
            "events": self.repo.memory_history(memory.id, user_id=user_id),
            "governance_traces": self.repo.traces_for_subject(memory.id, user_id=user_id),
        }
