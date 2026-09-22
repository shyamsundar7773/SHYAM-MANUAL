"""SQLite connection and schema initialization."""

from contextlib import contextmanager
import logging
from pathlib import Path
import sqlite3
from typing import Iterator

from data.seed_content import seed_content

LOGGER = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Raised when the local database cannot be prepared or queried."""


@contextmanager
def get_connection(database_path: Path | str) -> Iterator[sqlite3.Connection]:
    path = Path(database_path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise DatabaseError(f"Database operation failed: {exc}") from exc
        finally:
            connection.close()
    except OSError as exc:
        LOGGER.exception("Database filesystem operation failed for %s", path)
        raise DatabaseError(f"Database path is not writable: {path}") from exc
    except sqlite3.Error as exc:
        LOGGER.exception("Database connection failed for %s", path)
        raise DatabaseError(f"Database connection failed: {exc}") from exc


def initialize_database(database_path: Path | str) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    try:
        schema = schema_path.read_text(encoding="utf-8")
        with get_connection(database_path) as connection:
            connection.executescript(schema)
            migrate_questions(connection)
            migrate_tricks(connection)
            migrate_jobs_resume(connection)
            migrate_resume_studio(connection)
            migrate_application_command_center(connection)
            migrate_live_interview(connection)
            migrate_phase13_voice_interview(connection)
            migrate_phase14_adaptive_preparation(connection)
            migrate_phase8_evaluation(connection)
            seed_categories(connection)
            seed_content(connection)
    except (OSError, sqlite3.Error, DatabaseError) as exc:
        if isinstance(exc, DatabaseError):
            raise
        LOGGER.exception("Database initialization failed for %s", database_path)
        raise DatabaseError(f"Database initialization failed: {exc}") from exc


def seed_categories(connection: sqlite3.Connection) -> None:
    categories = (
        ("HR Screening", "hr-screening", "Behavioral and HR preparation.", 1),
        ("SQL Technical Notes", "sql-technical-notes", "SQL concepts and practice notes.", 2),
        ("Technical Round", "technical-round", "Core technical interview preparation.", 3),
        ("Project & Practical", "project-practical", "Project discussion and practical scenarios.", 4),
        ("Jobs + Resume", "jobs-resume", "Job and resume preparation foundation.", 5),
        ("Non-Technical + Live Interview", "non-technical-live-interview", "Communication and live interview preparation.", 6),
        ("20-Day Mission", "20-day-mission", "Reserved for the future mission planner.", 7),
        ("Progress", "progress", "Reserved for future progress tracking.", 8),
    )
    connection.executemany(
        """
        INSERT INTO categories (name, slug, description, sort_order)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET description = excluded.description, sort_order = excluded.sort_order
        """,
        categories,
    )


def migrate_questions(connection: sqlite3.Connection) -> None:
    """Apply additive schema changes without disturbing existing Phase 0/1 data."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(questions)")}
    additions = {
        "personal_answer": "TEXT",
        "interviewer_expectation": "TEXT",
        "thinking_approach": "TEXT",
        "sql_solution": "TEXT",
        "alternative_solution": "TEXT",
        "common_trap": "TEXT",
        "interview_style": "TEXT",
        "source": "TEXT",
        "completed": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, type_sql in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE questions ADD COLUMN {name} {type_sql}")

    history_columns = {row[1] for row in connection.execute("PRAGMA table_info(interview_history)")}
    for name, type_sql in {
        "source": "TEXT",
        "completed": "INTEGER NOT NULL DEFAULT 0",
        "interview_type": "TEXT",
    }.items():
        if name not in history_columns:
            connection.execute(f"ALTER TABLE interview_history ADD COLUMN {name} {type_sql}")


def migrate_tricks(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(tricks)")}
    if "topic_id" not in columns:
        connection.execute("ALTER TABLE tricks ADD COLUMN topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE")


def migrate_jobs_resume(connection: sqlite3.Connection) -> None:
    """Add Phase 6 fields while preserving databases created by earlier phases."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
    additions = {
        "remote_type": "TEXT",
        "responsibilities": "TEXT",
        "education": "TEXT",
        "required_skills": "TEXT",
        "sql_requirements": "TEXT",
        "sql": "TEXT",
        "tools": "TEXT",
        "source_metadata": "TEXT",
        "metadata": "TEXT",
        "preferred_skills": "TEXT",
        "salary": "TEXT",
    }
    for name, type_sql in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE jobs ADD COLUMN {name} {type_sql}")

    profile_columns = {row[1] for row in connection.execute("PRAGMA table_info(candidate_profiles)")}
    for name in (
        "projects", "preferred_roles", "preferred_locations", "experience_level", "availability",
        "resume_information", "additional_information",
    ):
        if name not in profile_columns:
            connection.execute(f"ALTER TABLE candidate_profiles ADD COLUMN {name} TEXT")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_search ON jobs(source, posting_date, remote_type)")


def migrate_resume_studio(connection: sqlite3.Connection) -> None:
    """Add Phase 11 resume-studio data tables without disturbing earlier phases."""
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "resume_documents" not in tables:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                document_type TEXT NOT NULL DEFAULT 'master',
                candidate_profile_id INTEGER,
                job_id INTEGER,
                template TEXT NOT NULL DEFAULT 'Professional',
                document_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL DEFAULT 'master',
                version_label TEXT NOT NULL DEFAULT 'v1',
                FOREIGN KEY(candidate_profile_id) REFERENCES candidate_profiles(id) ON DELETE SET NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE SET NULL
            )
            """
        )
    if "resume_suggestion_items" not in tables:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_suggestion_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES resume_documents(id) ON DELETE CASCADE,
                original_content TEXT,
                suggested_content TEXT,
                reason TEXT,
                related_job_requirement TEXT,
                evidence TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    if "resume_versions" not in tables:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES resume_documents(id) ON DELETE CASCADE,
                version_label TEXT NOT NULL,
                title TEXT NOT NULL,
                template TEXT NOT NULL DEFAULT 'Professional',
                content_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    if "resume_templates" not in tables:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS resume_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO resume_templates(name, description, active) VALUES (?, ?, ?)",
            [
                ("Professional", "Standard professional resume structure.", 1),
                ("Modern", "Modern, polished, and contemporary layout.", 1),
                ("ATS", "ATS-friendly and structured for easy parsing.", 1),
                ("Minimal", "Clean, compact, and concise resume format.", 1),
                ("Technical", "Technical resume with a stronger skills-first structure.", 1),
            ],
        )


