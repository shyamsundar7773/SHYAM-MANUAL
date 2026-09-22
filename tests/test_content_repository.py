import tempfile
import unittest
from pathlib import Path

from data.database import get_connection, initialize_database
from data.repositories import ContentRepository


class ContentRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "content.db"
        initialize_database(self.path)
        self.repository = ContentRepository(self.path)
        self.category = next(row for row in self.repository.list_categories()
                             if row["slug"] == "sql-technical-notes")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_category_module_topic_crud(self):
        module_id = self.repository.create_module({"category_id": self.category["id"], "name": "Python"})
        topic_id = self.repository.create_topic({"module_id": module_id, "name": "Iterators"})
        self.assertEqual(self.repository.list_modules(self.category["id"])[0]["name"], "Python")
        self.assertEqual(self.repository.list_topics(module_id)[0]["name"], "Iterators")
        self.repository.update_topic(topic_id, {"module_id": module_id, "name": "Generators"})
        self.assertEqual(self.repository.list_topics(module_id)[0]["name"], "Generators")
        self.repository.delete_topic(topic_id)
        self.assertEqual(self.repository.list_topics(module_id), [])

    def test_question_crud_search_filters_and_recent(self):
        before = self.repository.count_questions(category_id=self.category["id"])
        question_id = self.repository.create_question({
            "category_id": self.category["id"], "question": "Explain indexing",
            "answer": "Indexes speed lookups.", "difficulty": "hard",
            "tags": ["database", "performance"],
        })
        self.assertEqual(self.repository.count_questions(category_id=self.category["id"]), before + 1)
        self.assertEqual(self.repository.list_questions(search="indexing")[0]["id"], question_id)
        self.assertEqual(self.repository.list_questions(difficulty="hard")[0]["id"], question_id)
        self.assertEqual(self.repository.list_questions(category_id=self.category["id"],
                                                         sort_by="created_at", limit=1)[0]["id"], question_id)
        self.repository.update_question(question_id, {"question": "Explain query indexing", "tags": "database, sql"})
        self.assertEqual(self.repository.get_question(question_id)["question"], "Explain query indexing")
        self.assertEqual(self.repository.get_question_tags(question_id), ["database", "sql"])
        self.repository.delete_question(question_id)
        self.assertEqual(self.repository.count_questions(category_id=self.category["id"]), before)

    def test_invalid_question_is_rejected(self):
        with self.assertRaises(ValueError):
            self.repository.create_question({"category_id": self.category["id"], "question": " "})
        with self.assertRaises(ValueError):
            self.repository.create_question({"category_id": "bad", "question": "Question"})

    def test_tag_filter_requires_all_tags(self):
        first = self.repository.create_question({
            "category_id": self.category["id"], "question": "One", "tags": ["a", "b"],
        })
        self.repository.create_question({
            "category_id": self.category["id"], "question": "Two", "tags": ["a"],
        })
        rows = self.repository.list_questions(tags=["a", "b"])
        self.assertEqual([row["id"] for row in rows], [first])
        self.assertEqual([row["name"] for row in self.repository.list_tags() if row["name"] in {"a", "b"}],
                         ["a", "b"])

    def test_search_matches_topic_category_and_tag_case_insensitively(self):
        module_id = self.repository.create_module({"category_id": self.category["id"], "name": "SQL Joins"})
        topic_id = self.repository.create_topic({"module_id": module_id, "name": "Inner Join"})
        question_id = self.repository.create_question({
            "category_id": self.category["id"], "module_id": module_id, "topic_id": topic_id,
            "question": "How does this work?", "tags": ["Relational"],
        })
        self.assertEqual(self.repository.search_questions("inner join")[0]["id"], question_id)
        self.assertEqual(self.repository.search_questions("RELATIONAL")[0]["id"], question_id)
        self.assertEqual(self.repository.search_questions(self.category["name"].lower())[0]["id"], question_id)

    def test_combined_filters(self):
        module_id = self.repository.create_module({"category_id": self.category["id"], "name": "SQL"})
        topic_id = self.repository.create_topic({"module_id": module_id, "name": "Joins"})
        question_id = self.repository.create_question({
            "category_id": self.category["id"], "module_id": module_id, "topic_id": topic_id,
            "question": "Join question", "difficulty": "medium", "question_type": "technical",
        })
        self.repository.create_question({
            "category_id": self.category["id"], "module_id": module_id, "topic_id": topic_id,
            "question": "Other question", "difficulty": "easy", "question_type": "technical",
        })
        rows = self.repository.filter_questions(category_id=self.category["id"], module_id=module_id,
                                                 topic_id=topic_id, difficulty="medium",
                                                 question_type="technical")
        self.assertEqual([row["id"] for row in rows], [question_id])

    def test_personal_answer_and_followup_search(self):
        question_id = self.repository.create_question({
            "category_id": self.category["id"], "question": "Tell me about your approach",
            "answer": "Use a structure.", "personal_answer": "I will use [my example].",
            "follow_up": "What did you learn?", "tags": ["behavioral"],
        })
        question = self.repository.get_question(question_id)
        self.assertEqual(question["personal_answer"], "I will use [my example].")
        self.assertEqual(self.repository.search_questions("learn")[0]["id"], question_id)
        self.repository.update_question(question_id, {"personal_answer": "Updated [truthful example]."})
        self.assertEqual(self.repository.get_question(question_id)["personal_answer"],
                         "Updated [truthful example].")


if __name__ == "__main__":
    unittest.main()
