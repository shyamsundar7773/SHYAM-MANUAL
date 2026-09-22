"""Resume Studio rendering and safety helpers for verified candidate resumes."""

from __future__ import annotations

import re
from typing import Any

TEMPLATE_NAMES = ("Professional", "Modern", "ATS", "Minimal", "Technical")


def get_template_layout(template: str = "Professional") -> dict[str, Any]:
    name = (template or "Professional").strip() or "Professional"
    base = {
        "summary_first": True,
        "section_order": ["summary", "skills", "experience", "projects", "education", "certifications", "achievements"],
    }
    if name == "Modern":
        base.update({"summary_first": True, "section_order": ["summary", "skills", "projects", "experience", "education"]})
    elif name == "ATS":
        base.update({"summary_first": False, "section_order": ["skills", "summary", "experience", "projects", "education"]})
    elif name == "Minimal":
        base.update({"summary_first": True, "section_order": ["summary", "experience", "skills", "education"]})
    elif name == "Technical":
        base.update({"summary_first": True, "section_order": ["skills", "summary", "projects", "experience", "education"]})
    return base


def render_resume_preview(resume: dict[str, Any] | None = None, template: str = "Professional") -> str:
    data = resume or {}
    title = ((data.get("personal") or {}).get("name") or "Resume Preview").strip()
    lines = [f"{template} Template", title]
    lines.extend(["-" * 10])
    lines.extend(_render_pdf_lines(data))
    return "\n".join(lines).strip()


def get_default_master_resume(candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = candidate or {}
    return {
        "personal": {
            "name": profile.get("full_name") or "",
            "email": profile.get("email") or "",
            "phone": profile.get("phone") or "",
            "location": profile.get("location") or "",
            "linkedin": "",
            "github": "",
            "portfolio": "",
        },
        "summary": profile.get("summary") or "",
        "education": [],
        "skills": {
            "technical": [item.strip() for item in str(profile.get("skills") or "").split(",") if item.strip()],
            "sql": [item.strip() for item in str(profile.get("sql") or "").split(",") if item.strip()],
            "tools": [item.strip() for item in str(profile.get("tools") or "").split(",") if item.strip()],
            "analytics": [],
            "other": [],
        },
        "experience": [],
        "projects": [],
        "certifications": [],
        "achievements": [],
        "additional_information": profile.get("additional_information") or "",
    }


def create_resume_document_payload(candidate: dict[str, Any] | None = None, job: dict[str, Any] | None = None, template: str = "Professional") -> dict[str, Any]:
    resume = get_default_master_resume(candidate)
    if job:
        resume["job_context"] = {
            "title": job.get("title") or "",
            "company": job.get("company") or "",
            "requirements": job.get("requirements") or job.get("description") or "",
        }
    resume["template"] = template
    return resume


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\r", "").replace("\n", " ")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _render_pdf_lines(resume: dict[str, Any] | None) -> list[str]:
    data = resume or {}
    lines = []
    personal = data.get("personal") or {}
    if personal.get("name"):
        lines.append(personal["name"])
    contacts = [personal.get("email"), personal.get("phone"), personal.get("location")]
    if any(contacts):
        lines.append(" | ".join(filter(None, contacts)))
    summary = (data.get("summary") or "").strip()
    if summary:
        lines.extend(["", "Professional Summary", summary])
    skills = data.get("skills") or {}
    combined_skills = []
    for key in ("technical", "sql", "tools", "analytics", "other"):
        combined_skills.extend(_as_list(skills.get(key) if isinstance(skills, dict) else skills))
    if combined_skills:
        lines.extend(["", "Skills", ", ".join(combined_skills)])
    projects = data.get("projects") or []
    if projects:
        lines.extend(["", "Projects"])
        if isinstance(projects, str):
            lines.append(projects)
        else:
            for item in projects:
                if isinstance(item, dict):
                    lines.append(f"- {item.get('name') or 'Project'}: {item.get('description') or ''}")
                else:
                    lines.append(f"- {item}")
    return lines


def render_resume_text(resume: dict[str, Any] | None) -> str:
    return "\n".join(_render_pdf_lines(resume)).strip()


def export_resume_pdf_bytes(resume: dict[str, Any] | None = None) -> bytes:
    lines = _render_pdf_lines(resume)
    if not lines:
        lines = ["No resume content available."]
    content_lines = []
    y = 760
    for line in lines:
        content_lines.append(f"BT /F1 12 Tf 50 {y} Td ({_escape_pdf_text(line)}) Tj ET")
        y -= 18
    content_block = "\n".join(content_lines)
    content_bytes = content_block.encode("latin-1", "replace")
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content_bytes)} >>\nstream\n{content_block}\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1", "replace"))
    xref_position = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1", "replace"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1", "replace"))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF\n".encode("latin-1", "replace"))
    return bytes(pdf)


def classify_requirement(requirement: str, resume: dict[str, Any] | None = None) -> str:
    if not requirement or not requirement.strip():
        return "Unclear"
    resume_text = render_resume_text(resume).lower()
    candidate_text = " ".join(filter(None, [
        resume_text,
        str((resume or {}).get("summary") or ""),
        str((resume or {}).get("additional_information") or ""),
    ])).lower()
    requirement_text = requirement.lower()
    if requirement_text in candidate_text:
        return "Strong Match"
    tokens = [part.strip() for part in requirement_text.split() if len(part.strip()) > 3]
    if any(token in candidate_text for token in tokens[:5]):
        return "Present"
    return "Missing"


def get_template_names() -> list[str]:
    return list(TEMPLATE_NAMES)


def compare_resume_to_job(job: dict[str, Any] | None, resume: dict[str, Any] | None) -> list[dict[str, Any]]:
    job_data = job or {}
    requirements = []
    raw_requirements = job_data.get("requirements") or job_data.get("description") or ""
    if isinstance(raw_requirements, str):
        parsed = [item.strip() for item in re.split(r"[\n;]+", raw_requirements) if item.strip()]
    else:
        parsed = []
    if not parsed:
        parsed = ["General role fit"]
    for item in parsed[:20]:
        status = classify_requirement(item, resume)
        evidence = "Direct evidence appears in the resume content." if status in {"Strong Match", "Present"} else "No clear evidence found in current resume content."
        requirements.append({"requirement": item, "status": status, "evidence": evidence})
    return requirements
