import tempfile
import unittest
from pathlib import Path

from data.database import initialize_database
from data.repositories import ContentRepository
from services.ai import MockAIProvider, build_ai_service
from services.jobs import EmptyJobSource, Job, JobFetcher, compare_job_to_candidate, normalize_jobs
from services.resume_studio import (
    compare_resume_to_job,
    export_resume_pdf_bytes,
    get_default_master_resume,
    get_template_names,
)


class JobsResumePhaseSixTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "jobs.db"
        initialize_database(self.path)
        self.repo = ContentRepository(self.path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_candidate_profile_and_master_resume_persist(self):
        self.repo.save_candidate_profile({
            "skills": "SQL, Python", "preferred_roles": "Data Analyst",
            "experience_level": "entry", "availability": "Immediately",
        })
        profile = self.repo.get_candidate_profile()
        self.assertEqual(profile["skills"], "SQL, Python")
        self.assertEqual(profile["preferred_roles"], "Data Analyst")
        draft = self.repo.create_resume_draft("Master", {"skills": profile["skills"]})
        self.assertTrue(any(row["id"] == draft for row in self.repo.list_resume_drafts()))

    def test_job_normalization_provider_empty_and_deduplication(self):
        jobs = normalize_jobs([
            Job(external_id="1", source="Example", company="Acme", title="Analyst"),
            Job(external_id="1", source="Example", company="Acme", title="Analyst"),
        ])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(JobFetcher([EmptyJobSource()]).fetch_all(), [])
        job_id = self.repo.create_job(jobs[0].as_record())
        self.assertEqual(self.repo.create_job(jobs[0].as_record()), job_id)
        self.assertEqual(len(self.repo.list_jobs()), 1)

    def test_safe_analysis_matching_and_gap_mapping(self):
        service = build_ai_service("mock")
        analysis = service.analyze_job("SQL and Window Functions required.", {"skills": "SQL"})
        self.assertTrue(analysis["available"])
        self.assertIn("inferred", analysis)
        match = service.match_candidate("SQL and Window Functions required.", {"skills": "SQL"})
        self.assertIn("SQL", match["matched"])
        self.assertEqual(match["inferred"], [])
        self.assertTrue(self.repo.map_preparation_gaps(["Window Functions"]))

    def test_application_history_and_analysis_persistence(self):
        job_id = self.repo.create_job({"source": "manual", "company": "Acme", "title": "Analyst"})
        self.repo.save_job(job_id)
        app_id = self.repo.upsert_application(job_id, "saved", notes="Review")
        self.repo.upsert_application(job_id, "applied")
        self.assertEqual(len(self.repo.list_application_history(app_id)), 2)
        self.repo.save_job_analysis(job_id, {"available": False, "explicit": [], "inferred": []})
        self.assertFalse(self.repo.get_job_analysis(job_id)["available"])

    def test_mock_provider_does_not_fabricate(self):
        result = MockAIProvider().analyze_job("We need a certified analyst.", {})
        self.assertEqual(result["inferred"], [])
        self.assertIn("unverified", result)

    def test_job_radar_filters_pagination_and_idempotent_identity(self):
        for index in range(3):
            self.repo.create_job({
                "external_id": str(index), "source": "Manual URL / Manual Job Entry",
                "company": "Acme", "title": f"SQL Developer {index}",
                "location": "Bengaluru", "remote_type": "hybrid",
            })
        self.assertEqual(self.repo.count_jobs("SQL", location="Bengaluru", remote_type="hybrid"), 3)
        page = self.repo.list_jobs("SQL", location="Bengaluru", remote_type="hybrid", limit=2, offset=2)
        self.assertEqual(len(page), 1)
        duplicate = self.repo.create_job({
            "external_id": "0", "source": "Manual URL / Manual Job Entry",
            "company": "Acme", "title": "SQL Developer updated",
        })
        self.assertEqual(len(self.repo.list_jobs()), 3)
        self.assertEqual(self.repo.get_job(duplicate)["title"], "SQL Developer updated")

    def test_job_intelligence_preserves_unclear_as_unclear(self):
        job = {"title": "SQL Developer", "requirements": "SQL Power BI ETL", "skills": "Python"}
        match = compare_job_to_candidate(job, {"skills": "SQL", "tools": "Python"})
        self.assertIn("sql", match["matched"])
        self.assertIn("power", match["unclear"])
        self.assertEqual(match["missing"], [])

    def test_source_checks_and_notifications_are_idempotent(self):
        self.repo.record_job_source_check("LinkedIn", "unavailable", 0, "not configured")
        self.repo.record_job_source_check("LinkedIn", "unavailable", 0, "not configured")
        self.assertEqual(len(self.repo.list_job_source_checks()), 1)
        job_id = self.repo.create_job({"source": "manual", "company": "Acme", "title": "Analyst"})
        first = self.repo.create_job_notification(job_id, "NEW_MATCHING_JOB")
        second = self.repo.create_job_notification(job_id, "NEW_MATCHING_JOB")
        self.assertEqual(first, second)
        self.assertEqual(len(self.repo.list_job_notifications(pending_only=True)), 1)

    def test_source_capabilities_and_duplicate_fallback_are_safe(self):
        from services.jobs import get_job_source_adapter, normalize_job

        adapter = get_job_source_adapter("Manual URL / Manual Job Entry")
        self.assertTrue(adapter.capabilities["manual_import"])
        self.assertEqual(adapter.capabilities["application_url"], True)

        first = normalize_job({
            "source": "Manual URL / Manual Job Entry",
            "company": "Acme",
            "title": "SQL Developer",
            "location": "Bengaluru",
            "required_skills": "SQL, Python",
            "application_url": "https://example.com/apply",
        })
        second = normalize_job({
            "source": "Manual URL / Manual Job Entry",
            "company": "Acme",
            "title": "SQL Developer",
            "location": "Bengaluru",
            "skills": "SQL, Python",
            "application_url": "https://example.com/apply",
        })
        self.assertEqual(first.required_skills, "SQL, Python")
        self.assertEqual(second.skills, "SQL, Python")

        job_id = self.repo.create_job(first.as_record())
        duplicate_id = self.repo.create_job(second.as_record())
        self.assertEqual(job_id, duplicate_id)

    def test_resume_studio_template_and_pdf_helpers(self):
        resume = get_default_master_resume({"full_name": "Rahul", "skills": "SQL, Python", "summary": "Data analyst"})
        self.assertEqual(get_template_names(), ["Professional", "Modern", "ATS", "Minimal", "Technical"])
        self.assertIn("Data analyst", resume["summary"] or "")
        comparison = compare_resume_to_job({"title": "SQL Developer", "requirements": "SQL, Python", "description": "SQL, Python"}, resume)
        self.assertTrue(comparison)
        pdf = export_resume_pdf_bytes(resume)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 100)


if __name__ == "__main__":
    unittest.main()
