from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
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
    dump,
    load,
)

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, revocation_epoch INTEGER NOT NULL DEFAULT 0, package_version INTEGER NOT NULL DEFAULT 0, cross_session_consent INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS observations (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), conversation_id TEXT NOT NULL REFERENCES conversations(id), turn_id TEXT NOT NULL, observed_at TEXT NOT NULL, timezone TEXT NOT NULL, role TEXT NOT NULL, content_hash TEXT NOT NULL, excerpt TEXT NOT NULL, speech_act TEXT NOT NULL, UNIQUE(conversation_id, turn_id));
CREATE TABLE IF NOT EXISTS candidates (id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observations(id), user_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL, summary TEXT NOT NULL, speech_act TEXT NOT NULL, status TEXT NOT NULL, confidence REAL NOT NULL, time_json TEXT NOT NULL, sensitivity TEXT NOT NULL, permissions_json TEXT NOT NULL, attributes_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL, summary TEXT NOT NULL, epistemic_status TEXT NOT NULL, speech_act TEXT NOT NULL, time_json TEXT NOT NULL, sensitivity TEXT NOT NULL, intention_state TEXT, outcome TEXT, persist_consent INTEGER NOT NULL, cross_session_consent INTEGER NOT NULL, proactive_consent INTEGER NOT NULL, revision INTEGER NOT NULL, revocation_epoch INTEGER NOT NULL, current INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS memory_sources (memory_id TEXT NOT NULL REFERENCES memories(id), source_id TEXT NOT NULL, PRIMARY KEY(memory_id, source_id));
CREATE TABLE IF NOT EXISTS memory_events (id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT NOT NULL REFERENCES memories(id), event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decision_traces (id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, reason_codes_json TEXT NOT NULL, input_summary TEXT NOT NULL, created_at TEXT NOT NULL, user_id TEXT REFERENCES users(id));
CREATE TABLE IF NOT EXISTS recall_packages (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), conversation_id TEXT NOT NULL, purpose TEXT NOT NULL, issued_at TEXT NOT NULL, expires_at TEXT NOT NULL, package_version INTEGER NOT NULL, revocation_epoch INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS recall_items (package_id TEXT NOT NULL REFERENCES recall_packages(id), memory_id TEXT NOT NULL REFERENCES memories(id), category TEXT NOT NULL, summary TEXT, guidance TEXT, source_ids_json TEXT NOT NULL, reason_codes_json TEXT NOT NULL, PRIMARY KEY(package_id, memory_id));
CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), canonical_name TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, UNIQUE(user_id, canonical_name));
CREATE TABLE IF NOT EXISTS entity_aliases (entity_id TEXT NOT NULL REFERENCES entities(id), alias TEXT NOT NULL, status TEXT NOT NULL, source_id TEXT NOT NULL, PRIMARY KEY(entity_id, alias));
CREATE TABLE IF NOT EXISTS lived_contexts (user_id TEXT PRIMARY KEY REFERENCES users(id), context TEXT NOT NULL, status TEXT NOT NULL, observed_at TEXT NOT NULL, timezone TEXT NOT NULL, source_id TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS import_sources (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), kind TEXT NOT NULL, locator TEXT NOT NULL, authorization_scope TEXT NOT NULL, content_hash TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS import_jobs (id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES import_sources(id), user_id TEXT NOT NULL REFERENCES users(id), status TEXT NOT NULL, total_records INTEGER NOT NULL DEFAULT 0, processed_records INTEGER NOT NULL DEFAULT 0, candidate_ids_json TEXT NOT NULL DEFAULT '[]', started_at TEXT, finished_at TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS import_records (job_id TEXT NOT NULL REFERENCES import_jobs(id), source_record_id TEXT NOT NULL, observation_id TEXT, candidate_id TEXT, status TEXT NOT NULL, PRIMARY KEY(job_id, source_record_id));
CREATE TABLE IF NOT EXISTS bootstrap_snapshots (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), mode TEXT NOT NULL, source_ids_json TEXT NOT NULL, job_ids_json TEXT NOT NULL, candidate_ids_json TEXT NOT NULL, established_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS adapter_events (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), conversation_id TEXT NOT NULL, turn_id TEXT NOT NULL, event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, payload_json TEXT NOT NULL);
"""


class SQLiteRepository:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript(SCHEMA)
        self._migrate()
        self.db.commit()

    def _migrate(self) -> None:
        """Apply additive migrations for databases created by earlier slices."""
        columns = {
            row[1] for row in self.db.execute("PRAGMA table_info(users)").fetchall()
        }
        if "cross_session_consent" not in columns:
            self.db.execute(
                "ALTER TABLE users ADD COLUMN cross_session_consent INTEGER NOT NULL DEFAULT 0"
            )
        trace_columns = {
            row[1] for row in self.db.execute("PRAGMA table_info(decision_traces)").fetchall()
        }
        if "user_id" not in trace_columns:
            self.db.execute("ALTER TABLE decision_traces ADD COLUMN user_id TEXT")
            self.db.execute(
                """UPDATE decision_traces SET user_id=(
                     SELECT user_id FROM candidates WHERE candidates.id=decision_traces.subject_id
                   ) WHERE subject_type IN ('candidate','decision')"""
            )
            self.db.execute(
                """UPDATE decision_traces SET user_id=(
                     SELECT user_id FROM memories WHERE memories.id=decision_traces.subject_id
                   ) WHERE subject_type='governance' AND user_id IS NULL"""
            )
            self.db.execute(
                """UPDATE decision_traces SET user_id=subject_id
                   WHERE subject_type='governance' AND user_id IS NULL
                   AND subject_id IN (SELECT id FROM users)"""
            )
            self.db.execute(
                """UPDATE decision_traces SET user_id=(
                     SELECT user_id FROM recall_packages WHERE recall_packages.id=decision_traces.subject_id
                   ) WHERE subject_type='recall' AND user_id IS NULL"""
            )
            self.db.execute(
                """UPDATE decision_traces SET user_id=(
                     SELECT user_id FROM entities WHERE entities.id=decision_traces.subject_id
                   ) WHERE subject_type='entity' AND user_id IS NULL"""
            )
            self.db.execute(
                """UPDATE decision_traces SET user_id=subject_id
                   WHERE subject_type='lived_context' AND user_id IS NULL
                   AND subject_id IN (SELECT id FROM users)"""
            )
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version < 3:
            self.db.execute("PRAGMA user_version=3")

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.db
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def ensure_user(self, user_id: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO users(id) VALUES (?)", (user_id,))

    def user_policy(self, user_id: str) -> dict[str, bool]:
        self.ensure_user(user_id)
        row = self.db.execute(
            "SELECT cross_session_consent FROM users WHERE id=?", (user_id,)
        ).fetchone()
        return {"cross_session_internal_use": bool(row[0])}

    def set_user_policy(self, user_id: str, *, cross_session_internal_use: bool) -> dict[str, bool]:
        self.ensure_user(user_id)
        self.db.execute(
            "UPDATE users SET cross_session_consent=? WHERE id=?",
            (int(cross_session_internal_use), user_id),
        )
        return self.user_policy(user_id)

    def ensure_conversation(self, user_id: str, conversation_id: str) -> None:
        self.ensure_user(user_id)
        existing = self.db.execute(
            "SELECT user_id FROM conversations WHERE id=?", (conversation_id,)
        ).fetchone()
        if existing and existing["user_id"] != user_id:
            raise ValueError("conversation_user_mismatch")
        self.db.execute(
            "INSERT OR IGNORE INTO conversations(id,user_id) VALUES (?,?)",
            (conversation_id, user_id),
        )

    def save_observation(self, o: Observation) -> bool:
        with self.tx():
            self.ensure_conversation(o.user_id, o.conversation_id)
            existing = self.db.execute(
                "SELECT content_hash FROM observations WHERE conversation_id=? AND turn_id=?",
                (o.conversation_id, o.turn_id),
            ).fetchone()
            if existing and existing["content_hash"] != o.content_hash:
                raise ValueError("idempotency_conflict")
            cur = self.db.execute(
                """INSERT OR IGNORE INTO observations(id,user_id,conversation_id,turn_id,observed_at,timezone,role,content_hash,excerpt,speech_act) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    o.id,
                    o.user_id,
                    o.conversation_id,
                    o.turn_id,
                    o.observed_at,
                    o.timezone,
                    o.role,
                    o.content_hash,
                    o.excerpt,
                    o.speech_act,
                ),
            )
            return cur.rowcount == 1

    def save_candidate(self, c: Candidate) -> None:
        self.db.execute(
            "INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                c.id,
                c.observation_id,
                c.user_id,
                c.kind,
                c.summary,
                c.speech_act,
                c.status,
                c.confidence,
                dump(c.time),
                c.sensitivity,
                dump(c.permissions),
                dump(c.attributes),
            ),
        )

    def candidate(self, cid: str) -> Candidate:
        r = self.db.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()
        if not r:
            raise KeyError(cid)
        return Candidate(
            r["id"],
            r["observation_id"],
            r["user_id"],
            r["kind"],
            r["summary"],
            r["speech_act"],
            r["status"],
            r["confidence"],
            load(r["time_json"], {}),
            r["sensitivity"],
            load(r["permissions_json"], {}),
            load(r["attributes_json"], {}),
        )

    def set_candidate_status(self, cid: str, status: str) -> None:
        self.db.execute("UPDATE candidates SET status=? WHERE id=?", (status, cid))

    def candidates(self, user_id: str, *, status: str | None = None, limit: int = 50) -> list[Candidate]:
        query = "SELECT id FROM candidates WHERE user_id=?"
        params: list[Any] = [user_id]
        if status is not None:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY rowid DESC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        return [self.candidate(row[0]) for row in self.db.execute(query, params)]

    def save_memory(
        self, m: Memory, source_ids: tuple[str, ...], event_type: str, now: str
    ) -> None:
        self.db.execute(
            "INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                m.id,
                m.user_id,
                m.kind,
                m.summary,
                m.epistemic_status,
                m.speech_act,
                dump(m.time),
                m.sensitivity,
                m.intention_state,
                m.outcome,
                int(m.persist_consent),
                int(m.cross_session_consent),
                int(m.proactive_consent),
                m.revision,
                m.revocation_epoch,
                1,
            ),
        )
        self.db.executemany(
            "INSERT INTO memory_sources(memory_id,source_id) VALUES (?,?)",
            [(m.id, s) for s in source_ids],
        )
        self.db.execute(
            "INSERT INTO memory_events(memory_id,event_type,payload_json,created_at) VALUES (?,?,?,?)",
            (m.id, event_type, dump({"source_ids": source_ids}), now),
        )

    def memory(self, mid: str) -> Memory:
        r = self.db.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
        if not r:
            raise KeyError(mid)
        sources = tuple(
            x[0]
            for x in self.db.execute(
                "SELECT source_id FROM memory_sources WHERE memory_id=?", (mid,)
            )
        )
        return Memory(
            r["id"],
            r["user_id"],
            r["kind"],
            r["summary"],
            r["epistemic_status"],
            r["speech_act"],
            load(r["time_json"], {}),
            r["sensitivity"],
            r["intention_state"],
            r["outcome"],
            bool(r["persist_consent"]),
            bool(r["cross_session_consent"]),
            bool(r["proactive_consent"]),
            r["revision"],
            r["revocation_epoch"],
            sources,
        )

    def memory_is_current(self, memory_id: str) -> bool:
        row = self.db.execute(
            "SELECT current,epistemic_status FROM memories WHERE id=?", (memory_id,)
        ).fetchone()
        if not row:
            raise KeyError(memory_id)
        return bool(row["current"]) and row["epistemic_status"] == "current"

    def memories(self, user_id: str) -> list[Memory]:
        return [
            self.memory(r[0])
            for r in self.db.execute(
                "SELECT id FROM memories WHERE user_id=? AND current=1", (user_id,)
            )
        ]

    def memory_history(self, memory_id: str, *, user_id: str) -> list[dict[str, Any]]:
        memory = self.memory(memory_id)
        if memory.user_id != user_id:
            raise KeyError(memory_id)
        return [
            {
                "event_type": row["event_type"],
                "payload": load(row["payload_json"], {}),
                "created_at": row["created_at"],
            }
            for row in self.db.execute(
                "SELECT event_type,payload_json,created_at FROM memory_events "
                "WHERE memory_id=? ORDER BY rowid",
                (memory_id,),
            )
        ]

    def memory_source_views(self, memory_id: str, *, user_id: str) -> list[dict[str, Any]]:
        memory = self.memory(memory_id)
        if memory.user_id != user_id:
            raise KeyError(memory_id)
        rows = self.db.execute(
            "SELECT o.id,o.conversation_id,o.turn_id,o.observed_at,o.timezone,o.role,o.excerpt "
            "FROM observations o JOIN memory_sources s ON s.source_id=o.id "
            "WHERE s.memory_id=? AND o.user_id=? ORDER BY o.observed_at,o.id",
            (memory_id, user_id),
        )
        return [dict(row) for row in rows]

    def traces_for_subject(self, subject_id: str, *, user_id: str) -> list[dict[str, Any]]:
        return [
            {
                "id": row["id"],
                "subject_type": row["subject_type"],
                "subject_id": row["subject_id"],
                "reason_codes": load(row["reason_codes_json"], []),
                "input_summary": row["input_summary"],
                "created_at": row["created_at"],
            }
            for row in self.db.execute(
                "SELECT * FROM decision_traces WHERE subject_id=? AND user_id=? ORDER BY rowid",
                (subject_id, user_id),
            )
        ]

    def revise_memory(
        self,
        memory_id: str,
        *,
        expected_revision: int,
        event_type: str,
        now: str,
        summary: str | None = None,
        time: dict[str, Any] | None = None,
        epistemic_status: str | None = None,
        current: bool | None = None,
        source_id: str | None = None,
    ) -> Memory:
        memory = self.memory(memory_id)
        if memory.revision != expected_revision:
            raise ValueError("revision_conflict")
        self.db.execute(
            "UPDATE memories SET summary=?, time_json=?, epistemic_status=?, current=?, revision=revision+1 WHERE id=?",
            (
                summary or memory.summary,
                dump(time if time is not None else memory.time),
                epistemic_status or memory.epistemic_status,
                int(current if current is not None else True),
                memory_id,
            ),
        )
        if source_id:
            self.db.execute(
                "INSERT OR IGNORE INTO memory_sources(memory_id,source_id) VALUES (?,?)",
                (memory_id, source_id),
            )
        self.db.execute(
            "INSERT INTO memory_events(memory_id,event_type,payload_json,created_at) VALUES (?,?,?,?)",
            (memory_id, event_type, dump({"source_id": source_id}), now),
        )
        return self.memory(memory_id)

    def canonicalize_entity(
        self,
        *,
        entity_id: str,
        user_id: str,
        canonical_name: str,
        aliases: tuple[str, ...],
        source_id: str,
    ) -> dict[str, Any]:
        self.ensure_user(user_id)
        existing = self.db.execute(
            "SELECT id FROM entities WHERE user_id=? AND canonical_name=?",
            (user_id, canonical_name),
        ).fetchone()
        resolved_id = existing["id"] if existing else entity_id
        self.db.execute(
            "INSERT OR IGNORE INTO entities(id,user_id,canonical_name) VALUES (?,?,?)",
            (resolved_id, user_id, canonical_name),
        )
        if existing:
            self.db.execute(
                "UPDATE entities SET revision=revision+1 WHERE id=?", (resolved_id,)
            )
        for alias in aliases:
            self.db.execute(
                "INSERT OR REPLACE INTO entity_aliases(entity_id,alias,status,source_id) VALUES (?,?,?,?)",
                (resolved_id, alias, "retracted", source_id),
            )
        return {
            "entity_id": resolved_id,
            "canonical_name": canonical_name,
            "aliases": list(aliases),
            "revision": self.db.execute(
                "SELECT revision FROM entities WHERE id=?", (resolved_id,)
            ).fetchone()[0],
        }

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
        self.ensure_user(user_id)
        current = self.db.execute(
            "SELECT * FROM lived_contexts WHERE user_id=?", (user_id,)
        ).fetchone()
        revision = (current["revision"] + 1) if current else 1
        self.db.execute(
            """
            INSERT INTO lived_contexts(user_id,context,status,observed_at,timezone,source_id,revision)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
              context=excluded.context, status=excluded.status,
              observed_at=excluded.observed_at, timezone=excluded.timezone,
              source_id=excluded.source_id, revision=excluded.revision
            """,
            (user_id, context, status, observed_at, timezone, source_id, revision),
        )
        return {
            "user_id": user_id,
            "context": context,
            "status": status,
            "observed_at": observed_at,
            "timezone": timezone,
            "source_id": source_id,
            "revision": revision,
        }

    def lived_context(self, user_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM lived_contexts WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def save_import_source(self, source: ImportSource) -> None:
        self.ensure_user(source.user_id)
        existing = self.db.execute(
            "SELECT user_id, kind, locator, authorization_scope, content_hash FROM import_sources WHERE id=?",
            (source.id,),
        ).fetchone()
        if existing and existing["user_id"] != source.user_id:
            raise ValueError("import_source_user_mismatch")
        if existing and tuple(existing) != (
            source.user_id, source.kind, source.locator,
            source.authorization_scope, source.content_hash,
        ):
            raise ValueError("import_source_conflict")
        self.db.execute(
            "INSERT OR IGNORE INTO import_sources VALUES (?,?,?,?,?,?,?)",
            (source.id, source.user_id, source.kind, source.locator,
             source.authorization_scope, source.content_hash, source.created_at),
        )

    def import_source(self, source_id: str) -> ImportSource:
        row = self.db.execute("SELECT * FROM import_sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise KeyError(source_id)
        return ImportSource(row["id"], row["user_id"], row["kind"], row["locator"],
                            row["authorization_scope"], row["content_hash"], row["created_at"])

    def save_import_job(self, job: ImportJob) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO import_jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
            (job.id, job.source_id, job.user_id, job.status, job.total_records,
             job.processed_records, dump(job.candidate_ids), job.started_at,
             job.finished_at, job.error),
        )

    def import_job(self, job_id: str) -> ImportJob:
        row = self.db.execute("SELECT * FROM import_jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError(job_id)
        return ImportJob(row["id"], row["source_id"], row["user_id"], row["status"],
                         row["total_records"], row["processed_records"],
                         tuple(load(row["candidate_ids_json"], [])), row["started_at"],
                         row["finished_at"], row["error"])

    def import_record(self, job_id: str, source_record_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT * FROM import_records WHERE job_id=? AND source_record_id=?",
            (job_id, source_record_id),
        ).fetchone()
        return dict(row) if row else None

    def import_record_for_source(self, source_id: str, source_record_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            """SELECT r.* FROM import_records r JOIN import_jobs j ON j.id=r.job_id
               WHERE j.source_id=? AND r.source_record_id=? ORDER BY r.job_id LIMIT 1""",
            (source_id, source_record_id),
        ).fetchone()
        return dict(row) if row else None

    def save_import_record(self, job_id: str, source_record_id: str, observation_id: str,
                           candidate_id: str, status: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO import_records VALUES (?,?,?,?,?)",
            (job_id, source_record_id, observation_id, candidate_id, status),
        )

    def save_bootstrap_snapshot(self, snapshot: BootstrapSnapshot) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO bootstrap_snapshots VALUES (?,?,?,?,?,?,?)",
            (snapshot.id, snapshot.user_id, snapshot.mode, dump(snapshot.source_ids),
             dump(snapshot.job_ids), dump(snapshot.candidate_ids), snapshot.established_at),
        )

    def bootstrap_snapshot(self, snapshot_id: str) -> BootstrapSnapshot:
        row = self.db.execute("SELECT * FROM bootstrap_snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if not row:
            raise KeyError(snapshot_id)
        return BootstrapSnapshot(row["id"], row["user_id"], row["mode"],
                                 tuple(load(row["source_ids_json"], [])),
                                 tuple(load(row["job_ids_json"], [])),
                                 tuple(load(row["candidate_ids_json"], [])), row["established_at"])

    def record_adapter_event(
        self,
        *,
        event_id: str,
        user_id: str,
        conversation_id: str,
        turn_id: str,
        event_type: str,
        occurred_at: str,
        payload: dict[str, Any],
    ) -> bool:
        self.ensure_user(user_id)
        cursor = self.db.execute(
            "INSERT OR IGNORE INTO adapter_events VALUES (?,?,?,?,?,?,?)",
            (event_id, user_id, conversation_id, turn_id, event_type, occurred_at, dump(payload)),
        )
        return cursor.rowcount == 1

    def adapter_events(self, user_id: str) -> list[dict[str, Any]]:
        return [
            {**dict(row), "payload": load(row["payload_json"], {})}
            for row in self.db.execute(
                "SELECT * FROM adapter_events WHERE user_id=? ORDER BY rowid", (user_id,)
            )
        ]

    def conversation_summaries(self, user_id: str) -> list[dict[str, Any]]:
        conversation_ids = [
            row[0]
            for row in self.db.execute(
                "SELECT id FROM conversations WHERE user_id=? "
                "UNION SELECT conversation_id FROM adapter_events WHERE user_id=?",
                (user_id, user_id),
            )
        ]
        result: list[dict[str, Any]] = []
        for conversation_id in conversation_ids:
            observation_times = [
                row[0]
                for row in self.db.execute(
                    "SELECT observed_at FROM observations WHERE user_id=? AND conversation_id=?",
                    (user_id, conversation_id),
                )
            ]
            adapter_times = [
                row[0]
                for row in self.db.execute(
                    "SELECT occurred_at FROM adapter_events WHERE user_id=? AND conversation_id=?",
                    (user_id, conversation_id),
                )
            ]
            activity_times = [*observation_times, *adapter_times]
            activity_times.sort(key=datetime.fromisoformat)
            observation_count = len(observation_times)
            adapter_event_count = len(adapter_times)
            candidate_count, pending_candidate_count = self.db.execute(
                "SELECT COUNT(*),SUM(CASE WHEN c.status='pending' THEN 1 ELSE 0 END) "
                "FROM candidates c JOIN observations o ON o.id=c.observation_id "
                "WHERE c.user_id=? AND o.user_id=? AND o.conversation_id=?",
                (user_id, user_id, conversation_id),
            ).fetchone()
            memory_count = self.db.execute(
                "SELECT COUNT(DISTINCT m.id) FROM memories m "
                "JOIN memory_sources ms ON ms.memory_id=m.id "
                "JOIN observations o ON o.id=ms.source_id "
                "WHERE m.user_id=? AND o.user_id=? AND o.conversation_id=?",
                (user_id, user_id, conversation_id),
            ).fetchone()[0]
            if observation_count and adapter_event_count:
                source_kind = "mixed"
            elif adapter_event_count:
                source_kind = "adapter"
            elif conversation_id.startswith("import:"):
                source_kind = "import"
            else:
                source_kind = "observation"
            result.append(
                {
                    "conversation_id": conversation_id,
                    "source_kind": source_kind,
                    "first_activity_at": activity_times[0] if activity_times else None,
                    "last_activity_at": activity_times[-1] if activity_times else None,
                    "observation_count": observation_count,
                    "candidate_count": candidate_count,
                    "pending_candidate_count": pending_candidate_count or 0,
                    "memory_count": memory_count,
                    "adapter_event_count": adapter_event_count,
                }
            )
        result.sort(
            key=lambda item: (
                datetime.fromisoformat(item["last_activity_at"]).timestamp()
                if item["last_activity_at"]
                else float("-inf"),
                item["conversation_id"],
            ),
            reverse=True,
        )
        return result

    def conversation_detail(self, conversation_id: str, *, user_id: str) -> dict[str, Any]:
        summaries = {
            item["conversation_id"]: item for item in self.conversation_summaries(user_id)
        }
        if conversation_id not in summaries:
            raise KeyError(conversation_id)
        observations = []
        for row in self.db.execute(
            "SELECT id,turn_id,observed_at,timezone,role,excerpt,speech_act "
            "FROM observations WHERE user_id=? AND conversation_id=? "
            "ORDER BY observed_at,id",
            (user_id, conversation_id),
        ):
            observation = dict(row)
            observation["candidates"] = [
                {
                    "id": candidate["id"],
                    "kind": candidate["kind"],
                    "summary": candidate["summary"],
                    "status": candidate["status"],
                    "sensitivity": candidate["sensitivity"],
                }
                for candidate in self.db.execute(
                    "SELECT id,kind,summary,status,sensitivity FROM candidates "
                    "WHERE user_id=? AND observation_id=? ORDER BY rowid",
                    (user_id, row["id"]),
                )
            ]
            observation["memories"] = [
                {
                    "id": memory["id"],
                    "kind": memory["kind"],
                    "summary": memory["summary"],
                    "epistemic_status": memory["epistemic_status"],
                    "current": bool(memory["current"]),
                    "revision": memory["revision"],
                }
                for memory in self.db.execute(
                    "SELECT m.id,m.kind,m.summary,m.epistemic_status,m.current,m.revision "
                    "FROM memories m JOIN memory_sources ms ON ms.memory_id=m.id "
                    "WHERE m.user_id=? AND ms.source_id=? ORDER BY m.id",
                    (user_id, row["id"]),
                )
            ]
            observations.append(observation)
        adapter_events = [
            {
                "turn_id": row["turn_id"],
                "event_type": row["event_type"],
                "occurred_at": row["occurred_at"],
            }
            for row in self.db.execute(
                "SELECT turn_id,event_type,occurred_at FROM adapter_events "
                "WHERE user_id=? AND conversation_id=? ORDER BY occurred_at,rowid",
                (user_id, conversation_id),
            )
        ]
        return {
            **summaries[conversation_id],
            "observations": observations,
            "adapter_events": adapter_events,
        }

    def user_versions(self, user_id: str) -> tuple[int, int]:
        self.ensure_user(user_id)
        r = self.db.execute(
            "SELECT revocation_epoch,package_version FROM users WHERE id=?", (user_id,)
        ).fetchone()
        return r[0], r[1]

    def bump_user(self, user_id: str, revoke: bool = False) -> tuple[int, int]:
        self.ensure_user(user_id)
        if revoke:
            self.db.execute(
                "UPDATE users SET revocation_epoch=revocation_epoch+1, package_version=package_version+1 WHERE id=?",
                (user_id,),
            )
        else:
            self.db.execute(
                "UPDATE users SET package_version=package_version+1 WHERE id=?", (user_id,)
            )
        return self.user_versions(user_id)

    def trace(
        self,
        trace_id: str,
        subject_type: str,
        subject_id: str,
        reasons: tuple[str, ...],
        summary: str,
        now: str,
    ) -> None:
        user_id = self._trace_user_id(subject_type, subject_id)
        self.db.execute(
            "INSERT INTO decision_traces(id,subject_type,subject_id,reason_codes_json,input_summary,created_at,user_id) VALUES (?,?,?,?,?,?,?)",
            (trace_id, subject_type, subject_id, dump(reasons), summary, now, user_id),
        )

    def _trace_user_id(self, subject_type: str, subject_id: str) -> str | None:
        lookups = {
            "candidate": ("candidates", "id"),
            "decision": ("candidates", "id"),
            "recall": ("recall_packages", "id"),
            "entity": ("entities", "id"),
            "lived_context": ("users", "id"),
        }
        if subject_type == "governance":
            row = self.db.execute("SELECT user_id FROM memories WHERE id=?", (subject_id,)).fetchone()
            if row:
                return row[0]
            return subject_id if self.db.execute("SELECT 1 FROM users WHERE id=?", (subject_id,)).fetchone() else None
        lookup = lookups.get(subject_type)
        if not lookup:
            return None
        table, key = lookup
        column = "id" if table == "users" else "user_id"
        row = self.db.execute(
            f"SELECT {column} FROM {table} WHERE {key}=?", (subject_id,)
        ).fetchone()
        return row[0] if row else None

    def get_trace(self, trace_id: str, *, user_id: str) -> dict[str, Any]:
        r = self.db.execute("SELECT * FROM decision_traces WHERE id=?", (trace_id,)).fetchone()
        if not r:
            raise KeyError(trace_id)
        if r["user_id"] != user_id:
            raise KeyError(trace_id)
        return {
            "id": r["id"],
            "subject_type": r["subject_type"],
            "subject_id": r["subject_id"],
            "reason_codes": load(r["reason_codes_json"], []),
            "input_summary": r["input_summary"],
            "created_at": r["created_at"],
        }

    def save_package(self, p: RecallPackage) -> None:
        self.db.execute(
            "INSERT INTO recall_packages VALUES (?,?,?,?,?,?,?,?)",
            (
                p.id,
                p.user_id,
                p.conversation_id,
                p.purpose,
                p.issued_at,
                p.expires_at,
                p.package_version,
                p.revocation_epoch,
            ),
        )
        self.db.executemany(
            "INSERT INTO recall_items VALUES (?,?,?,?,?,?,?)",
            [
                (
                    p.id,
                    i.memory_id,
                    i.category,
                    i.summary,
                    i.guidance,
                    dump(i.source_ids),
                    dump(i.reason_codes),
                )
                for i in p.items
            ],
        )

    def package(self, pid: str) -> RecallPackage:
        r = self.db.execute("SELECT * FROM recall_packages WHERE id=?", (pid,)).fetchone()
        if not r:
            raise KeyError(pid)
        items = tuple(
            RecallItem(
                x["memory_id"],
                x["category"],
                x["summary"],
                x["guidance"],
                tuple(load(x["source_ids_json"], [])),
                tuple(load(x["reason_codes_json"], [])),
            )
            for x in self.db.execute("SELECT * FROM recall_items WHERE package_id=?", (pid,))
        )
        return RecallPackage(
            r["id"],
            r["user_id"],
            r["conversation_id"],
            r["purpose"],
            r["issued_at"],
            r["expires_at"],
            r["package_version"],
            r["revocation_epoch"],
            items,
        )
