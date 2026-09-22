"""Provider boundaries, normalization, and deterministic job intelligence."""

from dataclasses import asdict, dataclass
from datetime import datetime
import re
from typing import Any, Protocol


SUPPORTED_SOURCES = (
    "LinkedIn",
    "Naukri",
    "Accenture Careers",
    "Dell Careers",
    "Other Official Career Sites",
    "Manual URL / Manual Job Entry",
)


SOURCE_CAPABILITIES = {
    "LinkedIn": {
        "search": False,
        "fetch_listing": False,
        "fetch_details": False,
        "posted_date": False,
        "application_url": False,
        "source_url": True,
        "official_api": False,
        "authorized_connector": False,
        "manual_import": True,
        "external_application_handoff": True,
    },
    "Naukri": {
        "search": False,
        "fetch_listing": False,
        "fetch_details": False,
        "posted_date": False,
        "application_url": False,
        "source_url": True,
        "official_api": False,
        "authorized_connector": False,
        "manual_import": True,
        "external_application_handoff": True,
    },
    "Accenture Careers": {
        "search": False,
        "fetch_listing": False,
        "fetch_details": False,
        "posted_date": False,
        "application_url": False,
        "source_url": True,
        "official_api": False,
        "authorized_connector": False,
        "manual_import": True,
        "external_application_handoff": True,
    },
    "Dell Careers": {
        "search": False,
        "fetch_listing": False,
        "fetch_details": False,
        "posted_date": False,
        "application_url": False,
        "source_url": True,
        "official_api": False,
        "authorized_connector": False,
        "manual_import": True,
        "external_application_handoff": True,
    },
    "Other Official Career Sites": {
        "search": False,
        "fetch_listing": False,
        "fetch_details": False,
        "posted_date": False,
        "application_url": False,
        "source_url": True,
        "official_api": False,
        "authorized_connector": False,
        "manual_import": True,
        "external_application_handoff": True,
    },
    "Manual URL / Manual Job Entry": {
        "search": False,
        "fetch_listing": False,
        "fetch_details": False,
        "posted_date": True,
        "application_url": True,
        "source_url": True,
        "official_api": False,
        "authorized_connector": False,
        "manual_import": True,
        "external_application_handoff": True,
    },
}


@dataclass(frozen=True)
class Job:
    external_id: str | None = None
    source: str = ""
    company: str = ""
    title: str = ""
    location: str | None = None
    remote_type: str | None = None
    description: str | None = None
    requirements: str | None = None
    skills: str | None = None
    required_skills: str | None = None
    preferred_skills: str | None = None
    experience: str | None = None
    salary: str | None = None
    posting_date: str | None = None
    application_url: str | None = None
    source_url: str | None = None
    fetched_at: datetime | None = None
    responsibilities: str | None = None
    education: str | None = None
    sql: str | None = None
    sql_requirements: str | None = None
    tools: str | None = None
    source_metadata: str | None = None
    metadata: str | None = None

    def as_record(self) -> dict[str, Any]:
        record = asdict(self)
        if self.fetched_at:
            record["fetched_at"] = self.fetched_at.isoformat()
        if record.get("source_metadata") is None and record.get("metadata"):
            record["source_metadata"] = record["metadata"]
        if record.get("required_skills") is None and record.get("skills"):
            record["required_skills"] = record["skills"]
        if record.get("skills") is None and record.get("required_skills"):
            record["skills"] = record["required_skills"]
        if record.get("sql_requirements") is None and record.get("sql"):
            record["sql_requirements"] = record["sql"]
        if record.get("sql") is None and record.get("sql_requirements"):
            record["sql"] = record["sql_requirements"]
        return record


class JobSource(Protocol):
    name: str
    configured: bool
    capabilities: dict[str, bool]

    def fetch(self, query: str = "", **filters: Any) -> list[Job]:
        ...


class EmptyJobSource:
    name = "Source unavailable"
    configured = False
    capabilities = {key: False for key in SOURCE_CAPABILITIES.get("LinkedIn", {})}

    def fetch(self, query: str = "", **filters: Any) -> list[Job]:
        return []


class UnconfiguredJobSource:
    """Safe placeholder for sources that require an authorized connector."""

    configured = False

    def __init__(self, name: str) -> None:
        self.name = name
        self.capabilities = SOURCE_CAPABILITIES.get(name, {"manual_import": True, "external_application_handoff": True})

    def fetch(self, query: str = "", **filters: Any) -> list[Job]:
        return []

    @property
    def unavailable_message(self) -> str:
        return f"{self.name}: Source unavailable / not configured"


