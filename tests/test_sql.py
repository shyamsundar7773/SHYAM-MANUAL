import tempfile
import unittest
from pathlib import Path

from data.database import initialize_database
from data.repositories import ContentRepository


class SQLPhaseThreeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "sql.db"
        initialize_database(self.path)
        self.repo = ContentRepository(self.path)
        self.category = next(c for c in self.repo.list_categories() if c["slug"] == "sql-technical-notes")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_modules_topics_and_idempotence(self):
        modules = self.repo.list_modules(self.category["id"])
        self.assertEqual(len(modules), 18)
        self.assertTrue(all(self.repo.list_topics(m["id"]) for m in modules))
        counts = (len(modules), self.repo.count_questions(), len(self.repo.list_notes()),
                  len(self.repo.list_examples()), len(self.repo.list_tricks()), len(self.repo.list_followups()))
        initialize_database(self.path)
        after = (len(self.repo.list_modules(self.category["id"])), self.repo.count_questions(),
                 len(self.repo.list_notes()), len(self.repo.list_examples()),
                 len(self.repo.list_tricks()), len(self.repo.list_followups()))
        self.assertEqual(counts, after)

    def test_learning_retrieval_search_and_question_crud(self):
        module = self.repo.list_modules(self.category["id"])[0]
        topic = self.repo.list_topics(module["id"])[0]
        self.assertTrue(self.repo.list_notes(topic_id=topic["id"]))
        self.assertTrue(self.repo.list_examples(topic_id=topic["id"]))
        self.assertTrue(self.repo.list_tricks(topic_id=topic["id"]))
        self.assertTrue(self.repo.list_followups(topic_id=topic["id"]))
        self.assertTrue(self.repo.search_content("MySQL", module_id=module["id"]))
        question_id = self.repo.create_question({
            "category_id": self.category["id"], "module_id": module["id"], "topic_id": topic["id"],
            "question": "Custom SQL question", "question_type": "technical", "difficulty": "hard",
            "tags": ["sql", "custom"],
        })
        self.assertEqual(self.repo.get_question_tags(question_id), ["custom", "sql"])
        self.assertEqual(self.repo.filter_questions(module_id=module["id"], topic_id=topic["id"],
                                                    difficulty="hard", question_type="technical")[0]["id"], question_id)
        self.assertTrue(self.repo.search_content("Custom SQL", topic_id=topic["id"]))
        self.repo.delete_question(question_id)

    def test_filtered_counts_and_pagination_use_database_filters(self):
        module = self.repo.list_modules(self.category["id"])[0]
        topic = self.repo.list_topics(module["id"])[0]
        hard_count = self.repo.count_questions(category_id=self.category["id"], difficulty="hard")
        rows = self.repo.list_questions(category_id=self.category["id"], difficulty="hard",
                                         limit=5, offset=5)
        self.assertEqual(len(rows), min(5, max(0, hard_count - 5)))
        self.assertTrue(all(row["category_name"] == self.category["name"] for row in rows))
        self.assertTrue(all(row["difficulty"] == "hard" for row in rows))
        topic_count = self.repo.count_questions(category_id=self.category["id"],
                                                 module_id=module["id"], topic_id=topic["id"])
        self.assertEqual(topic_count, len(self.repo.list_questions(
            category_id=self.category["id"], module_id=module["id"], topic_id=topic["id"])))
        self.assertTrue(self.repo.list_question_types(self.category["id"]))


if __name__ == "__main__":
    unittest.main()
