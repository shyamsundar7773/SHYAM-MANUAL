import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.settings import get_settings
from data.database import get_connection, initialize_database
from data.repositories import ContentRepository
from services.ai import AIService, MockAIProvider, build_ai_service
from services.jobs import JobFetcher


class FoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_connection_and_schema_creation(self) -> None:
        with get_connection(self.database_path) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue({"categories", "modules", "topics", "questions", "jobs"} <= tables)

    def test_seeded_categories_are_retrievable(self) -> None:
        categories = ContentRepository(self.database_path).list_categories()
        self.assertEqual(len(categories), 8)
        self.assertEqual(categories[0]["name"], "HR Screening")

    def test_phase_two_seed_content_and_idempotence(self) -> None:
        repository = ContentRepository(self.database_path)
        hr = next(row for row in repository.list_categories() if row["slug"] == "hr-screening")
        live = next(row for row in repository.list_categories()
                    if row["slug"] == "non-technical-live-interview")
        self.assertGreaterEqual(len(repository.list_modules(hr["id"])), 1)
        self.assertGreaterEqual(len(repository.list_modules(live["id"])), 1)
        before = repository.count_questions()
        hr_modules = {row["name"] for row in repository.list_modules(hr["id"])}
        self.assertEqual(hr_modules, {
            "Self Introduction", "Project Introduction", "Project Deep Dive",
            "Tricky Project Questions", "HR Follow-ups", "Career & Motivation",
        })
        self.assertEqual(
            len(repository.list_topics(next(row["id"] for row in repository.list_modules(hr["id"])
                                          if row["name"] == "Self Introduction"))),
            11,
        )
        live_modules = {row["name"] for row in repository.list_modules(live["id"])}
        self.assertIn("Handling Unknown Questions", live_modules)
        self.assertIn("Behavioural Follow-ups", live_modules)
        initialize_database(self.database_path)
        self.assertEqual(repository.count_questions(), before)
        self.assertEqual(repository.count_questions(), before)
        self.assertTrue(repository.search_questions("truthful"))
        self.assertTrue(repository.search_questions("follow-up"))

    def test_module_topic_relationships_and_question_crud(self) -> None:
        with get_connection(self.database_path) as connection:
            category_id = connection.execute(
                "SELECT id FROM categories WHERE slug = 'sql-technical-notes'"
            ).fetchone()[0]
            module_id = connection.execute(
                "INSERT INTO modules (category_id, name, slug) VALUES (?, ?, ?)",
                (category_id, "Joins Test", "joins-test"),
            ).lastrowid
            topic_id = connection.execute(
                "INSERT INTO topics (module_id, name, slug) VALUES (?, ?, ?)",
                (module_id, "Inner Join", "inner-join"),
            ).lastrowid
        repository = ContentRepository(self.database_path)
        question_id = repository.create_question({
            "category_id": category_id,
            "module_id": module_id,
            "topic_id": topic_id,
            "question": "What is an inner join?",
        })
        question = repository.get_question(question_id)
        self.assertEqual(question["topic_id"], topic_id)

    def test_configuration_defaults_without_provider(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = get_settings()
        self.assertEqual(settings.ai_provider, "mock")
        self.assertIsNone(settings.ai_api_key)

    def test_safe_ai_provider_and_job_fetcher(self) -> None:
        service = build_ai_service("missing-provider")
        self.assertIsInstance(service, AIService)
        self.assertIn("not configured", service.generate("test"))
        self.assertIsInstance(MockAIProvider(), MockAIProvider)
        self.assertEqual(JobFetcher().fetch_all(), [])


if __name__ == "__main__":
    unittest.main()