class ManualJobEntrySource:
    name = "Manual URL / Manual Job Entry"
    configured = True
    capabilities = SOURCE_CAPABILITIES[name]

    def fetch(self, query: str = "", **filters: Any) -> list[Job]:
        return []


class JobFetcher:
    def __init__(self, sources: list[JobSource] | None = None) -> None:
        self.sources = sources or [EmptyJobSource()]

    @property
    def configured(self) -> bool:
        return any(getattr(source, "configured", True) for source in self.sources)

    def fetch_all(self, query: str = "", **filters: Any) -> list[Job]:
        jobs: list[Job] = []
        for source in self.sources:
            jobs.extend(source.fetch(query, **filters))
        return normalize_jobs(jobs)


def get_job_source_adapter(source_name: str) -> JobSource:
    if source_name == "Manual URL / Manual Job Entry":
        return ManualJobEntrySource()
    return UnconfiguredJobSource(source_name)


def normalize_job(raw: Job | dict[str, Any]) -> Job:
    data = raw.as_record() if isinstance(raw, Job) else dict(raw)
    if "required_skills" not in data and "skills" in data:
        data["required_skills"] = data["skills"]
    if "skills" not in data and "required_skills" in data:
        data["skills"] = data["required_skills"]
    if "sql_requirements" not in data and "sql" in data:
        data["sql_requirements"] = data["sql"]
    if "sql" not in data and "sql_requirements" in data:
        data["sql"] = data["sql_requirements"]
    if "source_metadata" not in data and "metadata" in data:
        data["source_metadata"] = data["metadata"]
    if "metadata" not in data and "source_metadata" in data:
        data["metadata"] = data["source_metadata"]
    text_keys = ("source", "company", "title")
    for key in text_keys:
        data[key] = str(data.get(key) or "").strip()
    if not all(data[key] for key in text_keys):
        raise ValueError("job source, company, and title are required")
    allowed = set(Job.__dataclass_fields__)
    normalized = {key: value for key, value in data.items() if key in allowed}
    return Job(**{field: normalized.get(field) for field in Job.__dataclass_fields__})


def normalize_jobs(raw_jobs: list[Job | dict[str, Any]]) -> list[Job]:
    result: list[Job] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_jobs:
        job = normalize_job(raw)
        key = (
            job.source.lower(),
            (job.external_id or job.application_url or
             f"{job.company}:{job.title}:{job.location or ''}").strip().lower(),
        )
        if key not in seen:
            seen.add(key)
            result.append(job)
    return result


def job_text(job: dict[str, Any]) -> str:
    """Return only source-supplied searchable text; never infer qualifications."""
    fields = ("title", "description", "requirements", "skills", "required_skills", "preferred_skills",
              "responsibilities", "education", "sql_requirements", "sql", "tools", "experience")
    return " ".join(str(job.get(field) or "") for field in fields)


def compare_job_to_candidate(job: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Compare explicit source terms to explicit candidate evidence.

    Terms absent from candidate data remain unclear rather than being labelled missing.
    """
    candidate_text = " ".join(
        str(candidate.get(field) or "")
        for field in ("skills", "tools", "sql", "experience", "education", "projects", "resume_information")
    ).lower()
    source_text = job_text(job)
    terms = []
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", source_text):
        normalized = raw.strip(".,:;()[]{}").lower()
        if normalized and normalized not in terms and normalized not in {"with", "and", "the", "for", "from"}:
            terms.append(normalized)
    matched = [term for term in terms if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", candidate_text)]
    unclear = [term for term in terms if term not in matched][:20]
    return {
        "available": bool(source_text.strip()),
        "matched": matched,
        "unclear": unclear,
        "missing": [],
        "categories": {
            "skills_match": {"matched": len(matched), "unclear": len(unclear), "status": "verified" if matched else "unclear"},
            "technical_match": {"status": "verified" if any(t in matched for t in ("sql", "mysql", "python")) else "unclear"},
            "experience_alignment": {"status": "unclear" if job.get("experience") else "not specified"},
            "education_alignment": {"status": "unclear" if job.get("education") else "not specified"},
            "resume_evidence": {"status": "verified" if candidate.get("resume_information") else "unclear"},
        },
        "note": "Only explicit candidate evidence is marked matched; unavailable evidence remains unclear.",
    }
