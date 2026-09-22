import tempfile
import unittest
from pathlib import Path

from data.database import initialize_database
from data.repositories import ContentRepository
from data.seed_content import PROJECT_MODULES


class ProjectPracticalPhaseFiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "project.db"
        initialize_database(self.path)
        self.repo = ContentRepository(self.path)
        self.category = next(c for c in self.repo.list_categories() if c["slug"] == "project-practical")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_modules_topics_and_learning_templates(self):
        modules = self.repo.list_modules(self.category["id"])
        self.assertEqual([row["name"] for row in modules], list(PROJECT_MODULES))
        for module in modules:
            topics = self.repo.list_topics(module["id"])
            self.assertTrue(topics)
            self.assertTrue(self.repo.list_notes(topic_id=topics[0]["id"]))
            self.assertTrue(self.repo.list_examples(topic_id=topics[0]["id"]))

    def test_seed_is_idempotent_and_varied(self):
        before = (self.repo.count_questions(category_id=self.category["id"]),
                  len(self.repo.list_followups()))
        initialize_database(self.path)
        self.assertEqual(before, (self.repo.count_questions(category_id=self.category["id"]),
                                  len(self.repo.list_followups())))
        rows = self.repo.list_questions(category_id=self.category["id"])
        self.assertGreaterEqual(len(rows), 300)
        self.assertEqual(len({row["question"] for row in rows}), len(rows))
        self.assertTrue({"phase-5-seed", "project-explanation", "sql-practical"} <=
                        {row["source"] for row in rows} | {row["interview_style"] for row in rows})

    def test_metadata_crud_tags_and_combined_search_filter(self):
        module = self.repo.list_modules(self.category["id"])[0]
        topic = self.repo.list_topics(module["id"])[0]
        qid = self.repo.create_question({
            "category_id": self.category["id"], "module_id": module["id"], "topic_id": topic["id"],
            "question": "Project phase five CRUD check", "answer": "Template answer",
            "interviewer_expectation": "State the grain", "thinking_approach": "Validate assumptions",
            "interview_style": "data-quality", "difficulty": "hard", "source": "test",
            "tags": ["phase5", "quality"],
        })
        self.repo.update_question(qid, {"answer": "Updated answer", "completed": True,
                                        "tags": ["phase5", "updated"]})
        row = self.repo.get_question(qid)
        self.assertEqual(row["completed"], 1)
        self.assertEqual(self.repo.get_question_tags(qid), ["phase5", "updated"])
        found = self.repo.search_questions("Updated", category_id=self.category["id"],
                                           difficulty="hard", tags=["updated"])
        self.assertEqual([item["id"] for item in found], [qid])

    def test_practice_sets_cover_project_types_and_history(self):
        for style in ("project-explanation", "sql-practical", "business-scenario", "data-quality", "follow-up"):
            rows = self.repo.practice_set(category_id=self.category["id"], interview_type=style, size=3)
            self.assertTrue(rows, style)
            self.assertTrue(all(row["interview_style"] == style for row in rows))
        mixed = self.repo.practice_set(category_id=self.category["id"], difficulty="hard", size=12,
                                        randomize=True)
        self.assertTrue(mixed)
        attempt = self.repo.record_practice_attempt(mixed[0]["id"], source="project-practical",
                                                    interview_type="business-scenario")
        self.assertTrue(attempt)
        self.assertTrue(self.repo.list_practice_history(mixed[0]["id"]))


if __name__ == "__main__":
    unittest.main()
