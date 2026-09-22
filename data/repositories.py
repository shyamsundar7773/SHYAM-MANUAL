"""Small, explicit repositories for database-driven content."""

from pathlib import Path
import json
import sqlite3
from typing import Any
import re
import uuid

from data.database import DatabaseError, get_connection


class ContentRepository:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = database_path

    def get_job_summary(self, job_id: int | None = None) -> dict[str, Any] | None:
        if job_id is None:
            return None
        row = self.get_job(job_id)
        if row is None:
            return None
        return dict(row)

    def list_categories(self) -> list[sqlite3.Row]:
        try:
            with get_connection(self.database_path) as connection:
                return list(connection.execute("SELECT * FROM categories ORDER BY sort_order, name"))
        except DatabaseError:
            raise

    @staticmethod
    def _text(value: Any, field: str, required: bool = False) -> str | None:
        if value is None:
            if required:
                raise ValueError(f"{field} is required")
            return None
        result = str(value).strip()
        if required and not result:
            raise ValueError(f"{field} is required")
        return result or None

    @staticmethod
    def _id(value: Any, field: str, required: bool = False) -> int | None:
        if value in (None, ""):
            if required:
                raise ValueError(f"{field} is required")
            return None
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be an integer") from exc
        if result <= 0:
            raise ValueError(f"{field} must be positive")
        return result

    @staticmethod
    def _slug(value: Any, fallback: str) -> str:
        raw = str(value or fallback).strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
        if not slug:
            raise ValueError("name must contain letters or numbers")
        return slug

    @staticmethod
    def _ensure_reference(connection: sqlite3.Connection, table: str, item_id: int | None, field: str) -> None:
        if item_id is not None and connection.execute(f"SELECT 1 FROM {table} WHERE id=?", (item_id,)).fetchone() is None:
            raise ValueError(f"{field} does not exist")

    def list_modules(self, category_id: int | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if category_id is None:
                return list(connection.execute("SELECT * FROM modules ORDER BY sort_order, name"))
            return list(connection.execute(
                "SELECT * FROM modules WHERE category_id = ? ORDER BY sort_order, name",
                (self._id(category_id, "category_id", True),),
            ))

    def list_topics(self, module_id: int | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if module_id is None:
                return list(connection.execute("SELECT * FROM topics ORDER BY sort_order, name"))
            return list(connection.execute(
                "SELECT * FROM topics WHERE module_id = ? ORDER BY sort_order, name",
                (self._id(module_id, "module_id", True),),
            ))

    def list_topics_for_category(self, category_id: int) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            return list(connection.execute(
                """SELECT t.* FROM topics t
                   JOIN modules m ON m.id=t.module_id
                   WHERE m.category_id=?
                   ORDER BY t.sort_order, t.name""",
                (self._id(category_id, "category_id", True),),
            ))

    def list_interview_sessions(self, status: str | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if status:
                return list(connection.execute(
                    "SELECT * FROM interview_sessions WHERE status = ? ORDER BY updated_at DESC, id DESC",
                    (status,),
                ))
            return list(connection.execute("SELECT * FROM interview_sessions ORDER BY updated_at DESC, id DESC"))

    def get_interview_session(self, session_id: int | str | None = None, *, session_key: str | None = None) -> sqlite3.Row | None:
        if session_id is None and session_key is None:
            return None
        with get_connection(self.database_path) as connection:
            if isinstance(session_id, str) and not session_id.isdigit():
                session_key = session_id
                session_id = None
            if session_key is not None:
                return connection.execute(
                    "SELECT * FROM interview_sessions WHERE session_key = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
                    (str(session_key),),
                ).fetchone()
            if session_id is None:
                return None
            return connection.execute(
                "SELECT * FROM interview_sessions WHERE id = ?",
                (self._id(session_id, "session_id", True),),
            ).fetchone()

    def save_interview_evaluation(self, session_id: int | str, evaluation: dict[str, Any]) -> sqlite3.Row:
        return self.create_interview_evaluation(session_id, evaluation)

    def create_interview_evaluation(self, session_id: int | str, evaluation: dict[str, Any]) -> sqlite3.Row:
        target_session = self.get_interview_session(session_id)
        if target_session is None:
            raise ValueError("interview session not found")
        session_id_int = int(target_session["id"])
        payload = evaluation or {}
        if not isinstance(payload, dict):
            raise ValueError("evaluation must be a dictionary")
        with get_connection(self.database_path) as connection:
            existing = connection.execute(
                "SELECT * FROM interview_evaluations WHERE session_id = ?",
                (session_id_int,),
            ).fetchone()
            summary = self._text(payload.get("overall_summary") or payload.get("summary"), "overall_summary") or "Structured review complete."
            strengths = payload.get("strengths") or []
            weaknesses = payload.get("weaknesses") or []
            observations = payload.get("key_observations") or []
            next_steps = payload.get("recommended_next_steps") or []
            payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO interview_evaluations (
                        session_id, overall_summary, strengths, weaknesses,
                        key_observations, recommended_next_steps, evaluation_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id_int,
                        summary,
                        json.dumps(strengths, ensure_ascii=False),
                        json.dumps(weaknesses, ensure_ascii=False),
                        json.dumps(observations, ensure_ascii=False),
                        json.dumps(next_steps, ensure_ascii=False),
                        payload_json,
                    ),
                )
                evaluation_id = int(cursor.lastrowid)
            else:
                evaluation_id = int(existing["id"])
                connection.execute(
                    """
                    UPDATE interview_evaluations SET
                        overall_summary = ?, strengths = ?, weaknesses = ?,
                        key_observations = ?, recommended_next_steps = ?, evaluation_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        summary,
                        json.dumps(strengths, ensure_ascii=False),
                        json.dumps(weaknesses, ensure_ascii=False),
                        json.dumps(observations, ensure_ascii=False),
                        json.dumps(next_steps, ensure_ascii=False),
                        payload_json,
                        evaluation_id,
                    ),
                )
            connection.execute("DELETE FROM interview_weaknesses WHERE session_id = ?", (session_id_int,))
            for weakness in payload.get("question_evaluations") or []:
                if not isinstance(weakness, dict):
                    continue
                quality = weakness.get("answer_completeness") or ""
                if quality not in {"limited", "moderate", "strong"}:
                    continue
                if quality in {"limited", "moderate"}:
                    weakness_name = self._weakness_name(weakness.get("question") or "Answer quality")
                    connection.execute(
                        """
                        INSERT INTO interview_weaknesses (
                            evaluation_id, session_id, name, description, evidence,
                            question_id, confidence, severity, category, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(session_id, name) DO UPDATE SET
                            evaluation_id=excluded.evaluation_id,
                            description=excluded.description,
                            evidence=excluded.evidence,
                            question_id=excluded.question_id,
                            confidence=excluded.confidence,
                            severity=excluded.severity,
                            category=excluded.category,
                            source=excluded.source
                        """,
                        (
                            evaluation_id,
                            session_id_int,
                            weakness_name,
                            weakness.get("improvement_guidance") or "Need more detail and structure.",
                            weakness.get("answer") or "No answer provided.",
                            self._id(weakness.get("question_id"), "question_id"),
                            "medium" if quality == "moderate" else "high",
                            "medium" if quality == "moderate" else "high",
                            "general",
                            weakness.get("source") or "structured-fallback",
                        ),
                    )
            connection.execute("DELETE FROM interview_recommendations WHERE session_id = ?", (session_id_int,))
            recommendations = list(payload.get("recommendations") or [])
            if not recommendations:
                for index, weakness in enumerate(payload.get("question_evaluations") or [], 1):
                    if not isinstance(weakness, dict):
                        continue
                    quality = weakness.get("answer_completeness") or ""
                    if quality not in {"limited", "moderate"}:
                        continue
                    name = self._weakness_name(weakness.get("question") or "Answer quality")
                    recommendations.append({
                        "weakness": name,
                        "reason": weakness.get("improvement_guidance") or "Targeted practice is recommended.",
                        "recommended_question": weakness.get("question") or "Review the relevant study notes and practice a short answer.",
                        "practice_objective": f"Strengthen {name.lower()} with a focused practice set.",
                        "priority": 2 if quality == "moderate" else 3,
                        "source": weakness.get("source") or "structured-fallback",
                    })
            for index, recommendation in enumerate(recommendations, 1):
                if not isinstance(recommendation, dict):
                    continue
                connection.execute(
                    """
                    INSERT INTO interview_recommendations (
                        evaluation_id, session_id, weakness, reason, recommended_question,
                        practice_objective, priority, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, weakness) DO UPDATE SET
                        evaluation_id=excluded.evaluation_id,
                        reason=excluded.reason,
                        recommended_question=excluded.recommended_question,
                        practice_objective=excluded.practice_objective,
                        priority=excluded.priority,
                        source=excluded.source
                    """,
                    (
                        evaluation_id,
                        session_id_int,
                        recommendation.get("weakness") or f"Practice area {index}",
                        recommendation.get("reason") or recommendation.get("practice_objective") or "Targeted practice is recommended.",
                        recommendation.get("recommended_question") or "Review the relevant study notes and practice a short answer.",
                        recommendation.get("practice_objective") or "Strengthen the weak area with a focused practice set.",
                        int(recommendation.get("priority") or index),
                        recommendation.get("source") or "structured-fallback",
                    ),
                )
            connection.execute("DELETE FROM mission_adaptations WHERE session_id = ?", (session_id_int,))
            for weakness in payload.get("question_evaluations") or []:
                if not isinstance(weakness, dict):
                    continue
                quality = weakness.get("answer_completeness") or ""
                if quality not in {"limited", "moderate"}:
                    continue
                name = self._weakness_name(weakness.get("question") or "Answer quality")
                connection.execute(
                    """
                    INSERT INTO mission_adaptations (session_id, weakness_name, priority, reason, topic_name, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(session_id, weakness_name) DO UPDATE SET
                        priority=excluded.priority,
                        reason=excluded.reason,
                        topic_name=excluded.topic_name,
                        status=excluded.status
                    """,
                    (
                        session_id_int,
                        name,
                        "high" if quality == "limited" else "medium",
                        "Priority increased because this topic was identified as a weakness in the latest interview.",
                        name,
                        "active",
                    ),
                )
        return self.get_interview_evaluation(session_id_int)

    def get_interview_evaluation(self, session_id: int | str) -> sqlite3.Row | None:
        session = self.get_interview_session(session_id)
        if session is None:
            return None
        with get_connection(self.database_path) as connection:
            return connection.execute(
                "SELECT * FROM interview_evaluations WHERE session_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (int(session["id"]),),
            ).fetchone()

    def list_interview_evaluations(self, session_id: int | str | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if session_id is None:
                return list(connection.execute("SELECT * FROM interview_evaluations ORDER BY created_at DESC, id DESC"))
            session = self.get_interview_session(session_id)
            if session is None:
                return []
            return list(connection.execute(
                "SELECT * FROM interview_evaluations WHERE session_id = ? ORDER BY created_at DESC, id DESC",
                (int(session["id"]),),
            ))

    def save_weakness(self, session_id: int | str, weakness: dict[str, Any], *, evaluation_id: int | None = None) -> sqlite3.Row:
        session = self.get_interview_session(session_id)
        if session is None:
            raise ValueError("interview session not found")
        session_id_int = int(session["id"])
        if evaluation_id is None:
            evaluation = self.get_interview_evaluation(session_id_int)
            evaluation_id = int(evaluation["id"]) if evaluation else None
        record = {**weakness}
        record.setdefault("name", "Answer quality")
        record.setdefault("description", "Needs more structure and clearer examples.")
        record.setdefault("source", "structured-fallback")
        record.setdefault("category", "general")
        record.setdefault("confidence", "medium")
        record.setdefault("severity", "medium")
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO interview_weaknesses (
                    evaluation_id, session_id, name, description, evidence,
                    question_id, confidence, severity, category, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, name) DO UPDATE SET
                    evaluation_id=excluded.evaluation_id,
                    description=excluded.description,
                    evidence=excluded.evidence,
                    question_id=excluded.question_id,
                    confidence=excluded.confidence,
                    severity=excluded.severity,
                    category=excluded.category,
                    source=excluded.source
                """,
                (
                    evaluation_id,
                    session_id_int,
                    self._text(record.get("name"), "name", True),
                    self._text(record.get("description"), "description"),
                    self._text(record.get("evidence"), "evidence"),
                    self._id(record.get("question_id"), "question_id"),
                    self._text(record.get("confidence"), "confidence") or "medium",
                    self._text(record.get("severity"), "severity") or "medium",
                    self._text(record.get("category"), "category") or "general",
                    self._text(record.get("source"), "source") or "structured-fallback",
                ),
            )
            connection.execute(
                """
                INSERT INTO weakness_records (session_id, evaluation_id, name, category, severity, evidence, reason, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, name) DO UPDATE SET
                    evaluation_id=excluded.evaluation_id,
                    category=excluded.category,
                    severity=excluded.severity,
                    evidence=excluded.evidence,
                    reason=excluded.reason,
                    status=excluded.status,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    session_id_int,
                    evaluation_id,
                    self._text(record.get("name"), "name", True),
                    self._text(record.get("category"), "category") or "general",
                    self._text(record.get("severity"), "severity") or "medium",
                    self._text(record.get("evidence"), "evidence") or self._text(record.get("description"), "description") or "Interview evidence recorded.",
                    self._text(record.get("description"), "description") or "Needs targeted practice.",
                    "identified",
                ),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO weakness_history (weakness_name, session_id, status, evidence)
                VALUES (?, ?, 'identified', ?)
                """,
                (
                    self._text(record.get("name"), "name", True),
                    session_id_int,
                    self._text(record.get("evidence"), "evidence") or self._text(record.get("description"), "description") or "Interview evidence recorded.",
                ),
            )
            row = connection.execute(
                "SELECT * FROM interview_weaknesses WHERE session_id = ? AND name = ? ORDER BY id DESC LIMIT 1",
                (session_id_int, self._text(record.get("name"), "name", True)),
            ).fetchone()
            if row is None:
                raise ValueError("weakness could not be saved")
            return row

    def list_weaknesses(self, session_id: int | str | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if session_id is None:
                return list(connection.execute("SELECT * FROM interview_weaknesses ORDER BY created_at DESC, id DESC"))
            session = self.get_interview_session(session_id)
            if session is None:
                return []
            return list(connection.execute(
                "SELECT * FROM interview_weaknesses WHERE session_id = ? ORDER BY created_at DESC, id DESC",
                (int(session["id"]),),
            ))

    def save_recommendation(self, session_id: int | str, recommendation: dict[str, Any], *, evaluation_id: int | None = None) -> sqlite3.Row:
        session = self.get_interview_session(session_id)
        if session is None:
            raise ValueError("interview session not found")
        session_id_int = int(session["id"])
        if evaluation_id is None:
            evaluation = self.get_interview_evaluation(session_id_int)
            evaluation_id = int(evaluation["id"]) if evaluation else None
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO interview_recommendations (
                    evaluation_id, session_id, weakness, reason, recommended_question,
                    practice_objective, priority, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, weakness) DO UPDATE SET
                    evaluation_id=excluded.evaluation_id,
                    reason=excluded.reason,
                    recommended_question=excluded.recommended_question,
                    practice_objective=excluded.practice_objective,
                    priority=excluded.priority,
                    source=excluded.source
                """,
                (
                    evaluation_id,
                    session_id_int,
                    self._text(recommendation.get("weakness"), "weakness", True),
                    self._text(recommendation.get("reason"), "reason") or "Practice this topic with a focused response.",
                    self._text(recommendation.get("recommended_question"), "recommended_question") or "Review the relevant notetaking and practice a concise response.",
                    self._text(recommendation.get("practice_objective"), "practice_objective") or "Strengthen the weak area with a focused practice session.",
                    max(1, int(recommendation.get("priority") or 1)),
                    self._text(recommendation.get("source"), "source") or "structured-fallback",
                ),
            )
            connection.execute(
                """
                INSERT INTO preparation_recommendations (session_id, weakness_name, title, recommendation, priority, action)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, weakness_name, title) DO UPDATE SET
                    recommendation=excluded.recommendation,
                    priority=excluded.priority,
                    action=excluded.action
                """,
                (
                    session_id_int,
                    self._text(recommendation.get("weakness"), "weakness", True),
                    self._text(recommendation.get("weakness"), "weakness", True),
                    self._text(recommendation.get("reason"), "reason") or self._text(recommendation.get("practice_objective"), "practice_objective") or "Practice this topic with a focused response.",
                    self._text(recommendation.get("priority"), "priority") or "important",
                    "Practice Now",
                ),
            )
            row = connection.execute(
                "SELECT * FROM interview_recommendations WHERE session_id = ? AND weakness = ? ORDER BY id DESC LIMIT 1",
                (session_id_int, self._text(recommendation.get("weakness"), "weakness", True)),
            ).fetchone()
            if row is None:
                raise ValueError("recommendation could not be saved")
            return row

    def list_recommendations(self, session_id: int | str | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if session_id is None:
                return list(connection.execute("SELECT * FROM interview_recommendations ORDER BY priority DESC, created_at DESC, id DESC"))
            session = self.get_interview_session(session_id)
            if session is None:
                return []
            return list(connection.execute(
                "SELECT * FROM interview_recommendations WHERE session_id = ? ORDER BY priority DESC, created_at DESC, id DESC",
                (int(session["id"]),),
            ))

    def list_preparation_recommendations(self, session_id: int | str | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if session_id is None:
                return list(connection.execute("SELECT * FROM preparation_recommendations ORDER BY created_at DESC, id DESC"))
            session = self.get_interview_session(session_id)
            if session is None:
                return []
            return list(connection.execute(
                "SELECT * FROM preparation_recommendations WHERE session_id = ? ORDER BY created_at DESC, id DESC",
                (int(session["id"]),),
            ))

    def save_mission_adaptation(self, values: dict[str, Any]) -> sqlite3.Row:
        session_id = self._id(values.get("session_id"), "session_id", True)
        session = self.get_interview_session(session_id)
        if session is None:
            raise ValueError("interview session not found")
        session_id_int = int(session["id"])
        weakness_name = self._text(values.get("weakness_name"), "weakness_name", True)
        priority = self._text(values.get("priority"), "priority") or "medium"
        reason = self._text(values.get("reason"), "reason") or "Priority increased because this topic was identified as a weakness."
        topic_name = self._text(values.get("topic_name"), "topic_name")
        status = self._text(values.get("status"), "status") or "active"
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO mission_adaptations (session_id, weakness_name, priority, reason, topic_name, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, weakness_name) DO UPDATE SET
                    priority=excluded.priority,
                    reason=excluded.reason,
                    topic_name=excluded.topic_name,
                    status=excluded.status
                """,
                (session_id_int, weakness_name, priority, reason, topic_name, status),
            )
            row = connection.execute(
                "SELECT * FROM mission_adaptations WHERE session_id = ? AND weakness_name = ? ORDER BY id DESC LIMIT 1",
                (session_id_int, weakness_name),
            ).fetchone()
            if row is None:
                raise ValueError("mission adaptation could not be saved")
            return row

    def list_mission_adaptations(self, session_id: int | str | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if session_id is None:
                return list(connection.execute("SELECT * FROM mission_adaptations ORDER BY created_at DESC, id DESC"))
            session = self.get_interview_session(session_id)
            if session is None:
                return []
            return list(connection.execute(
                "SELECT * FROM mission_adaptations WHERE session_id = ? ORDER BY created_at DESC, id DESC",
                (int(session["id"]),),
            ))

    def save_adaptive_mission(self, *args, **kwargs):
        return self.save_mission_adaptation(*args, **kwargs)

    def save_interview_relationship(self, interview_id: int | str, related_interview_id: int | str,
                                   relationship_type: str = "reinterview") -> int:
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO interview_relationships(interview_id, related_interview_id, relationship_type) VALUES (?, ?, ?)",
                (self._id(interview_id, "interview_id", True), self._id(related_interview_id, "related_interview_id", True), relationship_type),
            )
            return int(cursor.lastrowid) if cursor.lastrowid else int(connection.execute(
                "SELECT id FROM interview_relationships WHERE interview_id=? AND related_interview_id=? AND relationship_type=?",
                (self._id(interview_id, "interview_id", True), self._id(related_interview_id, "related_interview_id", True), relationship_type),
            ).fetchone()["id"])

    def list_interview_relationships(self, interview_id: int | str | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if interview_id is None:
                return list(connection.execute("SELECT * FROM interview_relationships ORDER BY created_at DESC, id DESC"))
            return list(connection.execute(
                "SELECT * FROM interview_relationships WHERE interview_id=? OR related_interview_id=? ORDER BY created_at DESC, id DESC",
                (self._id(interview_id, "interview_id", True), self._id(interview_id, "interview_id", True)),
            ))

    def set_job_readiness(self, job_id: int, area_name: str, status: str = "identified",
                          evidence: str | None = None) -> int:
        job_id_int = self._id(job_id, "job_id", True)
        with get_connection(self.database_path) as connection:
            if connection.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id_int,)).fetchone() is None:
                raise ValueError("job not found for readiness tracking")
            connection.execute(
                """
                INSERT INTO job_readiness(job_id, area_name, status, evidence)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(job_id, area_name) DO UPDATE SET
                    status=excluded.status,
                    evidence=excluded.evidence,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    job_id_int,
                    self._text(area_name, "area_name", True),
                    self._text(status, "status") or "identified",
                    self._text(evidence, "evidence"),
                ),
            )
            row = connection.execute("SELECT id FROM job_readiness WHERE job_id=? AND area_name=?", (job_id_int, self._text(area_name, "area_name", True))).fetchone()
            if row is None:
                raise ValueError("job readiness could not be saved")
            return int(row["id"])

    def list_job_readiness(self, job_id: int | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if job_id is None:
                return list(connection.execute("SELECT * FROM job_readiness ORDER BY updated_at DESC, id DESC"))
            return list(connection.execute(
                "SELECT * FROM job_readiness WHERE job_id=? ORDER BY updated_at DESC, id DESC",
                (self._id(job_id, "job_id", True),),
            ))

    def save_weakness_topic_mapping(self, weakness_name: str, *, category: str | None = None,
                                   category_slug: str | None = None, module_name: str | None = None,
                                   topic_name: str | None = None, reason: str | None = None,
                                   recommendation: str | None = None, severity: str = "medium") -> sqlite3.Row:
        weakness_key = self._text(weakness_name, "weakness_name", True)
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO weakness_topic_mappings (
                    weakness_name, category, category_slug, module_name, topic_name, reason, recommendation, severity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(weakness_name, category_slug, module_name, topic_name) DO UPDATE SET
                    category=excluded.category,
                    reason=excluded.reason,
                    recommendation=excluded.recommendation,
                    severity=excluded.severity
                """,
                (
                    weakness_key,
                    self._text(category, "category"),
                    self._text(category_slug, "category_slug") or self._slug(category or weakness_key, weakness_key),
                    self._text(module_name, "module_name"),
                    self._text(topic_name, "topic_name"),
                    self._text(reason, "reason") or "Keep this preparation area tied to an existing learning topic.",
                    self._text(recommendation, "recommendation") or "Review the relevant module and practice a concise answer.",
                    self._text(severity, "severity") or "medium",
                ),
            )
            row = connection.execute(
                "SELECT * FROM weakness_topic_mappings WHERE weakness_name = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (weakness_key,),
            ).fetchone()
            if row is None:
                raise ValueError("weakness topic mapping could not be saved")
            return row

    def list_weakness_topic_mappings(self, weakness_name: str | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if weakness_name is not None:
                return list(connection.execute(
                    "SELECT * FROM weakness_topic_mappings WHERE weakness_name = ? ORDER BY created_at DESC, id DESC",
                    (self._text(weakness_name, "weakness_name", True),),
                ))
            return list(connection.execute("SELECT * FROM weakness_topic_mappings ORDER BY created_at DESC, id DESC"))

    def resolve_weakness_topic(self, weakness_name: str, category: str | None = None) -> sqlite3.Row | None:
        if not weakness_name:
            return None
        normalized = str(weakness_name).strip()
        with get_connection(self.database_path) as connection:
            existing = connection.execute(
                "SELECT * FROM weakness_topic_mappings WHERE weakness_name = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (normalized,),
            ).fetchone()
            if existing is not None:
                return existing

        rules = {
            "window": ("sql-technical-notes", "Window Functions", "Window-function concept"),
            "join": ("sql-technical-notes", "Joins", "LEFT JOIN"),
            "cte": ("sql-technical-notes", "CTEs", "What is a CTE"),
            "aggregation": ("sql-technical-notes", "Aggregation", "GROUP BY"),
            "optimization": ("sql-technical-notes", "Indexes & Performance", "Query performance"),
            "project deep dive": ("project-practical", "Project Deep Dive", "Architecture explanation"),
            "project architecture": ("project-practical", "Project Architecture", "Architecture explanation"),
            "communication": ("non-technical-live-interview", "Communication", "Communication"),
            "unknown": ("non-technical-live-interview", "Handling Unknown Questions", "Handling Unknown Questions"),
            "behavioral": ("hr-screening", "Project Introduction", "Career story"),
        }
        lowered = normalized.lower()
        mapping = None
        for keyword, tuple_value in rules.items():
            if keyword in lowered:
                mapping = tuple_value
                break
        if mapping is None:
            return None
        category_slug, module_name, topic_name = mapping
        row = self.save_weakness_topic_mapping(
            normalized,
            category=category or "Prepared topic",
            category_slug=category_slug,
            module_name=module_name,
            topic_name=topic_name,
            reason=f"Mapped from weakness '{normalized}' to the existing curriculum.",
            recommendation=f"Review the '{module_name}' material and practice with the relevant question set.",
            severity="medium",
        )
        return row

    def record_progress_event(self, *, event_type: str = "preparation", title: str, description: str | None = None,
                             category: str | None = None, related_record_type: str | None = None,
                             related_record_id: int | None = None, status: str = "active") -> sqlite3.Row:
        title_text = self._text(title, "title", True)
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO progress_events (
                    event_type, title, description, category, related_record_type, related_record_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._text(event_type, "event_type") or "preparation",
                    title_text,
                    self._text(description, "description"),
                    self._text(category, "category"),
                    self._text(related_record_type, "related_record_type"),
                    self._id(related_record_id, "related_record_id") if related_record_id is not None else None,
                    self._text(status, "status") or "active",
                ),
            )
            row = connection.execute("SELECT * FROM progress_events WHERE id = ?", (int(cursor.lastrowid),)).fetchone()
            if row is None:
                raise ValueError("progress event could not be created")
            return row

    def list_progress_events(self, *, limit: int = 20, category: str | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if category is not None:
                return list(connection.execute(
                    "SELECT * FROM progress_events WHERE category = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                    (self._text(category, "category", True), max(1, int(limit))),
                ))
            return list(connection.execute(
                "SELECT * FROM progress_events ORDER BY created_at DESC, id DESC LIMIT ?",
                (max(1, int(limit)),),
            ))

    def get_progress_summary(self) -> dict[str, int | str]:
        with get_connection(self.database_path) as connection:
            counts = {
                "events": int(connection.execute("SELECT COUNT(*) FROM progress_events").fetchone()[0]),
                "job_readiness": int(connection.execute("SELECT COUNT(*) FROM job_readiness").fetchone()[0]),
                "weaknesses": int(connection.execute("SELECT COUNT(*) FROM interview_weaknesses").fetchone()[0]),
                "missions": int(connection.execute("SELECT COUNT(*) FROM mission_adaptations").fetchone()[0]),
                "applications": int(connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0]),
            }
            return counts

    def _weakness_name(self, question: str) -> str:
        lowered = (question or "").lower()
        if "join" in lowered:
            return "SQL JOIN reasoning"
        if "window" in lowered:
            return "Window Function understanding"
        if "project" in lowered or "architecture" in lowered:
            return "Explaining project architecture"
        if "behavior" in lowered or "story" in lowered or "describe" in lowered:
            return "Structured behavioral response"
        if "sql" in lowered or "query" in lowered:
            return "Query reasoning"
        return "Answer completeness"

    def create_interview_session(self, values: dict[str, Any]) -> sqlite3.Row:
        role = self._text(values.get("role"), "role", True)
        interview_type = self._text(values.get("interview_type"), "interview_type", True)
        difficulty = self._text(values.get("difficulty"), "difficulty", True)
        selected_topics = values.get("selected_topics") or values.get("topics") or []
        if isinstance(selected_topics, str):
            topic_text = selected_topics
        else:
            topic_text = ", ".join(str(item).strip() for item in selected_topics if str(item).strip())
        question_count = max(1, int(values.get("question_count", values.get("question_count", 5) or 5)))
        status = self._text(values.get("status"), "status") or "not_started"
        current_question = max(0, int(values.get("current_question", 0) or 0))
        completed_questions = max(0, int(values.get("completed_questions", 0) or 0))
        metadata_json = values.get("metadata_json") or values.get("metadata") or {}
        if not isinstance(metadata_json, str):
            metadata_json = json.dumps(metadata_json, ensure_ascii=False)
        mode = self._text(values.get("mode"), "mode")
        try:
            metadata_dict = json.loads(metadata_json) if isinstance(metadata_json, str) else {}
        except (TypeError, ValueError):
            metadata_dict = {}
        if isinstance(metadata_dict, dict):
            if not mode:
                mode = self._text(metadata_dict.get("mode"), "mode") or "Structured Interview"
            metadata_dict.setdefault("mode", mode)
            metadata_dict["voice_mode"] = bool(values.get("voice_mode", metadata_dict.get("voice_mode", False)))
            metadata_json = json.dumps(metadata_dict, ensure_ascii=False)
        elif not mode:
            mode = "Structured Interview"
        job_id = self._id(values.get("job_id"), "job_id")
        profile_id = self._id(values.get("candidate_profile_id"), "candidate_profile_id")
        resume_document_id = self._id(values.get("resume_document_id"), "resume_document_id")
        resume_version_id = self._id(values.get("resume_version_id"), "resume_version_id")
        application_id = self._id(values.get("application_id"), "application_id")
        with get_connection(self.database_path) as connection:
            if job_id is not None:
                self._ensure_reference(connection, "jobs", job_id, "job_id")
            if profile_id is not None:
                self._ensure_reference(connection, "candidate_profiles", profile_id, "candidate_profile_id")
            if resume_document_id is not None:
                self._ensure_reference(connection, "resume_documents", resume_document_id, "resume_document_id")
            if resume_version_id is not None:
                self._ensure_reference(connection, "resume_versions", resume_version_id, "resume_version_id")
            if application_id is not None:
                self._ensure_reference(connection, "applications", application_id, "application_id")
            session_key = self._text(values.get("session_key"), "session_key") or uuid.uuid4().hex
            cursor = connection.execute(
                """
                INSERT INTO interview_sessions (
                    session_key, role, interview_type, difficulty, selected_topics,
                    question_count, status, current_question, completed_questions,
                    started_at, ended_at, candidate_profile_id, job_id,
                    resume_document_id, resume_version_id, application_id,
                    mode, voice_mode, voice_provider, tts_provider,
                    session_context_json, voice_config_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_key, role, interview_type, difficulty, topic_text,
                    question_count, status, current_question, completed_questions,
                    self._text(values.get("started_at"), "started_at"),
                    self._text(values.get("ended_at"), "ended_at"),
                    profile_id, job_id,
                    resume_document_id, resume_version_id, application_id,
                    mode,
                    int(bool(values.get("voice_mode", False))),
                    self._text(values.get("voice_provider"), "voice_provider") or "mock",
                    self._text(values.get("tts_provider"), "tts_provider") or "mock",
                    json.dumps(values.get("session_context") or values.get("session_context_json") or {}, ensure_ascii=False),
                    json.dumps(values.get("voice_config") or values.get("voice_config_json") or {}, ensure_ascii=False),
                    metadata_json,
                ),
            )
            row = connection.execute(
                "SELECT * FROM interview_sessions WHERE id = ?",
                (int(cursor.lastrowid),),
            ).fetchone()
            return row

    def update_interview_session(self, session_id: int | str, values: dict[str, Any]) -> sqlite3.Row | None:
        existing = self.get_interview_session(session_id) if isinstance(session_id, (int, str)) else None
        if existing is None:
            raise ValueError("interview session not found")
        target_id = int(existing["id"])
        metadata_source = values.get("metadata_json") if values.get("metadata_json") is not None else existing["metadata_json"]
        try:
            metadata_dict = json.loads(metadata_source) if isinstance(metadata_source, str) else (metadata_source or {})
        except (TypeError, ValueError):
            metadata_dict = {}
        if not isinstance(metadata_dict, dict):
            metadata_dict = {}
        mode = self._text(values.get("mode"), "mode") or metadata_dict.get("mode") or existing["mode"] or "Structured Interview"
        metadata_dict["mode"] = mode
        metadata_dict["voice_mode"] = bool(values.get("voice_mode", metadata_dict.get("voice_mode", bool(existing["voice_mode"]) if existing["voice_mode"] is not None else False)))
        if values.get("session_context_json") is not None:
            session_context = values["session_context_json"]
        elif values.get("session_context") is not None:
            session_context = values["session_context"]
        else:
            session_context = existing["session_context_json"]
        if isinstance(session_context, dict):
            session_context_json = json.dumps(session_context, ensure_ascii=False)
        else:
            try:
                session_context_json = json.dumps(json.loads(session_context) if isinstance(session_context, str) else {}, ensure_ascii=False)
            except (TypeError, ValueError):
                session_context_json = json.dumps({}, ensure_ascii=False)
        if values.get("voice_config_json") is not None:
            voice_config = values["voice_config_json"]
        elif values.get("voice_config") is not None:
            voice_config = values["voice_config"]
        else:
            voice_config = existing["voice_config_json"]
        if isinstance(voice_config, dict):
            voice_config_json = json.dumps(voice_config, ensure_ascii=False)
        else:
            try:
                voice_config_json = json.dumps(json.loads(voice_config) if isinstance(voice_config, str) else {}, ensure_ascii=False)
            except (TypeError, ValueError):
                voice_config_json = json.dumps({}, ensure_ascii=False)
        updates = {
            "role": self._text(values.get("role"), "role") or existing["role"],
            "interview_type": self._text(values.get("interview_type"), "interview_type") or existing["interview_type"],
            "difficulty": self._text(values.get("difficulty"), "difficulty") or existing["difficulty"],
            "question_count": max(1, int(values.get("question_count", existing["question_count"]) or existing["question_count"])),
            "status": self._text(values.get("status"), "status") or existing["status"],
            "current_question": max(0, int(values.get("current_question", existing["current_question"]) or existing["current_question"])),
            "completed_questions": max(0, int(values.get("completed_questions", existing["completed_questions"]) or existing["completed_questions"])),
            "selected_topics": values.get("selected_topics") if values.get("selected_topics") is not None else existing["selected_topics"],
            "metadata_json": json.dumps(metadata_dict, ensure_ascii=False),
            "candidate_profile_id": self._id(values.get("candidate_profile_id", existing["candidate_profile_id"]), "candidate_profile_id") if values.get("candidate_profile_id") is not None else existing["candidate_profile_id"],
            "job_id": self._id(values.get("job_id", existing["job_id"]), "job_id") if values.get("job_id") is not None else existing["job_id"],
            "resume_document_id": self._id(values.get("resume_document_id", existing["resume_document_id"]), "resume_document_id") if values.get("resume_document_id") is not None else existing["resume_document_id"],
            "resume_version_id": self._id(values.get("resume_version_id", existing["resume_version_id"]), "resume_version_id") if values.get("resume_version_id") is not None else existing["resume_version_id"],
            "application_id": self._id(values.get("application_id", existing["application_id"]), "application_id") if values.get("application_id") is not None else existing["application_id"],
            "mode": mode,
            "voice_mode": int(bool(values.get("voice_mode", bool(existing["voice_mode"]) if existing["voice_mode"] is not None else False))),
            "voice_provider": self._text(values.get("voice_provider"), "voice_provider") or existing["voice_provider"] or "mock",
            "tts_provider": self._text(values.get("tts_provider"), "tts_provider") or existing["tts_provider"] or "mock",
            "session_context_json": session_context_json,
            "voice_config_json": voice_config_json,
            "started_at": self._text(values.get("started_at"), "started_at") or existing["started_at"],
            "ended_at": self._text(values.get("ended_at"), "ended_at") or existing["ended_at"],
        }
        if isinstance(updates["selected_topics"], list):
            updates["selected_topics"] = ", ".join(str(item).strip() for item in updates["selected_topics"] if str(item).strip())
        with get_connection(self.database_path) as connection:
            if updates["job_id"] is not None:
                self._ensure_reference(connection, "jobs", updates["job_id"], "job_id")
            if updates["candidate_profile_id"] is not None:
                self._ensure_reference(connection, "candidate_profiles", updates["candidate_profile_id"], "candidate_profile_id")
            if updates["resume_document_id"] is not None:
                self._ensure_reference(connection, "resume_documents", updates["resume_document_id"], "resume_document_id")
            if updates["resume_version_id"] is not None:
                self._ensure_reference(connection, "resume_versions", updates["resume_version_id"], "resume_version_id")
            if updates["application_id"] is not None:
                self._ensure_reference(connection, "applications", updates["application_id"], "application_id")
            connection.execute(
                """
                UPDATE interview_sessions SET role=?, interview_type=?, difficulty=?, selected_topics=?,
                question_count=?, status=?, current_question=?, completed_questions=?, started_at=?,
                ended_at=?, candidate_profile_id=?, job_id=?, resume_document_id=?, resume_version_id=?, application_id=?,
                mode=?, voice_mode=?, voice_provider=?, tts_provider=?, session_context_json=?, voice_config_json=?,
                metadata_json=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    updates["role"], updates["interview_type"], updates["difficulty"], updates["selected_topics"],
                    updates["question_count"], updates["status"], updates["current_question"], updates["completed_questions"],
                    updates["started_at"], updates["ended_at"], updates["candidate_profile_id"], updates["job_id"],
                    updates["resume_document_id"], updates["resume_version_id"], updates["application_id"],
                    updates["mode"], updates["voice_mode"], updates["voice_provider"], updates["tts_provider"],
                    updates["session_context_json"], updates["voice_config_json"], updates["metadata_json"], target_id,
                ),
            )
        return self.get_interview_session(target_id)

    def list_interview_messages(self, session_id: int | str) -> list[sqlite3.Row]:
        session = self.get_interview_session(session_id)
        if session is None:
            return []
        with get_connection(self.database_path) as connection:
            return list(connection.execute(
                "SELECT * FROM interview_messages WHERE session_id = ? ORDER BY created_at ASC, id ASC",
                (int(session["id"]),),
            ))

    def add_interview_message(self, session_id: int | str, speaker: str, message: str,
                             question_id: int | None = None, source_question_id: int | None = None,
                             follow_up: bool = False, *, transcript_text: str | None = None,
                             voice_mode: bool = False) -> int:
        session = self.get_interview_session(session_id)
        if session is None:
            raise ValueError("interview session not found")
        if speaker not in {"interviewer", "user", "system"}:
            raise ValueError("speaker must be interviewer, user, or system")
        message_text = self._text(message, "message", True)
        with get_connection(self.database_path) as connection:
            if question_id is not None:
                self._ensure_reference(connection, "questions", question_id, "question_id")
            if source_question_id is not None:
                self._ensure_reference(connection, "questions", source_question_id, "source_question_id")
            cursor = connection.execute(
                """
                INSERT INTO interview_messages (session_id, speaker, message, question_id, source_question_id, follow_up, transcript_text, voice_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (int(session["id"]), speaker, message_text, self._id(question_id, "question_id") if question_id is not None else None,
                 self._id(source_question_id, "source_question_id") if source_question_id is not None else None,
                 int(bool(follow_up)), self._text(transcript_text, "transcript_text") if transcript_text is not None else None,
                 int(bool(voice_mode))),
            )
        return int(cursor.lastrowid)

    def build_interview_questions(self, *, role: str, interview_type: str, difficulty: str | None = None,
                                 selected_topics: list[str] | None = None, question_count: int = 5,
                                 mode: str = "structured") -> list[sqlite3.Row]:
        cleaned_topics = [str(item).strip() for item in (selected_topics or []) if str(item).strip()]
        style_aliases = {
            "hr": "behavioral",
            "human resources": "behavioral",
            "sql technical": "technical",
            "technical round": "technical",
            "technical": "technical",
            "project": "project-explanation",
            "practical": "sql-practical",
            "mixed": None,
            "custom": None,
        }
        desired_style = style_aliases.get(str(interview_type).lower(), None)
        rows: list[sqlite3.Row] = []
        seen: set[int] = set()
        for topic in cleaned_topics:
            for row in self.list_questions(search=topic, difficulty=difficulty, interview_style=desired_style, limit=15):
                if row["id"] not in seen:
                    rows.append(row)
                    seen.add(row["id"])
            if len(rows) >= max(1, int(question_count)):
                break
        if len(rows) < max(1, int(question_count)):
            fallback_categories = [
                row["id"] for row in self.list_categories() if row["slug"] in {"hr-screening", "technical-round", "project-practical", "non-technical-live-interview"}
            ]
            for category_id in fallback_categories:
                for row in self.list_questions(category_id=category_id, difficulty=difficulty, interview_style=desired_style, limit=20):
                    if row["id"] not in seen:
                        rows.append(row); seen.add(row["id"])
                    if len(rows) >= max(1, int(question_count)):
                        break
                if len(rows) >= max(1, int(question_count)):
                    break
        if not rows:
            row = self.list_questions(limit=1)
            if row:
                return row[:max(1, int(question_count))]
        return rows[:max(1, int(question_count))]

    def create_category(self, values: dict[str, Any]) -> int:
        name = self._text(values.get("name"), "name", True)
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO categories (name, slug, description, sort_order) VALUES (?, ?, ?, ?)",
                (name, self._slug(values.get("slug"), name), self._text(values.get("description"), "description"),
                 int(values.get("sort_order", 0))),
            )
            return int(cursor.lastrowid)

    def create_module(self, values: dict[str, Any]) -> int:
        name = self._text(values.get("name"), "name", True)
        category_id = self._id(values.get("category_id"), "category_id", True)
        with get_connection(self.database_path) as connection:
            self._ensure_reference(connection, "categories", category_id, "category_id")
            cursor = connection.execute(
                "INSERT INTO modules (category_id, name, slug, description, sort_order) VALUES (?, ?, ?, ?, ?)",
                (category_id, name, self._slug(values.get("slug"), name), self._text(values.get("description"), "description"),
                 int(values.get("sort_order", 0))),
            )
            return int(cursor.lastrowid)

    def create_topic(self, values: dict[str, Any]) -> int:
        name = self._text(values.get("name"), "name", True)
        module_id = self._id(values.get("module_id"), "module_id", True)
        with get_connection(self.database_path) as connection:
            self._ensure_reference(connection, "modules", module_id, "module_id")
            cursor = connection.execute(
                "INSERT INTO topics (module_id, name, slug, description, sort_order) VALUES (?, ?, ?, ?, ?)",
                (module_id, name, self._slug(values.get("slug"), name), self._text(values.get("description"), "description"),
                 int(values.get("sort_order", 0))),
            )
            return int(cursor.lastrowid)

    def _update_named(self, table: str, item_id: int, values: dict[str, Any]) -> None:
        if table not in {"categories", "modules", "topics"}:
            raise ValueError("unsupported content type")
        item_id = self._id(item_id, "id", True)
        name = self._text(values.get("name"), "name", True)
        slug = self._slug(values.get("slug"), name)
        fields = ["name=?", "slug=?", "description=?", "sort_order=?", "updated_at=CURRENT_TIMESTAMP"]
        params: list[Any] = [name, slug, self._text(values.get("description"), "description"), int(values.get("sort_order", 0))]
        if table == "modules":
            fields.insert(0, "category_id=?")
            params.insert(0, self._id(values.get("category_id"), "category_id", True))
        if table == "topics":
            fields.insert(0, "module_id=?")
            params.insert(0, self._id(values.get("module_id"), "module_id", True))
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(f"UPDATE {table} SET {', '.join(fields)} WHERE id=?", params + [item_id])
            if cursor.rowcount == 0:
                raise ValueError(f"{table[:-1]} not found")

    def update_category(self, category_id: int, values: dict[str, Any]) -> None:
        self._update_named("categories", category_id, values)

    def update_module(self, module_id: int, values: dict[str, Any]) -> None:
        self._update_named("modules", module_id, values)

    def update_topic(self, topic_id: int, values: dict[str, Any]) -> None:
        self._update_named("topics", topic_id, values)

    def delete_category(self, category_id: int) -> None:
        with get_connection(self.database_path) as connection:
            connection.execute("DELETE FROM categories WHERE id=?", (self._id(category_id, "category_id", True),))

    def delete_module(self, module_id: int) -> None:
        with get_connection(self.database_path) as connection:
            connection.execute("DELETE FROM modules WHERE id=?", (self._id(module_id, "module_id", True),))

    def delete_topic(self, topic_id: int) -> None:
        with get_connection(self.database_path) as connection:
            connection.execute("DELETE FROM topics WHERE id=?", (self._id(topic_id, "topic_id", True),))

    def create_question(self, values: dict[str, Any]) -> int:
        category_id = self._id(values.get("category_id"), "category_id", True)
        question = self._text(values.get("question"), "question", True)
        with get_connection(self.database_path) as connection:
            self._ensure_reference(connection, "categories", category_id, "category_id")
            self._ensure_reference(connection, "modules", self._id(values.get("module_id"), "module_id"), "module_id")
            self._ensure_reference(connection, "topics", self._id(values.get("topic_id"), "topic_id"), "topic_id")
            cursor = connection.execute(
                """
                INSERT INTO questions (
                    category_id, module_id, topic_id, question, answer, personal_answer, explanation,
                    question_type, difficulty, interview_trick, follow_up,
                    interviewer_expectation, thinking_approach, sql_solution,
                    alternative_solution, common_trap, interview_style, source, completed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    category_id, self._id(values.get("module_id"), "module_id"),
                    self._id(values.get("topic_id"), "topic_id"), question,
                    self._text(values.get("answer"), "answer"), self._text(values.get("personal_answer"), "personal_answer"),
                    self._text(values.get("explanation"), "explanation"),
                    self._text(values.get("question_type", "general"), "question_type", True),
                    self._text(values.get("difficulty", "medium"), "difficulty", True),
                    self._text(values.get("interview_trick"), "interview_trick"),
                    self._text(values.get("follow_up"), "follow_up"),
                    self._text(values.get("interviewer_expectation"), "interviewer_expectation"),
                    self._text(values.get("thinking_approach"), "thinking_approach"),
                    self._text(values.get("sql_solution"), "sql_solution"),
                    self._text(values.get("alternative_solution"), "alternative_solution"),
                    self._text(values.get("common_trap"), "common_trap"),
                    self._text(values.get("interview_style"), "interview_style"),
                    self._text(values.get("source"), "source"),
                    int(bool(values.get("completed", False))),
                ),
            )
            question_id = int(cursor.lastrowid)
        if "tags" in values:
            self.replace_question_tags(question_id, values["tags"])
        return question_id

    def get_question(self, question_id: int) -> sqlite3.Row | None:
        with get_connection(self.database_path) as connection:
            return connection.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()

    def update_question(self, question_id: int, values: dict[str, Any]) -> None:
        question_id = self._id(question_id, "question_id", True)
        allowed = ("category_id", "module_id", "topic_id", "question", "answer", "explanation",
                   "personal_answer", "question_type", "difficulty", "interview_trick", "follow_up",
                   "interviewer_expectation", "thinking_approach", "sql_solution",
                   "alternative_solution", "common_trap", "interview_style", "source", "completed")
        if not any(key in values for key in allowed):
            raise ValueError("no question fields supplied")
        current = self.get_question(question_id)
        if current is None:
            raise ValueError("question not found")
        data = {key: values.get(key, current[key]) for key in allowed}
        data["category_id"] = self._id(data["category_id"], "category_id", True)
        data["module_id"] = self._id(data["module_id"], "module_id")
        data["topic_id"] = self._id(data["topic_id"], "topic_id")
        data["question"] = self._text(data["question"], "question", True)
        data["completed"] = int(bool(data["completed"]))
        with get_connection(self.database_path) as connection:
            self._ensure_reference(connection, "categories", data["category_id"], "category_id")
            self._ensure_reference(connection, "modules", data["module_id"], "module_id")
            self._ensure_reference(connection, "topics", data["topic_id"], "topic_id")
            connection.execute(
                """UPDATE questions SET category_id=?, module_id=?, topic_id=?, question=?, answer=?,
                   explanation=?, personal_answer=?, question_type=?, difficulty=?, interview_trick=?, follow_up=?,
                   interviewer_expectation=?, thinking_approach=?, sql_solution=?, alternative_solution=?,
                   common_trap=?, interview_style=?, source=?, completed=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                tuple(data[key] for key in allowed) + (question_id,),
            )
        if "tags" in values:
            self.replace_question_tags(question_id, values["tags"])

    def delete_question(self, question_id: int) -> None:
        with get_connection(self.database_path) as connection:
            connection.execute("DELETE FROM questions WHERE id = ?", (self._id(question_id, "question_id", True),))

    def list_questions(self, *, category_id: int | None = None, module_id: int | None = None,
                      topic_id: int | None = None, search: str = "", tags: list[str] | None = None,
                      difficulty: str | None = None, question_type: str | None = None,
                      interview_style: str | None = None,
                      sort_by: str = "updated_at", descending: bool = True,
                      limit: int | None = None, offset: int | None = None) -> list[sqlite3.Row]:
        allowed_sort = {"updated_at", "created_at", "question", "difficulty"}
        sort_column = sort_by if sort_by in allowed_sort else "updated_at"
        clauses, params = [], []
        for column, value in (("category_id", category_id), ("module_id", module_id), ("topic_id", topic_id)):
            if value is not None:
                clauses.append(f"q.{column} = ?")
                params.append(self._id(value, column, True))
        if search.strip():
            clauses.append("""(q.question LIKE ? OR q.answer LIKE ? OR q.personal_answer LIKE ? OR q.explanation LIKE ?
                OR q.follow_up LIKE ? OR q.interviewer_expectation LIKE ? OR q.thinking_approach LIKE ?
                OR q.sql_solution LIKE ? OR q.alternative_solution LIKE ? OR q.common_trap LIKE ?
                OR q.interview_style LIKE ? OR c.name LIKE ? OR m.name LIKE ? OR t.name LIKE ?
                OR EXISTS (SELECT 1 FROM question_tags sqt JOIN tags st ON st.id=sqt.tag_id
                           WHERE sqt.question_id=q.id AND st.name LIKE ?))""")
            term = f"%{search.strip()}%"
            params.extend((term,) * 15)
        if difficulty:
            clauses.append("q.difficulty = ?")
            params.append(difficulty)
        if question_type:
            clauses.append("q.question_type = ?")
            params.append(question_type)
        if interview_style:
            clauses.append("q.interview_style = ?")
            params.append(interview_style)
        wanted_tags = [str(tag).strip() for tag in (tags or []) if str(tag).strip()]
        if wanted_tags:
            placeholders = ",".join("?" for _ in wanted_tags)
            clauses.append(f"""q.id IN (SELECT qt.question_id FROM question_tags qt JOIN tags t ON t.id=qt.tag_id
                              WHERE t.name IN ({placeholders}) GROUP BY qt.question_id HAVING COUNT(DISTINCT t.name)=?)""")
            params.extend(wanted_tags)
            params.append(len(wanted_tags))
        query = """SELECT q.*, c.name AS category_name, m.name AS module_name, t.name AS topic_name,
                   COALESCE((SELECT GROUP_CONCAT(tag.name, ', ') FROM question_tags qt
                   JOIN tags tag ON tag.id=qt.tag_id WHERE qt.question_id=q.id), '') AS tag_names
                   FROM questions q JOIN categories c ON c.id=q.category_id
                   LEFT JOIN modules m ON m.id=q.module_id LEFT JOIN topics t ON t.id=q.topic_id"""
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += f" ORDER BY q.{sort_column} {'DESC' if descending else 'ASC'}, q.id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(1, int(limit)))
            if offset is not None:
                query += " OFFSET ?"
                params.append(max(0, int(offset)))
        with get_connection(self.database_path) as connection:
            return list(connection.execute(query, params))

    def search_questions(self, search: str, **filters: Any) -> list[sqlite3.Row]:
        return self.list_questions(search=search, **filters)

    def filter_questions(self, **filters: Any) -> list[sqlite3.Row]:
        return self.list_questions(**filters)

    def practice_set(self, *, category_id: int | None = None, module_id: int | None = None,
                    topic_id: int | None = None, difficulty: str | None = None,
                    interview_type: str | None = None, size: int = 10,
                    randomize: bool = False) -> list[sqlite3.Row]:
        # Accept display labels and stable slug forms so callers can use the
        # same project practice API without creating a second engine.
        style_aliases = {
            "Project Explanation": "project-explanation",
            "project_explanation": "project-explanation",
            "SQL Practical": "sql-practical",
            "sql_practical": "sql-practical",
            "Business Scenario": "business-scenario",
            "business_scenario": "business-scenario",
            "Data Quality": "data-quality",
            "data_quality": "data-quality",
            "Follow-up": "follow-up",
            "follow_up": "follow-up",
            "Mixed Project": None,
            "mixed-project": None,
        }
        interview_type = style_aliases.get(interview_type, interview_type)
        rows = self.list_questions(category_id=category_id, module_id=module_id,
                                    topic_id=topic_id, difficulty=difficulty,
                                    interview_style=interview_type)
        if randomize:
            import random
            random.Random(0).shuffle(rows)
        return rows[:max(1, int(size))]

    def get_practice_set(self, **filters: Any) -> list[sqlite3.Row]:
        """Named API alias used by UI integrations."""
        return self.practice_set(**filters)

    def record_practice_attempt(self, question_id: int, *, response: str = "",
                                score: float | None = None, notes: str = "",
                                source: str = "technical-round", completed: bool = True,
                                interview_type: str | None = None) -> int:
        question_id = self._id(question_id, "question_id", True)
        with get_connection(self.database_path) as connection:
            self._ensure_reference(connection, "questions", question_id, "question_id")
            cursor = connection.execute(
                """INSERT INTO interview_history
                   (question_id,response,score,notes,source,completed,interview_type)
                   VALUES (?,?,?,?,?,?,?)""",
                (question_id, response or None, score, notes or None, source,
                 int(bool(completed)), interview_type),
            )
            if completed:
                connection.execute("UPDATE questions SET completed=1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                                   (question_id,))
            return int(cursor.lastrowid)

    def record_practice(self, question_id: int, **values: Any) -> int:
        return self.record_practice_attempt(question_id, **values)

    def list_practice_history(self, question_id: int | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if question_id is None:
                return list(connection.execute("SELECT * FROM interview_history ORDER BY asked_at DESC, id DESC"))
            return list(connection.execute(
                "SELECT * FROM interview_history WHERE question_id=? ORDER BY asked_at DESC, id DESC",
                (self._id(question_id, "question_id", True),)))

    def count_questions(self, **filters: Any) -> int:
        clauses, params = [], []
        for column, value in (("category_id", filters.get("category_id")),
                              ("module_id", filters.get("module_id")),
                              ("topic_id", filters.get("topic_id"))):
            if value is not None:
                clauses.append(f"q.{column}=?")
                params.append(self._id(value, column, True))
        for column in ("difficulty", "question_type", "interview_style"):
            if filters.get(column):
                clauses.append(f"q.{column}=?")
                params.append(filters[column])
        search = str(filters.get("search") or "").strip()
        if search:
            clauses.append("""(q.question LIKE ? OR q.answer LIKE ? OR q.personal_answer LIKE ? OR q.explanation LIKE ?
                OR q.follow_up LIKE ? OR q.interviewer_expectation LIKE ? OR q.thinking_approach LIKE ?
                OR q.sql_solution LIKE ? OR q.alternative_solution LIKE ? OR q.common_trap LIKE ?
                OR q.interview_style LIKE ? OR c.name LIKE ? OR m.name LIKE ? OR t.name LIKE ?
                OR EXISTS (SELECT 1 FROM question_tags sqt JOIN tags st ON st.id=sqt.tag_id
                           WHERE sqt.question_id=q.id AND st.name LIKE ?))""")
            params.extend((f"%{search}%",) * 15)
        wanted_tags = [str(tag).strip() for tag in (filters.get("tags") or []) if str(tag).strip()]
        if wanted_tags:
            placeholders = ",".join("?" for _ in wanted_tags)
            clauses.append(f"""q.id IN (SELECT qt.question_id FROM question_tags qt JOIN tags t ON t.id=qt.tag_id
                              WHERE t.name IN ({placeholders}) GROUP BY qt.question_id
                              HAVING COUNT(DISTINCT t.name)=?)""")
            params.extend(wanted_tags)
            params.append(len(wanted_tags))
        query = """SELECT COUNT(*) FROM questions q
                   JOIN categories c ON c.id=q.category_id
                   LEFT JOIN modules m ON m.id=q.module_id
                   LEFT JOIN topics t ON t.id=q.topic_id"""
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        with get_connection(self.database_path) as connection:
            return int(connection.execute(query, params).fetchone()[0])

    def list_question_types(self, category_id: int | None = None) -> list[str]:
        query = "SELECT DISTINCT question_type FROM questions"
        params: list[Any] = []
        if category_id is not None:
            query += " WHERE category_id=?"
            params.append(self._id(category_id, "category_id", True))
        query += " ORDER BY question_type"
        with get_connection(self.database_path) as connection:
            return [row[0] for row in connection.execute(query, params) if row[0]]

    def recent_questions(self, limit: int = 5) -> list[sqlite3.Row]:
        return self.list_questions(sort_by="created_at", limit=limit)

    def _list_learning(self, table: str, *, topic_id: int | None = None,
                       question_id: int | None = None) -> list[sqlite3.Row]:
        if table not in {"notes", "examples", "tricks", "followups"}:
            raise ValueError("unsupported learning content")
        clauses, params = [], []
        if topic_id is not None:
            if table == "followups":
                clauses.append("question_id IN (SELECT id FROM questions WHERE topic_id=?)")
            else:
                clauses.append("topic_id=?")
            params.append(self._id(topic_id, "topic_id", True))
        if question_id is not None:
            clauses.append("question_id=?")
            params.append(self._id(question_id, "question_id", True))
        query = f"SELECT * FROM {table}"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id"
        with get_connection(self.database_path) as connection:
            return list(connection.execute(query, params))

    def list_notes(self, **filters: Any) -> list[sqlite3.Row]:
        return self._list_learning("notes", **filters)

    def list_examples(self, **filters: Any) -> list[sqlite3.Row]:
        return self._list_learning("examples", **filters)

    def list_tricks(self, **filters: Any) -> list[sqlite3.Row]:
        return self._list_learning("tricks", **filters)

    def list_followups(self, **filters: Any) -> list[sqlite3.Row]:
        return self._list_learning("followups", **filters)

    def _get_learning(self, table: str, item_id: int) -> sqlite3.Row | None:
        if table not in {"notes", "examples", "tricks", "followups"}:
            raise ValueError("unsupported learning content")
        with get_connection(self.database_path) as connection:
            return connection.execute(f"SELECT * FROM {table} WHERE id=?", (self._id(item_id, "id", True),)).fetchone()

    def get_note(self, item_id: int) -> sqlite3.Row | None:
        return self._get_learning("notes", item_id)

    def get_example(self, item_id: int) -> sqlite3.Row | None:
        return self._get_learning("examples", item_id)

    def get_trick(self, item_id: int) -> sqlite3.Row | None:
        return self._get_learning("tricks", item_id)

    def get_followup(self, item_id: int) -> sqlite3.Row | None:
        return self._get_learning("followups", item_id)

    def _create_learning(self, table: str, values: dict[str, Any]) -> int:
        if table not in {"notes", "examples", "tricks", "followups"}:
            raise ValueError("unsupported learning content")
        title = self._text(values.get("title", values.get("question")), "title", True)
        body = self._text(values.get("body", values.get("answer")), "body", True)
        topic_id = self._id(values.get("topic_id"), "topic_id")
        question_id = self._id(values.get("question_id"), "question_id")
        if table == "followups":
            question = self._text(values.get("question"), "question", True)
            with get_connection(self.database_path) as connection:
                self._ensure_reference(connection, "questions", question_id, "question_id")
                return int(connection.execute(
                    "INSERT INTO followups(question_id,question,answer) VALUES (?,?,?)",
                    (question_id, question, self._text(values.get("answer"), "answer"))).lastrowid)
        with get_connection(self.database_path) as connection:
            if topic_id is not None:
                self._ensure_reference(connection, "topics", topic_id, "topic_id")
            if question_id is not None:
                self._ensure_reference(connection, "questions", question_id, "question_id")
            if table == "tricks":
                cursor = connection.execute("INSERT INTO tricks(question_id,topic_id,title,body) VALUES (?,?,?,?)",
                                            (question_id, topic_id, title, body))
            else:
                cursor = connection.execute(f"INSERT INTO {table}(topic_id,title,body) VALUES (?,?,?)",
                                            (topic_id, title, body))
            return int(cursor.lastrowid)

    def create_note(self, values: dict[str, Any]) -> int:
        return self._create_learning("notes", values)

    def create_example(self, values: dict[str, Any]) -> int:
        return self._create_learning("examples", values)

    def create_trick(self, values: dict[str, Any]) -> int:
        return self._create_learning("tricks", values)

    def create_followup(self, values: dict[str, Any]) -> int:
        return self._create_learning("followups", values)

    def search_content(self, search: str, **filters: Any) -> list[dict[str, Any]]:
        term = f"%{str(search).strip()}%"
        topic_id, module_id = filters.get("topic_id"), filters.get("module_id")
        results: list[dict[str, Any]] = []
        with get_connection(self.database_path) as connection:
            scoped = " AND ".join(filter(None, [
                "x.id=?" if topic_id is not None else "",
                "m.id=?" if module_id is not None else "",
            ]))
            scope_params = ([self._id(topic_id, "topic_id", True)] if topic_id is not None else [])
            scope_params += ([self._id(module_id, "module_id", True)] if module_id is not None else [])
            for table, fields, join in (
                ("notes", "title,body", "JOIN topics x ON x.id=n.topic_id JOIN modules m ON m.id=x.module_id"),
                ("examples", "title,body", "JOIN topics x ON x.id=n.topic_id JOIN modules m ON m.id=x.module_id"),
                ("tricks", "title,body", "LEFT JOIN topics x ON x.id=n.topic_id JOIN modules m ON m.id=x.module_id"),
                ("followups", "question,answer", "JOIN questions q ON q.id=n.question_id LEFT JOIN topics x ON x.id=q.topic_id LEFT JOIN modules m ON m.id=x.module_id"),
            ):
                aliases = " OR ".join(f"n.{field} LIKE ?" for field in fields.split(","))
                where = f"({aliases})" + (f" AND {scoped}" if scoped else "")
                selected = ",".join(f"n.{field}" for field in fields.split(","))
                for row in connection.execute(f"SELECT n.id,{selected} FROM {table} n {join} WHERE {where}",
                                              [term] * len(fields.split(",")) + scope_params):
                    results.append({"content_type": table[:-1], **dict(row)})
        results.extend({"content_type": "question", **dict(row)}
                       for row in self.search_questions(search, module_id=module_id, topic_id=topic_id, **{
                           k: v for k, v in filters.items() if k in {"category_id", "difficulty", "question_type", "tags"}}))
        return results

    def list_tags(self) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            return list(connection.execute("SELECT * FROM tags ORDER BY name"))

    def get_question_tags(self, question_id: int) -> list[str]:
        with get_connection(self.database_path) as connection:
            return [row["name"] for row in connection.execute(
                "SELECT t.name FROM tags t JOIN question_tags qt ON qt.tag_id=t.id WHERE qt.question_id=? ORDER BY t.name",
                (self._id(question_id, "question_id", True),))]

    def replace_question_tags(self, question_id: int, tags: list[str] | str | None) -> None:
        question_id = self._id(question_id, "question_id", True)
        values = [str(tag).strip() for tag in (tags.split(",") if isinstance(tags, str) else (tags or []))
                  if str(tag).strip()]
        with get_connection(self.database_path) as connection:
            connection.execute("DELETE FROM question_tags WHERE question_id=?", (question_id,))
            for name in dict.fromkeys(values):
                connection.execute("INSERT INTO tags(name) VALUES (?) ON CONFLICT(name) DO NOTHING", (name,))
                tag_id = connection.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()[0]
                connection.execute("INSERT INTO question_tags(question_id, tag_id) VALUES (?, ?)", (question_id, tag_id))

    # Phase 6: candidate, jobs, matching, resumes, and application tracking.
    def get_candidate_profile(self) -> sqlite3.Row | None:
        with get_connection(self.database_path) as connection:
            return connection.execute("SELECT * FROM candidate_profiles WHERE id=1").fetchone()

    def save_candidate_profile(self, values: dict[str, Any]) -> int:
        fields = ("full_name", "headline", "email", "phone", "location", "links", "summary",
                  "skills", "experience", "education", "tools", "sql", "projects", "certifications",
                  "preferred_roles", "preferred_locations", "experience_level", "availability",
                  "resume_information", "additional_information")
        data = [self._text(values.get(field), field) for field in fields]
        with get_connection(self.database_path) as connection:
            connection.execute(
                f"INSERT INTO candidate_profiles (id,{','.join(fields)}) VALUES (1,{','.join('?' for _ in fields)}) "
                f"ON CONFLICT(id) DO UPDATE SET {','.join(f'{field}=excluded.{field}' for field in fields)}, updated_at=CURRENT_TIMESTAMP",
                data,
            )
        return 1

    def create_job(self, values: dict[str, Any]) -> int:
        values = dict(values or {})
        if "sql_requirements" not in values and "sql" in values:
            values["sql_requirements"] = values["sql"]
        if "required_skills" not in values and "skills" in values:
            values["required_skills"] = values["skills"]
        if "skills" not in values and "required_skills" in values:
            values["skills"] = values["required_skills"]
        if "source_metadata" not in values and "metadata" in values:
            values["source_metadata"] = values["metadata"]
        required = ("source", "company", "title")
        for key in required:
            if not self._text(values.get(key), key, True):
                raise ValueError(f"{key} is required")
        fields = ("external_id", "source", "company", "title", "location", "remote_type", "description",
                  "requirements", "skills", "required_skills", "preferred_skills", "responsibilities", "education",
                  "sql_requirements", "sql", "tools", "experience", "salary", "posting_date",
                  "application_url", "source_url", "source_metadata", "metadata")
        data = [self._text(values.get(field), field) for field in fields]

        source_value = data[1]
        external_id_value = data[0]
        company_value = data[2]
        title_value = data[3]
        location_value = data[4]
        remote_type_value = data[5]
        description_value = data[6]
        requirements_value = data[7]
        skills_value = data[8]
        required_skills_value = data[9]
        preferred_skills_value = data[10]
        responsibilities_value = data[11]
        education_value = data[12]
        sql_requirements_value = data[13]
        sql_value = data[14]
        tools_value = data[15]
        experience_value = data[16]
        salary_value = data[17]
        posting_date_value = data[18]
        application_url_value = data[19]
        source_url_value = data[20]
        source_metadata_value = data[21]
        metadata_value = data[22]

        with get_connection(self.database_path) as connection:
            if external_id_value:
                existing = connection.execute(
                    "SELECT id FROM jobs WHERE source=? AND external_id=? LIMIT 1",
                    (source_value, external_id_value),
                ).fetchone()
                if existing is not None:
                    connection.execute(
                        "UPDATE jobs SET company=?, title=?, location=?, remote_type=?, description=?, requirements=?, "
                        "skills=?, required_skills=?, preferred_skills=?, responsibilities=?, education=?, "
                        "sql_requirements=?, sql=?, tools=?, experience=?, salary=?, posting_date=?, "
                        "application_url=?, source_url=?, source_metadata=?, metadata=? WHERE id=?",
                        (
                            company_value, title_value, location_value, remote_type_value, description_value,
                            requirements_value, skills_value, required_skills_value, preferred_skills_value,
                            responsibilities_value, education_value, sql_requirements_value, sql_value, tools_value,
                            experience_value, salary_value, posting_date_value, application_url_value,
                            source_url_value, source_metadata_value, metadata_value, int(existing["id"]),
                        ),
                    )
                    return int(existing["id"])

            duplicate_query = (
                "SELECT id FROM jobs WHERE source=? AND lower(company)=lower(?) AND lower(title)=lower(?) "
                "AND COALESCE(lower(location),'')=COALESCE(lower(?), '') "
                "AND COALESCE(application_url,'')=COALESCE(?, '') LIMIT 1"
            )
            existing = connection.execute(
                duplicate_query,
                (source_value, company_value, title_value, location_value or "", application_url_value or ""),
            ).fetchone()
            if existing is not None:
                return int(existing["id"])

            if not external_id_value and not application_url_value and not source_url_value:
                fallback = connection.execute(
                    "SELECT id FROM jobs WHERE source=? AND lower(company)=lower(?) AND lower(title)=lower(?) LIMIT 1",
                    (source_value, company_value, title_value),
                ).fetchone()
                if fallback is not None:
                    return int(fallback["id"])

            cursor = connection.execute(
                f"INSERT INTO jobs ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)}) "
                "ON CONFLICT(source, external_id) DO UPDATE SET company=excluded.company,title=excluded.title,"
                "location=excluded.location,remote_type=excluded.remote_type,description=excluded.description,"
                "requirements=excluded.requirements,skills=excluded.skills,required_skills=excluded.required_skills,"
                "preferred_skills=excluded.preferred_skills,responsibilities=excluded.responsibilities,"
                "education=excluded.education,sql_requirements=excluded.sql_requirements,sql=excluded.sql,"
                "tools=excluded.tools,experience=excluded.experience,salary=excluded.salary,posting_date=excluded.posting_date,"
                "application_url=excluded.application_url,source_url=excluded.source_url,source_metadata=excluded.source_metadata,metadata=excluded.metadata",
                data,
            )
            if cursor.lastrowid:
                return int(cursor.lastrowid)
            row = connection.execute("SELECT id FROM jobs WHERE source=? AND external_id=?", (source_value, external_id_value)).fetchone()
            if row is not None:
                return int(row[0])
            fallback_row = connection.execute(
                "SELECT id FROM jobs WHERE source=? AND lower(company)=lower(?) AND lower(title)=lower(?) ORDER BY id DESC LIMIT 1",
                (source_value, company_value, title_value),
            ).fetchone()
            if fallback_row is not None:
                return int(fallback_row[0])
            raise ValueError("job could not be persisted")

    def get_job(self, job_id: int) -> sqlite3.Row | None:
        with get_connection(self.database_path) as connection:
            return connection.execute("SELECT * FROM jobs WHERE id=?", (self._id(job_id, "job_id", True),)).fetchone()

    def list_jobs(
        self,
        search: str = "",
        *,
        source: str | None = None,
        location: str | None = None,
        remote_type: str | None = None,
        posting_since: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        clauses, params = [], []
        if search.strip():
            clauses.append("(title LIKE ? OR company LIKE ? OR description LIKE ? OR skills LIKE ? OR requirements LIKE ?)")
            params.extend([f"%{search.strip()}%"] * 5)
        if source:
            clauses.append("source=?"); params.append(source)
        if location:
            clauses.append("location LIKE ?"); params.append(f"%{location.strip()}%")
        if remote_type:
            clauses.append("remote_type=?"); params.append(remote_type)
        if posting_since:
            clauses.append("(posting_date IS NULL OR posting_date >= ?)"); params.append(posting_since)
        query = "SELECT * FROM jobs" + ((" WHERE " + " AND ".join(clauses)) if clauses else "")
        query += " ORDER BY COALESCE(posting_date, fetched_at) DESC, id DESC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([max(1, int(limit)), max(0, int(offset))])
        with get_connection(self.database_path) as connection:
            return list(connection.execute(query, params))

    def count_jobs(
        self,
        search: str = "",
        *,
        source: str | None = None,
        location: str | None = None,
        remote_type: str | None = None,
        posting_since: str | None = None,
    ) -> int:
        clauses, params = [], []
        if search.strip():
            clauses.append("(title LIKE ? OR company LIKE ? OR description LIKE ? OR skills LIKE ? OR requirements LIKE ?)")
            params.extend([f"%{search.strip()}%"] * 5)
        if source:
            clauses.append("source=?"); params.append(source)
        if location:
            clauses.append("location LIKE ?"); params.append(f"%{location.strip()}%")
        if remote_type:
            clauses.append("remote_type=?"); params.append(remote_type)
        if posting_since:
            clauses.append("(posting_date IS NULL OR posting_date >= ?)"); params.append(posting_since)
        query = "SELECT COUNT(*) AS total FROM jobs" + ((" WHERE " + " AND ".join(clauses)) if clauses else "")
        with get_connection(self.database_path) as connection:
            return int(connection.execute(query, params).fetchone()["total"])

    def record_job_source_check(self, source: str, status: str, result_count: int, message: str) -> int:
        with get_connection(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO job_source_checks(source,status,result_count,message)
                VALUES (?,?,?,?)
                ON CONFLICT(source) DO UPDATE SET status=excluded.status,
                checked_at=CURRENT_TIMESTAMP,result_count=excluded.result_count,message=excluded.message
                """,
                (source, status, int(result_count), message),
            )
            return int(connection.execute("SELECT id FROM job_source_checks WHERE source=?", (source,)).fetchone()["id"])

    def list_job_source_checks(self) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            return list(connection.execute("SELECT * FROM job_source_checks ORDER BY source"))

    def create_job_notification(self, job_id: int, notification_type: str) -> int:
        with get_connection(self.database_path) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO job_notifications(job_id,notification_type) VALUES (?,?)",
                (self._id(job_id, "job_id", True), notification_type),
            )
            return int(connection.execute(
                "SELECT id FROM job_notifications WHERE job_id=? AND notification_type=?",
                (job_id, notification_type),
            ).fetchone()["id"])

    def list_job_notifications(self, *, pending_only: bool = False) -> list[sqlite3.Row]:
        clause = " WHERE n.delivered=0" if pending_only else ""
        with get_connection(self.database_path) as connection:
            return list(connection.execute(
                "SELECT n.*,j.company,j.title,j.posting_date,j.source FROM job_notifications n "
                "JOIN jobs j ON j.id=n.job_id" + clause + " ORDER BY n.created_at DESC,n.id DESC"
            ))

    def mark_job_notification_delivered(self, notification_id: int) -> None:
        with get_connection(self.database_path) as connection:
            connection.execute("UPDATE job_notifications SET delivered=1 WHERE id=?",
                               (self._id(notification_id, "notification_id", True),))

    def save_job(self, job_id: int) -> int:
        with get_connection(self.database_path) as connection:
            connection.execute("INSERT OR IGNORE INTO saved_jobs(job_id) VALUES (?)", (self._id(job_id, "job_id", True),))
            return int(connection.execute("SELECT id FROM saved_jobs WHERE job_id=?", (job_id,)).fetchone()[0])

    def list_saved_jobs(self) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            return list(connection.execute("SELECT j.*, s.saved_at FROM jobs j JOIN saved_jobs s ON s.job_id=j.id ORDER BY s.saved_at DESC"))

    def upsert_application(self, job_id: int, status: str, notes: str = "", applied_at: str | None = None,
                           *, candidate_profile_id: int | None = None, resume_document_id: int | None = None,
                           resume_version_id: int | None = None, official_application_url: str | None = None,
                           source_url: str | None = None, application_method: str = "external",
                           confirmed_submitted: bool = False, metadata: dict[str, Any] | None = None) -> int:
        allowed = {"saved", "ready", "applied", "screening", "interview", "offer", "rejected", "withdrawn"}
        if status not in allowed:
            raise ValueError("unsupported application status")
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True) if metadata is not None else "{}"
        with get_connection(self.database_path) as connection:
            row = connection.execute("SELECT id,status FROM applications WHERE job_id=?", (self._id(job_id, "job_id", True),)).fetchone()
            if row:
                app_id = int(row["id"])
                connection.execute(
                    "UPDATE applications SET status=?,notes=?,applied_at=COALESCE(?,applied_at),candidate_profile_id=?,resume_document_id=?,resume_version_id=?,official_application_url=?,source_url=?,application_method=?,confirmed_submitted=?,metadata_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (
                        status,
                        notes or None,
                        applied_at,
                        self._id(candidate_profile_id, "candidate_profile_id"),
                        self._id(resume_document_id, "resume_document_id"),
                        self._id(resume_version_id, "resume_version_id"),
                        self._text(official_application_url, "official_application_url") or None,
                        self._text(source_url, "source_url") or None,
                        application_method or "external",
                        int(bool(confirmed_submitted)),
                        metadata_json,
                        app_id,
                    ),
                )
            else:
                cur = connection.execute(
                    "INSERT INTO applications(job_id,status,notes,applied_at,candidate_profile_id,resume_document_id,resume_version_id,official_application_url,source_url,application_method,confirmed_submitted,metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        self._id(job_id, "job_id", True),
                        status,
                        notes or None,
                        applied_at,
                        self._id(candidate_profile_id, "candidate_profile_id"),
                        self._id(resume_document_id, "resume_document_id"),
                        self._id(resume_version_id, "resume_version_id"),
                        self._text(official_application_url, "official_application_url") or None,
                        self._text(source_url, "source_url") or None,
                        application_method or "external",
                        int(bool(confirmed_submitted)),
                        metadata_json,
                    ),
                )
                app_id = int(cur.lastrowid)
            if not row or row["status"] != status:
                connection.execute("INSERT INTO application_history(application_id,status,notes) VALUES (?,?,?)",
                                   (app_id, status, notes or None))
            return int(app_id)

    def get_application(self, application_id: int | None = None, *, job_id: int | None = None) -> sqlite3.Row | None:
        with get_connection(self.database_path) as connection:
            if application_id is not None:
                return connection.execute(
                    "SELECT a.*, j.company, j.title, j.location, j.source, j.application_url, j.source_url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.id=?",
                    (self._id(application_id, "application_id", True),),
                ).fetchone()
            if job_id is not None:
                return connection.execute(
                    "SELECT a.*, j.company, j.title, j.location, j.source, j.application_url, j.source_url FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.job_id=? ORDER BY a.updated_at DESC LIMIT 1",
                    (self._id(job_id, "job_id", True),),
                ).fetchone()
            return None

    def create_application(self, job_id: int, status: str = "saved", notes: str = "", *,
                          candidate_profile_id: int | None = None, resume_document_id: int | None = None,
                          resume_version_id: int | None = None, official_application_url: str | None = None,
                          source_url: str | None = None, application_method: str = "external",
                          confirmed_submitted: bool = False, metadata: dict[str, Any] | None = None) -> int:
        return self.upsert_application(
            job_id, status, notes,
            applied_at=None,
            candidate_profile_id=candidate_profile_id,
            resume_document_id=resume_document_id,
            resume_version_id=resume_version_id,
            official_application_url=official_application_url,
            source_url=source_url,
            application_method=application_method,
            confirmed_submitted=confirmed_submitted,
            metadata=metadata,
        )

    def list_applications(self, *, status: str | None = None, company: str | None = None,
                         role: str | None = None, source: str | None = None,
                         limit: int | None = None, offset: int = 0) -> list[sqlite3.Row]:
        clauses, params = [], []
        if status:
            clauses.append("a.status = ?")
            params.append(status)
        if company:
            clauses.append("j.company LIKE ?")
            params.append(f"%{company.strip()}%")
        if role:
            clauses.append("j.title LIKE ?")
            params.append(f"%{role.strip()}%")
        if source:
            clauses.append("j.source = ?")
            params.append(source)
        query = "SELECT a.*, j.company, j.title, j.location, j.source, j.application_url, j.source_url FROM applications a JOIN jobs j ON j.id=a.job_id"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY a.updated_at DESC, a.id DESC"
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([max(1, int(limit)), max(0, int(offset))])
        with get_connection(self.database_path) as connection:
            return list(connection.execute(query, params))

    def list_application_history(self, application_id: int) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            return list(connection.execute("SELECT * FROM application_history WHERE application_id=? ORDER BY changed_at DESC,id DESC", (application_id,)))

    def record_application_event(self, application_id: int, event_type: str, *, description: str = "", metadata: dict[str, Any] | None = None) -> int:
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO application_history(application_id, status, notes) VALUES (?, ?, ?)",
                (self._id(application_id, "application_id", True), event_type, description or json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)),
            )
            return int(cursor.lastrowid)

    def add_application_note(self, application_id: int, note_text: str, *, note_type: str = "general") -> int:
        note_text = self._text(note_text, "note_text", True)
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO application_notes(application_id, note_type, note_text) VALUES (?, ?, ?)",
                (self._id(application_id, "application_id", True), note_type, note_text),
            )
            return int(cursor.lastrowid)

    def list_application_notes(self, application_id: int | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if application_id is None:
                return list(connection.execute("SELECT * FROM application_notes ORDER BY created_at DESC, id DESC"))
            return list(connection.execute("SELECT * FROM application_notes WHERE application_id=? ORDER BY created_at DESC, id DESC", (self._id(application_id, "application_id", True),)))

    def set_application_resume_version(self, application_id: int, resume_version_id: int | None,
                                      *, resume_document_id: int | None = None, template: str | None = None) -> None:
        with get_connection(self.database_path) as connection:
            connection.execute(
                "UPDATE applications SET resume_version_id=?, resume_document_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (
                    self._id(resume_version_id, "resume_version_id"),
                    self._id(resume_document_id, "resume_document_id"),
                    self._id(application_id, "application_id", True),
                ),
            )
            if resume_version_id is not None:
                connection.execute(
                    "INSERT OR IGNORE INTO application_resume_versions(application_id, resume_document_id, resume_version_id, template) VALUES (?, ?, ?, ?)",
                    (
                        self._id(application_id, "application_id", True),
                        self._id(resume_document_id, "resume_document_id"),
                        self._id(resume_version_id, "resume_version_id", True),
                        template,
                    ),
                )

    def delete_application(self, application_id: int) -> None:
        with get_connection(self.database_path) as connection:
            cursor = connection.execute("DELETE FROM applications WHERE id=?",
                                        (self._id(application_id, "application_id", True),))
            if cursor.rowcount == 0:
                raise ValueError("application not found")

    def save_job_analysis(self, job_id: int, analysis: dict[str, Any], provider: str = "mock") -> int:
        import json
        with get_connection(self.database_path) as connection:
            connection.execute("INSERT INTO job_analyses(job_id,analysis_json,provider) VALUES (?,?,?) ON CONFLICT(job_id,provider) DO UPDATE SET analysis_json=excluded.analysis_json,created_at=CURRENT_TIMESTAMP",
                               (job_id, json.dumps(analysis, sort_keys=True), provider))
            return int(connection.execute("SELECT id FROM job_analyses WHERE job_id=? AND provider=?", (job_id, provider)).fetchone()[0])

    def get_job_analysis(self, job_id: int) -> dict[str, Any] | None:
        import json
        with get_connection(self.database_path) as connection:
            row = connection.execute("SELECT analysis_json FROM job_analyses WHERE job_id=? ORDER BY id DESC LIMIT 1", (job_id,)).fetchone()
        return json.loads(row["analysis_json"]) if row else None

    def save_candidate_match(self, job_id: int, match: dict[str, Any]) -> int:
        import json
        with get_connection(self.database_path) as connection:
            connection.execute("INSERT INTO candidate_matches(job_id,match_json) VALUES (?,?) ON CONFLICT(job_id) DO UPDATE SET match_json=excluded.match_json,created_at=CURRENT_TIMESTAMP",
                               (job_id, json.dumps(match, sort_keys=True)))
            return int(connection.execute("SELECT id FROM candidate_matches WHERE job_id=?", (job_id,)).fetchone()[0])

    def create_resume_draft(self, title: str, content: dict[str, Any], source: str = "manual") -> int:
        import json
        with get_connection(self.database_path) as connection:
            cur = connection.execute("INSERT INTO resume_drafts(title,content_json,source) VALUES (?,?,?)",
                                     (self._text(title, "title", True), json.dumps(content, sort_keys=True), source))
            return int(cur.lastrowid)

    def list_resume_drafts(self) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            return list(connection.execute("SELECT * FROM resume_drafts ORDER BY updated_at DESC,id DESC"))

    def create_resume_document(self, title: str, *, document_type: str = "master",
                              candidate_profile_id: int | None = None, job_id: int | None = None,
                              template: str = "Professional", document_json: dict[str, Any] | None = None,
                              source: str = "master", version_label: str = "v1") -> int:
        import json
        payload = document_json or {}
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO resume_documents(title, document_type, candidate_profile_id, job_id, template, document_json, source, version_label) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self._text(title, "title", True),
                    document_type,
                    self._id(candidate_profile_id, "candidate_profile_id"),
                    self._id(job_id, "job_id"),
                    self._text(template, "template") or "Professional",
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    source,
                    version_label,
                ),
            )
            return int(cursor.lastrowid)

    def get_resume_document(self, document_id: int) -> sqlite3.Row | None:
        with get_connection(self.database_path) as connection:
            return connection.execute("SELECT * FROM resume_documents WHERE id = ?", (self._id(document_id, "document_id", True),)).fetchone()

    def list_resume_documents(self, *, document_type: str | None = None, job_id: int | None = None) -> list[sqlite3.Row]:
        clauses, params = [], []
        if document_type:
            clauses.append("document_type = ?")
            params.append(document_type)
        if job_id is not None:
            clauses.append("job_id = ?")
            params.append(self._id(job_id, "job_id", True))
        query = "SELECT * FROM resume_documents"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC, id DESC"
        with get_connection(self.database_path) as connection:
            return list(connection.execute(query, params))

    def update_resume_document(self, document_id: int, *, template: str | None = None,
                              document_json: dict[str, Any] | None = None,
                              title: str | None = None, version_label: str | None = None) -> int:
        import json
        if document_json is None and template is None and title is None and version_label is None:
            raise ValueError("no resume document update fields supplied")
        with get_connection(self.database_path) as connection:
            current = connection.execute("SELECT * FROM resume_documents WHERE id = ?", (self._id(document_id, "document_id", True),)).fetchone()
            if current is None:
                raise ValueError("resume document not found")
            update_template = template or current["template"]
            update_title = self._text(title, "title") or current["title"]
            update_label = self._text(version_label, "version_label") or current["version_label"]
            payload = document_json if document_json is not None else json.loads(current["document_json"] or "{}")
            connection.execute(
                "UPDATE resume_documents SET title = ?, template = ?, document_json = ?, version_label = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (update_title, update_template, json.dumps(payload, ensure_ascii=False, sort_keys=True), update_label, int(document_id)),
            )
            return int(document_id)

    def create_resume_version(self, document_id: int, *, version_label: str, title: str, template: str,
                             content_json: dict[str, Any]) -> int:
        import json
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO resume_versions(document_id, version_label, title, template, content_json) VALUES (?, ?, ?, ?, ?)",
                (self._id(document_id, "document_id", True), self._text(version_label, "version_label", True), self._text(title, "title", True), self._text(template, "template") or "Professional", json.dumps(content_json, ensure_ascii=False, sort_keys=True)),
            )
            return int(cursor.lastrowid)

    def list_resume_versions(self, document_id: int | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if document_id is None:
                return list(connection.execute("SELECT * FROM resume_versions ORDER BY created_at DESC, id DESC"))
            return list(connection.execute("SELECT * FROM resume_versions WHERE document_id = ? ORDER BY created_at DESC, id DESC", (self._id(document_id, "document_id", True),)))

    def save_resume_suggestion(self, document_id: int, *, original_content: str, suggested_content: str,
                               reason: str, related_job_requirement: str = "", evidence: str = "", status: str = "pending") -> int:
        with get_connection(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO resume_suggestion_items(document_id, original_content, suggested_content, reason, related_job_requirement, evidence, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    self._id(document_id, "document_id", True),
                    original_content,
                    suggested_content,
                    reason,
                    related_job_requirement,
                    evidence,
                    status,
                ),
            )
            return int(cursor.lastrowid)

    def list_resume_suggestions(self, document_id: int | None = None) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            if document_id is None:
                return list(connection.execute("SELECT * FROM resume_suggestion_items ORDER BY created_at DESC, id DESC"))
            return list(connection.execute("SELECT * FROM resume_suggestion_items WHERE document_id = ? ORDER BY created_at DESC, id DESC", (self._id(document_id, "document_id", True),)))

    def update_resume_suggestion_status(self, suggestion_id: int, status: str) -> None:
        allowed = {"pending", "accepted", "rejected"}
        if status not in allowed:
            raise ValueError("unsupported suggestion status")
        with get_connection(self.database_path) as connection:
            connection.execute("UPDATE resume_suggestion_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, self._id(suggestion_id, "suggestion_id", True)))

    def list_resume_templates(self) -> list[sqlite3.Row]:
        with get_connection(self.database_path) as connection:
            return list(connection.execute("SELECT * FROM resume_templates ORDER BY name"))

    def save_resume_suggestions(self, draft_id: int, suggestions: dict[str, Any]) -> int:
        import json
        with get_connection(self.database_path) as connection:
            cur = connection.execute("INSERT INTO resume_suggestions(draft_id,suggestion_json) VALUES (?,?)",
                                     (draft_id, json.dumps(suggestions, sort_keys=True)))
            return int(cur.lastrowid)

    def map_preparation_gaps(self, missing_terms: list[str]) -> list[sqlite3.Row]:
        """Map explicit missing keywords to existing learning topics only."""
        terms = [str(term).strip() for term in missing_terms if str(term).strip()]
        if not terms:
            return []
        clauses = " OR ".join("(t.name LIKE ? OR t.description LIKE ? OR m.name LIKE ?)" for _ in terms)
        params = [value for term in terms for value in (f"%{term}%",) * 3]
        with get_connection(self.database_path) as connection:
            return list(connection.execute(
                f"SELECT t.*,m.name AS module_name,c.name AS category_name FROM topics t "
                f"JOIN modules m ON m.id=t.module_id JOIN categories c ON c.id=m.category_id WHERE {clauses} "
                "ORDER BY c.sort_order,m.sort_order,t.sort_order", params))