def migrate_application_command_center(connection: sqlite3.Connection) -> None:
    """Add Phase 12 application lifecycle and resume-version tracking in an additive way."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(applications)")}
    additions = {
        "candidate_profile_id": "INTEGER REFERENCES candidate_profiles(id) ON DELETE SET NULL",
        "resume_document_id": "INTEGER REFERENCES resume_documents(id) ON DELETE SET NULL",
        "resume_version_id": "INTEGER REFERENCES resume_versions(id) ON DELETE SET NULL",
        "official_application_url": "TEXT",
        "source_url": "TEXT",
        "application_method": "TEXT DEFAULT 'external'",
        "confirmed_submitted": "INTEGER NOT NULL DEFAULT 0",
        "metadata_json": "TEXT DEFAULT '{}'",
    }
    for name, type_sql in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE applications ADD COLUMN {name} {type_sql}")

    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "application_notes" not in tables:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                note_type TEXT NOT NULL DEFAULT 'general',
                note_text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    if "application_resume_versions" not in tables:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS application_resume_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                resume_document_id INTEGER REFERENCES resume_documents(id) ON DELETE SET NULL,
                resume_version_id INTEGER REFERENCES resume_versions(id) ON DELETE SET NULL,
                template TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(application_id, resume_version_id)
            )
            """
        )


