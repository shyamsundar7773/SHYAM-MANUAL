import tempfile
import unittest
from pathlib import Path

from data.database import initialize_database
from data.repositories import ContentRepository
from services.ai import build_ai_service
from ui.live_interview import _active_session, _session_dict, _session_meta


class LiveInterviewPhaseSevenTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "live.db"
        initialize_database(self.path)
        self.repo = ContentRepository(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_session_creation_persistence_and_resume(self):
        session = self.repo.create_interview_session({
            "role": "SQL Developer",
            "interview_type": "SQL Technical",
            "difficulty": "medium",
            "selected_topics": ["SQL", "Joins"],
            "question_count": 5,
            "status": "active",
            "metadata_json": {"mode": "Structured Interview", "question_ids": [1], "question_index": 0},
        })
        self.assertTrue(session["session_key"])
        self.assertEqual(self.repo.get_interview_session(session["session_key"])["role"], "SQL Developer")
        self.repo.add_interview_message(session["id"], "interviewer", "Explain INNER JOIN.")
        self.repo.add_interview_message(session["id"], "user", "It matches rows from both tables.")
        self.assertEqual(len(self.repo.list_interview_messages(session["id"])), 2)
        updated = self.repo.update_interview_session(session["id"], {"status": "paused"})
        self.assertEqual(updated["status"], "paused")

    def test_active_sqlite_row_is_normalized_for_voice_and_metadata(self):
        session = self.repo.create_interview_session({
            "role": "Non-Technical",
            "interview_type": "HR",
            "difficulty": "easy",
            "selected_topics": ["Business Analysis"],
            "question_count": 1,
            "status": "active",
            "metadata_json": {"mode": "Structured Interview", "question_ids": [], "question_index": 0},
        })
        active = _active_session(self.repo)
        self.assertIsInstance(active, dict)
        self.assertEqual(_session_meta(active)["mode"], "Structured Interview")
        self.assertFalse(bool(active.get("voice_mode") or _session_meta(active).get("voice_mode", False)))
        self.assertEqual(active["session_key"], session["session_key"])

        voice_session = self.repo.create_interview_session({
            "role": "Non-Technical",
            "interview_type": "Mixed",
            "difficulty": "medium",
            "selected_topics": ["Project"],
            "question_count": 1,
            "status": "paused",
            "voice_mode": True,
            "metadata_json": {"mode": "Mixed Interview", "voice_mode": True},
        })
        self.repo.update_interview_session(session["id"], {"status": "completed"})
        active_voice = _session_dict(self.repo.get_interview_session(voice_session["id"]))
        self.assertEqual(active_voice["session_key"], voice_session["session_key"])
        self.assertTrue(bool(active_voice.get("voice_mode") or _session_meta(active_voice).get("voice_mode", False)))

    def test_question_bank_and_ai_fallback_generation(self):
        service = build_ai_service()
        start = service.start_interview("SQL Developer", "SQL Technical", "medium", ["SQL", "Joins"], 5)
        self.assertEqual(start["status"], "ready")
        next_question = service.generate_next_question("SQL Developer", "SQL Technical", "medium", ["SQL"], ["Explain joins."], [])
        self.assertTrue(next_question["question"])
        follow_up = service.generate_follow_up("Explain joins.", "I return matching rows only.", "SQL Developer", "SQL Technical", "medium", ["Joins"])
        self.assertIn("how would your answer change", follow_up["question"].lower())

    def test_question_selection_uses_existing_content(self):
        rows = self.repo.build_interview_questions(
            role="SQL Developer",
            interview_type="SQL Technical",
            difficulty="easy",
            selected_topics=["SQL", "Joins"],
            question_count=3,
        )
        self.assertTrue(rows)
        self.assertLessEqual(len(rows), 3)
        self.assertTrue(all(row["question"] for row in rows))

    def test_job_and_resume_context_and_voice_fallback(self):
        self.repo.create_job({
            "source": "LinkedIn",
            "company": "Acme",
            "title": "SQL Developer",
            "description": "SQL and analytics role.",
            "requirements": "SQL, Python, ETL",
            "external_id": "job-101",
        })
        self.repo.create_resume_document("Resume v1", document_type="master")
        session = self.repo.create_interview_session({
            "role": "SQL Developer",
            "interview_type": "Job-Based",
            "difficulty": "medium",
            "selected_topics": ["SQL", "Project"],
            "question_count": 2,
            "status": "active",
            "mode": "Job Mode",
            "voice_mode": True,
            "job_id": 1,
            "resume_document_id": 1,
            "metadata_json": {"mode": "Job Mode", "voice_mode": True},
        })
        self.assertEqual(session["mode"], "Job Mode")
        self.assertEqual(int(session["voice_mode"]), 1)
        self.repo.add_interview_message(session["id"], "user", "I used SQL joins and data cleaning.", transcript_text="I used SQL joins and data cleaning.", voice_mode=True)
        service = build_ai_service()
        follow_up = service.generate_follow_up(
            "Explain your SQL approach.",
            "I used SQL joins and data cleaning.",
            "SQL Developer",
            "Job-Based",
            "medium",
            ["SQL"],
            job_context={"title": "SQL Developer", "company": "Acme"},
            context={"job": {"title": "SQL Developer", "company": "Acme"}},
        )
        self.assertIn("Acme", follow_up["question"])
        voice_transcript = service.transcribe_audio(text="I used SQL joins and data cleaning.")
        self.assertEqual(voice_transcript["status"], "available")
        self.assertTrue(service.synthesize_speech("Thanks for the answer.")["provider"] == "mock")


if __name__ == "__main__":
    unittest.main()
