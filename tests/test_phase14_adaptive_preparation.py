import tempfile
import unittest
from pathlib import Path

from data.database import initialize_database
from data.repositories import ContentRepository


class AdaptivePreparationPhaseFourteenTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "phase14.db"
        initialize_database(self.path)
        self.repo = ContentRepository(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_evaluation_to_weakness_and_recommendation_persistence(self):
        session = self.repo.create_interview_session({
            "role": "SQL Developer",
            "interview_type": "SQL Technical",
            "difficulty": "medium",
            "selected_topics": ["SQL", "Window Functions"],
            "question_count": 2,
            "status": "active",
        })
        self.repo.add_interview_message(session["id"], "interviewer", "Explain window functions.")
        self.repo.add_interview_message(session["id"], "user", "I can use row_number, but I am unsure about partitions.")
        evaluation = {
            "overall_summary": "Needs more practice with window functions.",
            "strengths": ["Understood basic SQL agility."],
            "weaknesses": ["Window Function understanding"],
            "key_observations": ["Window functions were weak."],
            "recommended_next_steps": ["Practice partitions and ranking functions."],
            "question_evaluations": [{
                "question": "Explain window functions.",
                "answer": "I can use row_number, but I am unsure about partitions.",
                "answer_completeness": "moderate",
                "relevance": "high",
                "clarity": "clear",
                "reasoning": "limited",
                "improvement_guidance": "Practice partitioning and window clauses with examples.",
                "source": "structured-fallback",
            }],
        }
        self.repo.save_interview_evaluation(session["id"], evaluation)
        self.repo.save_weakness(session["id"], {
            "name": "Window Function understanding",
            "description": "Need more practice with partitioning and ranking.",
            "evidence": "Candidate mentioned uncertainty around partitions.",
            "severity": "high",
            "category": "SQL",
        })
        self.repo.save_recommendation(session["id"], {
            "weakness": "Window Function understanding",
            "reason": "Practice window partitions and ranking functions.",
            "recommended_question": "Explain the difference between ROW_NUMBER and RANK.",
            "practice_objective": "Strengthen partitioning logic.",
            "priority": 2,
            "source": "structured-fallback",
        })

        rows = self.repo.list_weaknesses(session["id"])
        recs = self.repo.list_preparation_recommendations(session["id"])
        self.assertTrue(rows)
        self.assertTrue(recs)
        self.assertEqual(rows[0]["name"], "Window Function understanding")
        self.assertEqual(recs[0]["weakness_name"], "Window Function understanding")

    def test_recurring_weaknesses_and_job_readiness(self):
        session_1 = self.repo.create_interview_session({
            "role": "SQL Developer",
            "interview_type": "SQL Technical",
            "difficulty": "medium",
            "selected_topics": ["SQL"],
            "question_count": 1,
            "status": "completed",
        })
        session_2 = self.repo.create_interview_session({
            "role": "SQL Developer",
            "interview_type": "SQL Technical",
            "difficulty": "medium",
            "selected_topics": ["SQL"],
            "question_count": 1,
            "status": "completed",
        })
        job_id = self.repo.create_job({
            "source": "LinkedIn",
            "company": "Acme",
            "title": "SQL Developer",
            "external_id": "job-readiness-1",
            "description": "SQL role",
            "location": "Bengaluru",
        })
        self.repo.save_weakness(session_1["id"], {
            "name": "SQL JOIN reasoning",
            "description": "Needs more join clarity.",
            "evidence": "Missing join explanation.",
            "severity": "medium",
            "category": "SQL",
        })
        self.repo.save_weakness(session_2["id"], {
            "name": "SQL JOIN reasoning",
            "description": "Join reasoning remains incomplete.",
            "evidence": "Repeated weakness in second interview.",
            "severity": "high",
            "category": "SQL",
        })
        self.repo.set_job_readiness(job_id, "SQL JOIN reasoning", "needs-practice", "Repeated weakness across interviews.")
        self.repo.set_job_readiness(job_id, "Window Function understanding", "identified", "Candidate needs review.")

        historical = self.repo.list_weaknesses(session_1["id"])
        self.assertTrue(historical)
        self.assertGreaterEqual(len(self.repo.list_job_readiness(job_id)), 2)

    def test_interview_relationship_and_version_tracking(self):
        first = self.repo.create_interview_session({
            "role": "SQL Developer",
            "interview_type": "Job-Based",
            "difficulty": "hard",
            "selected_topics": ["SQL"],
            "question_count": 1,
            "status": "completed",
        })
        second = self.repo.create_interview_session({
            "role": "SQL Developer",
            "interview_type": "Job-Based",
            "difficulty": "hard",
            "selected_topics": ["SQL"],
            "question_count": 1,
            "status": "active",
        })
        job_id = self.repo.create_job({
            "source": "LinkedIn",
            "company": "Acme",
            "title": "SQL Developer",
            "external_id": "job-1",
            "description": "SQL role",
        })
        resume_doc = self.repo.create_resume_document("Resume v1", document_type="master")
        self.repo.update_interview_session(first["id"], {"job_id": job_id, "resume_document_id": resume_doc})
        self.repo.update_interview_session(second["id"], {"job_id": job_id, "resume_document_id": resume_doc})
        self.repo.save_interview_relationship(first["id"], second["id"], "reinterview")
        rels = self.repo.list_interview_relationships(first["id"])
        self.assertTrue(rels)
        self.assertEqual(rels[0]["relationship_type"], "reinterview")

    def test_weakness_topic_mapping_and_progress_tracking(self):
        mapping = self.repo.resolve_weakness_topic("Window Functions")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["category_slug"], "sql-technical-notes")
        event = self.repo.record_progress_event(
            event_type="interview",
            title="Interview weakness identified",
            description="Window function recall was weak in the SQL technical interview.",
            category="sql-technical-notes",
            related_record_type="interview_session",
            related_record_id=1,
            status="tracked",
        )
        self.assertEqual(event["title"], "Interview weakness identified")
        summary = self.repo.get_progress_summary()
        self.assertIn("events", summary)


if __name__ == "__main__":
    unittest.main()
