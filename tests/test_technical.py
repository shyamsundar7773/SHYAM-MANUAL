import tempfile
import unittest
from pathlib import Path

from data.database import initialize_database
from data.repositories import ContentRepository
from data.seed_content import TECHNICAL_MODULES


class TechnicalPhaseFourTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "technical.db"
        initialize_database(self.path)
        self.repo = ContentRepository(self.path)
        self.category = next(c for c in self.repo.list_categories() if c["slug"] == "technical-round")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_modules_topics_and_idempotent_seed(self):
        modules = self.repo.list_modules(self.category["id"])
        self.assertEqual([m["name"] for m in modules], list(TECHNICAL_MODULES))
        before = (self.repo.count_questions(category_id=self.category["id"]),
                  len(self.repo.list_followups()))
        initialize_database(self.path)
        self.assertEqual(before, (self.repo.count_questions(category_id=self.category["id"]),
                                  len(self.repo.list_followups())))
        self.assertTrue(all(self.repo.list_topics(m["id"]) for m in modules))

    def test_metadata_tags_search_filters_and_practice_history(self):
        question = self.repo.list_questions(category_id=self.category["id"], limit=1)[0]
        self.assertTrue(question["interviewer_expectation"])
        self.assertTrue(self.repo.search_questions("interviewer expects", category_id=self.category["id"]) or
                        self.repo.search_questions("NULL", category_id=self.category["id"]))
        self.assertTrue(self.repo.filter_questions(category_id=self.category["id"],
                                                   interview_style="technical"))
        attempt_id = self.repo.record_practice_attempt(question["id"], response="reasoned",
                                                        score=4, completed=True)
        self.assertTrue(attempt_id)
        self.assertTrue(self.repo.list_practice_history(question["id"]))
        self.assertEqual(self.repo.get_question(question["id"])["completed"], 1)

    def test_metadata_crud(self):
        module = self.repo.list_modules(self.category["id"])[0]
        topic = self.repo.list_topics(module["id"])[0]
        qid = self.repo.create_question({
            "category_id": self.category["id"], "module_id": module["id"], "topic_id": topic["id"],
            "question": "Metadata CRUD", "interviewer_expectation": "State the grain",
            "thinking_approach": "Plan, then validate", "sql_solution": "SELECT 1",
            "alternative_solution": "Use a CTE", "common_trap": "Duplicate rows",
            "interview_style": "technical", "source": "test", "tags": ["phase4"],
        })
        self.repo.update_question(qid, {"common_trap": "NULL handling", "completed": True})
        row = self.repo.get_question(qid)
        self.assertEqual(row["common_trap"], "NULL handling")
        self.assertEqual(row["completed"], 1)


if __name__ == "__main__":
    unittest.main()