def migrate_live_interview(connection: sqlite3.Connection) -> None:
    """Add Phase 7 interview session tables while preserving older databases."""
    session_columns = {row[1] for row in connection.execute("PRAGMA table_info(interview_sessions)")}
    if not session_columns:
        return

    additions = {
        "session_key": "TEXT",
        "role": "TEXT",
        "interview_type": "TEXT",
        "difficulty": "TEXT",
        "selected_topics": "TEXT",
        "question_count": "INTEGER DEFAULT 5",
        "status": "TEXT DEFAULT 'not_started'",
        "current_question": "INTEGER DEFAULT 0",
        "completed_questions": "INTEGER DEFAULT 0",
        "started_at": "TEXT",
        "ended_at": "TEXT",
        "candidate_profile_id": "INTEGER",
        "job_id": "INTEGER",
        "metadata_json": "TEXT DEFAULT '{}'",
    }
    for name, type_sql in additions.items():
        if name not in session_columns:
            connection.execute(f"ALTER TABLE interview_sessions ADD COLUMN {name} {type_sql}")

    message_columns = {row[1] for row in connection.execute("PRAGMA table_info(interview_messages)")}
    for name, type_sql in {
        "source_question_id": "INTEGER",
        "follow_up": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        if name not in message_columns:
            connection.execute(f"ALTER TABLE interview_messages ADD COLUMN {name} {type_sql}")

    existing = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interview_sessions'").fetchone()
    if existing is None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key TEXT NOT NULL UNIQUE,
                role TEXT NOT NULL,
                interview_type TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                selected_topics TEXT,
                question_count INTEGER NOT NULL DEFAULT 5,
                status TEXT NOT NULL DEFAULT 'not_started',
                current_question INTEGER NOT NULL DEFAULT 0,
                completed_questions INTEGER NOT NULL DEFAULT 0,
                started_at TEXT,
                ended_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                candidate_profile_id INTEGER REFERENCES candidate_profiles(id) ON DELETE SET NULL,
                job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
                metadata_json TEXT DEFAULT '{}'
            )
            """
        )

    existing_messages = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interview_messages'").fetchone()
    if existing_messages is None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interview_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
                speaker TEXT NOT NULL CHECK (speaker IN ('interviewer', 'user', 'system')),
                message TEXT NOT NULL,
                question_id INTEGER REFERENCES questions(id) ON DELETE SET NULL,
                source_question_id INTEGER REFERENCES questions(id) ON DELETE SET NULL,
                follow_up INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def migrate_phase13_voice_interview(connection: sqlite3.Connection) -> None:
    """Add Phase 13 voice and context metadata while keeping text interviews working."""
    session_columns = {row[1] for row in connection.execute("PRAGMA table_info(interview_sessions)")}
    additions = {
        "mode": "TEXT DEFAULT 'Structured Interview'",
        "voice_mode": "INTEGER NOT NULL DEFAULT 0",
        "voice_provider": "TEXT DEFAULT 'mock'",
        "tts_provider": "TEXT DEFAULT 'mock'",
        "resume_document_id": "INTEGER REFERENCES resume_documents(id) ON DELETE SET NULL",
        "resume_version_id": "INTEGER REFERENCES resume_versions(id) ON DELETE SET NULL",
        "application_id": "INTEGER REFERENCES applications(id) ON DELETE SET NULL",
        "session_context_json": "TEXT DEFAULT '{}'",
        "voice_config_json": "TEXT DEFAULT '{}'",
    }
    for name, type_sql in additions.items():
        if name not in session_columns:
            connection.execute(f"ALTER TABLE interview_sessions ADD COLUMN {name} {type_sql}")
    message_columns = {row[1] for row in connection.execute("PRAGMA table_info(interview_messages)")}
    for name, type_sql in {
        "transcript_text": "TEXT",
        "voice_mode": "INTEGER NOT NULL DEFAULT 0",
    }.items():
        if name not in message_columns:
            connection.execute(f"ALTER TABLE interview_messages ADD COLUMN {name} {type_sql}")


def migrate_phase14_adaptive_preparation(connection: sqlite3.Connection) -> None:
    """Add adaptive preparation tables for repeated weaknesses, recency, and job-specific readiness."""
    for table_name, ddl in {
        "weakness_records": """
            CREATE TABLE IF NOT EXISTS weakness_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER REFERENCES interview_sessions(id) ON DELETE SET NULL,
                evaluation_id INTEGER REFERENCES interview_evaluations(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                severity TEXT NOT NULL DEFAULT 'medium',
                evidence TEXT,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'identified',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, name)
            )
        """,
        "weakness_history": """
            CREATE TABLE IF NOT EXISTS weakness_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weakness_name TEXT NOT NULL,
                session_id INTEGER REFERENCES interview_sessions(id) ON DELETE SET NULL,
                status TEXT NOT NULL DEFAULT 'identified',
                evidence TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(weakness_name, session_id)
            )
        """,
        "preparation_recommendations": """
            CREATE TABLE IF NOT EXISTS preparation_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER REFERENCES interview_sessions(id) ON DELETE SET NULL,
                weakness_name TEXT NOT NULL,
                title TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'important',
                action TEXT NOT NULL DEFAULT 'Practice Now',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, weakness_name, title)
            )
        """,
        "interview_relationships": """
            CREATE TABLE IF NOT EXISTS interview_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                interview_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
                related_interview_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
                relationship_type TEXT NOT NULL DEFAULT 'reinterview',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(interview_id, related_interview_id, relationship_type)
            )
        """,
        "job_readiness": """
            CREATE TABLE IF NOT EXISTS job_readiness (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                area_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                evidence TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(job_id, area_name)
            )
        """,
        "weakness_topic_mappings": """
            CREATE TABLE IF NOT EXISTS weakness_topic_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weakness_name TEXT NOT NULL,
                category TEXT,
                category_slug TEXT,
                module_name TEXT,
                topic_name TEXT,
                reason TEXT,
                recommendation TEXT,
                severity TEXT NOT NULL DEFAULT 'medium',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(weakness_name, category_slug, module_name, topic_name)
            )
        """,
        "progress_events": """
            CREATE TABLE IF NOT EXISTS progress_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL DEFAULT 'preparation',
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                related_record_type TEXT,
                related_record_id INTEGER,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """,
    }.items():
        connection.execute(ddl)


def migrate_phase8_evaluation(connection: sqlite3.Connection) -> None:
    """Add Phase 8 interview evaluation, weakness, recommendation, and mission tables."""
    for table_name, ddl in {
        "interview_evaluations": """
            CREATE TABLE IF NOT EXISTS interview_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL UNIQUE REFERENCES interview_sessions(id) ON DELETE CASCADE,
                overall_summary TEXT,
                strengths TEXT,
                weaknesses TEXT,
                key_observations TEXT,
                recommended_next_steps TEXT,
                evaluation_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """,
        "interview_weaknesses": """
            CREATE TABLE IF NOT EXISTS interview_weaknesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER REFERENCES interview_evaluations(id) ON DELETE CASCADE,
                session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT,
                evidence TEXT,
                question_id INTEGER REFERENCES questions(id) ON DELETE SET NULL,
                confidence TEXT DEFAULT 'medium',
                severity TEXT DEFAULT 'medium',
                category TEXT DEFAULT 'general',
                source TEXT DEFAULT 'structured-fallback',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, name)
            )
        """,
        "interview_recommendations": """
            CREATE TABLE IF NOT EXISTS interview_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id INTEGER REFERENCES interview_evaluations(id) ON DELETE CASCADE,
                session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
                weakness TEXT NOT NULL,
                reason TEXT,
                recommended_question TEXT,
                practice_objective TEXT,
                priority INTEGER NOT NULL DEFAULT 1,
                source TEXT DEFAULT 'structured-fallback',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, weakness)
            )
        """,
        "mission_adaptations": """
            CREATE TABLE IF NOT EXISTS mission_adaptations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
                weakness_name TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium',
                reason TEXT,
                topic_name TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, weakness_name)
            )
        """,
    }.items():
        connection.execute(ddl)
