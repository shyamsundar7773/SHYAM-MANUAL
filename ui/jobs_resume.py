"""Phase 6 jobs foundation plus Phase 10 Job Radar and Job Intelligence."""

from datetime import date, timedelta
import json

import streamlit as st

from data.repositories import ContentRepository
from services.ai import build_ai_service
from services.jobs import (
    SUPPORTED_SOURCES,
    EmptyJobSource,
    JobFetcher,
    compare_job_to_candidate,
    normalize_job,
)
from services.resume_studio import (
    compare_resume_to_job,
    export_resume_pdf_bytes,
    get_default_master_resume,
    get_template_names,
    render_resume_preview,
)


PROFILE_FIELDS = (
    "full_name", "headline", "email", "phone", "location", "links", "summary",
    "skills", "experience", "education", "tools", "sql", "projects", "certifications",
    "preferred_roles", "preferred_locations", "experience_level", "availability",
    "resume_information", "additional_information",
)
STATUSES = ["saved", "ready", "applied", "screening", "interview", "offer", "rejected", "withdrawn"]


def _render_profile(repository: ContentRepository) -> dict:
    st.subheader("Candidate Profile")
    profile = repository.get_candidate_profile()
    if st.session_state.pop("candidate-profile-saved", False):
        st.success("Candidate Profile saved. Job Radar, Resume Studio, and future interview context now use this persisted profile.")
    if profile:
        st.caption(f"Editing your single persisted candidate profile · Last saved: {profile['updated_at']}")
    else:
        st.info("No Candidate Profile has been saved yet. Complete any fields below, then save once to make them available across Shyam Manual.")
    with st.form("candidate-profile"):
        values = {}
        cols = st.columns(2)
        for index, field in enumerate(PROFILE_FIELDS):
            with cols[index % 2]:
                values[field] = st.text_area(
                    field.replace("_", " ").title(),
                    value=(profile[field] or "") if profile else "",
                    height=70 if field in {"summary", "experience", "education"} else 40,
                )
        if st.form_submit_button("Save / Update Candidate Profile"):
            repository.save_candidate_profile(values)
            st.session_state["candidate-profile-saved"] = True
            st.rerun()
    return dict(profile) if profile else {}


def _render_manual_job_form(repository: ContentRepository) -> None:
    with st.expander("NEW JOB / MANUAL IMPORT", expanded=False):
        with st.form("add-job"):
            title = st.text_input("Job title")
            company = st.text_input("Company")
            source = st.selectbox("Source", SUPPORTED_SOURCES, index=len(SUPPORTED_SOURCES) - 1)
            location = st.text_input("Location")
            urls = st.columns(2)
            with urls[0]:
                application_url = st.text_input("Official application URL")
            with urls[1]:
                source_url = st.text_input("Source URL")
            description = st.text_area("Job description")
            requirements = st.text_area("Requirements")
            skills = st.text_input("Required skills (as provided)")
            preferred_skills = st.text_input("Preferred skills (as provided)")
            responsibilities = st.text_area("Responsibilities")
            education = st.text_input("Education")
            sql_requirements = st.text_input("SQL requirements")
            tools = st.text_input("Tools")
            experience = st.text_input("Experience")
            salary = st.text_input("Salary (if provided)")
            posting_date = st.date_input("Posting date", value=date.today())
            remote = st.selectbox("Remote type", ["unspecified", "remote", "hybrid", "onsite"])
            if st.form_submit_button("Save job"):
                if not title.strip() or not company.strip():
                    st.error("Title and company are required.")
                    return
                record = normalize_job({
                    "title": title, "company": company, "source": source, "location": location,
                    "description": description, "skills": skills, "preferred_skills": preferred_skills,
                    "requirements": requirements, "responsibilities": responsibilities,
                    "education": education, "sql_requirements": sql_requirements, "tools": tools,
                    "experience": experience, "salary": salary, "posting_date": posting_date.isoformat(),
                    "remote_type": remote, "application_url": application_url, "source_url": source_url,
                }).as_record()
                repository.create_job(record)
                st.success("Job saved.")
                st.rerun()


def _render_source_checks(repository: ContentRepository) -> None:
    with st.expander("SOURCE STATUS", expanded=False):
        st.caption("Only configured, authorized connectors may fetch listings. No scraping or fake results are used.")
        selected = st.multiselect("Sources to check", list(SUPPORTED_SOURCES), default=list(SUPPORTED_SOURCES),
                                   key="job-radar-sources")
        if st.button("CHECK FOR NEW JOBS", key="job-radar-check"):
            fetcher = JobFetcher([EmptyJobSource()])
            for source in selected:
                fetched = fetcher.fetch_all()
                repository.record_job_source_check(
                    source, "unavailable", len(fetched),
                    "Source unavailable / not configured. Add an authorized connector to enable refresh.",
                )
            st.info("No source connector is configured. Existing persisted jobs remain available.")
            st.rerun()
        for row in repository.list_job_source_checks():
            st.caption(f"{row['source']}: {row['message']} · last checked {row['checked_at']}")


def _render_job_detail(repository: ContentRepository, job: dict, candidate: dict) -> None:
    st.markdown(f"### {job['title']} — {job['company']}")
    st.caption(" · ".join(filter(None, [job["location"], job["remote_type"], job["source"],
                                         f"Posted {job['posting_date']}" if job["posting_date"] else None])))
    if job["application_url"]:
        st.link_button("OPEN OFFICIAL APPLICATION", job["application_url"])
        st.caption("Opening the official page does not mark this job as applied.")
    else:
        st.info("No official application URL was supplied.")
    st.markdown("#### Requirements")
    st.write(job["requirements"] or job["description"] or "No requirements supplied.")
    match = repository.get_job_analysis(job["id"]) or compare_job_to_candidate(dict(job), candidate)
    st.markdown("#### Candidate Match / Resume Match")
    st.json(match)
    unclear = match.get("unclear", [])
    gaps = [dict(row) for row in repository.map_preparation_gaps(unclear)]
    st.markdown("#### Preparation Gaps")
    if gaps:
        for gap in gaps:
            st.write(f"**{gap['category_name']} → {gap['module_name']} → {gap['name']}**")
    else:
        st.caption("No mapped SHYAM-MANUAL topics for the currently unclear terms.")
    actions = st.columns(4)
    with actions[0]:
        if st.button("SAVE JOB", key=f"detail-save-{job['id']}"):
            repository.save_job(job["id"])
            st.success("Job saved.")
    with actions[1]:
        if st.button("PREPARE APPLICATION", key=f"detail-prepare-{job['id']}"):
            app_id = repository.create_application(job["id"], "ready", notes="Ready to apply", official_application_url=job.get("application_url"), source_url=job.get("source_url"), candidate_profile_id=1)
            st.success(f"Application prepared for {job['title']}.")
            st.session_state["selected_application_id"] = app_id
    with actions[2]:
        if st.button("ANALYZE / MATCH", key=f"detail-analyze-{job['id']}"):
            result = compare_job_to_candidate(dict(job), candidate)
            result["preparation_topics"] = [
                dict(row) for row in repository.map_preparation_gaps(result.get("unclear", []))
            ]
            repository.save_job_analysis(job["id"], result)
            repository.save_candidate_match(job["id"], result)
            st.success("Transparent match saved.")
            st.rerun()
    with actions[3]:
        if st.button("MARK AS APPLIED", key=f"detail-applied-{job['id']}"):
            repository.upsert_application(job["id"], "applied", applied_at=date.today().isoformat(), official_application_url=job.get("application_url"), source_url=job.get("source_url"))
            st.success("Marked as applied from your explicit action.")


def _render_radar(repository: ContentRepository, candidate: dict) -> None:
    st.subheader("JOB RADAR")
    matching = repository.count_jobs()
    saved = len(repository.list_saved_jobs())
    applications = len(repository.list_applications())
    notifications = len(repository.list_job_notifications(pending_only=True))
    metrics = st.columns(5)
    for target, label, value in zip(metrics, ("NEW JOBS", "MATCHING JOBS", "SAVED JOBS", "APPLICATIONS", "NEW MATCH ALERTS"),
                                    (notifications, matching, saved, applications, notifications)):
        target.metric(label, value)

    controls = st.columns(2)
    with controls[0]:
        search = st.text_input("Search", key="job-radar-search", placeholder="SQL Developer")
        location = st.text_input("Location", key="job-radar-location", placeholder="Bengaluru")
        experience = st.selectbox("Experience", ["Any", "0–2 years", "2–5 years", "5+ years"], key="job-radar-experience")
    with controls[1]:
        job_type = st.selectbox("Job type", ["Any"], key="job-radar-type")
        remote = st.selectbox("Remote", ["Any", "remote", "hybrid", "onsite"], key="job-radar-remote")
        posted = st.selectbox("Posted", ["Any", "Today", "3 days", "7 days"], key="job-radar-posted")

    _render_source_checks(repository)
    _render_manual_job_form(repository)

    posting_since = None
    if posted != "Any":
        posting_since = (date.today() - timedelta(days=int(posted.split()[0]))).isoformat()
    remote_filter = None if remote == "Any" else remote
    total = repository.count_jobs(search, location=location, remote_type=remote_filter, posting_since=posting_since)
    page_size = st.selectbox("Jobs per page", [10, 20, 50], index=0, key="job-radar-page-size")
    page_count = max(1, (total + page_size - 1) // page_size)
    page_number = st.number_input("Job page", min_value=1, max_value=page_count, step=1,
                                  value=min(st.session_state.get("job-radar-page", 1), page_count),
                                  key="job-radar-page")
    jobs = repository.list_jobs(search, location=location, remote_type=remote_filter,
                                posting_since=posting_since, limit=page_size,
                                offset=(page_number - 1) * page_size)
    st.caption(f"Showing {((page_number - 1) * page_size) + 1 if total else 0}-{min(page_number * page_size, total)} of {total} job(s)")
    if experience != "Any":
        st.caption("Experience selection is retained for future source-side filtering; only source-provided values are shown.")
    if job_type != "Any":
        st.caption("Job type is retained for future source-side filtering; only source-provided values are shown.")
    st.markdown("### MATCHING JOBS")
    if not jobs:
        st.info("No persisted jobs match these filters. Check a configured source or use NEW JOB / MANUAL IMPORT.")
        return
    options = {f"{row['title']} — {row['company']} · {row['source']}": row["id"] for row in jobs}
    selected_label = st.selectbox("View job", list(options), key="job-radar-selected")
    for job in jobs:
        match = compare_job_to_candidate(dict(job), candidate)
        with st.container(border=True):
            st.markdown(f"**{job['title']}**")
            st.caption(" · ".join(filter(None, [job["company"], job["location"], job["source"]])))
            st.caption(f"Posted: {job['posting_date'] or 'Not provided'}")
            st.write(job["description"] or job["requirements"] or "No description supplied.")
            st.write(f"Verified: {', '.join(match['matched'][:6]) or 'None'}")
            st.write(f"Needs verification: {', '.join(match['unclear'][:6]) or 'None'}")
            cols = st.columns(3)
            with cols[0]:
                if st.button("VIEW", key=f"view-job-{job['id']}"):
                    st.session_state["job-radar-selected"] = options.get(
                        f"{job['title']} — {job['company']} · {job['source']}", selected_label
                    )
                    st.rerun()
            with cols[1]:
                if st.button("PREPARE", key=f"prepare-job-{job['id']}"):
                    st.session_state["job-radar-selected"] = f"{job['title']} — {job['company']} · {job['source']}"
                    st.rerun()
            with cols[2]:
                if st.button("SAVE", key=f"save-job-{job['id']}"):
                    repository.save_job(job["id"])
                    st.success("Saved.")
    selected_id = options[selected_label]
    selected = next(row for row in jobs if row["id"] == selected_id)
    with st.expander("JOB DETAIL", expanded=True):
        _render_job_detail(repository, dict(selected), candidate)


def _render_resume_studio(repository: ContentRepository) -> None:
    st.subheader("Resume Studio")
    profile = repository.get_candidate_profile() or {}
    candidate = dict(profile)
    master_resume = get_default_master_resume(candidate)
    selected_job = None

    document_type = st.selectbox("Document type", ["Master Resume", "Job-Specific Resume"], key="resume-document-type")
    template = st.selectbox("Template", get_template_names(), index=0, key="resume-template")

    if document_type == "Master Resume":
        resume = master_resume
        title = st.text_input("Resume title", value="Master Resume", key="resume-title-master")
    else:
        jobs = repository.list_saved_jobs()
        if jobs:
            labels = {f"{row['title']} — {row['company']}": row for row in jobs}
            job_label = st.selectbox("Select a saved job", list(labels), key="resume-job-select")
            selected_job = dict(labels[job_label])
        else:
            st.info("No saved jobs available. Save a job from Job Radar first.")
            selected_job = None
        if selected_job:
            title = st.text_input("Resume title", value=f"{selected_job['company']} {selected_job['title']} — tailored", key="resume-title-job")
            resume = {
                **master_resume,
                "template": template,
                "job_context": {"title": selected_job.get("title"), "company": selected_job.get("company"), "requirements": selected_job.get("requirements") or selected_job.get("description")},
            }
        else:
            title = st.text_input("Resume title", value="Job-specific Resume", key="resume-title-job-empty")
            resume = {**master_resume, "template": template}

    st.caption("The resume stays grounded in supplied candidate profile data. It never invents missing qualifications.")

    section = st.tabs(["Summary", "Skills", "Experience", "Projects", "Preview", "Suggestions"])
    with section[0]:
        resume["summary"] = st.text_area("Professional Summary", value=resume.get("summary") or "", height=140)
        resume["personal"]["name"] = st.text_input("Name", value=resume.get("personal", {}).get("name") or "")
        resume["personal"]["email"] = st.text_input("Email", value=resume.get("personal", {}).get("email") or "")
        resume["personal"]["phone"] = st.text_input("Phone", value=resume.get("personal", {}).get("phone") or "")
        resume["personal"]["location"] = st.text_input("Location", value=resume.get("personal", {}).get("location") or "")
    with section[1]:
        resume.setdefault("skills", {"technical": [], "sql": [], "tools": [], "analytics": [], "other": []})
        resume["skills"]["technical"] = st.text_input("Technical skills", value=", ".join(resume["skills"].get("technical", [])))
        resume["skills"]["sql"] = st.text_input("SQL skills", value=", ".join(resume["skills"].get("sql", [])))
        resume["skills"]["tools"] = st.text_input("Tools", value=", ".join(resume["skills"].get("tools", [])))
    with section[2]:
        resume["experience"] = st.text_area("Experience", value=str(resume.get("experience") or ""), height=140)
    with section[3]:
        resume["projects"] = st.text_area("Projects", value=str(resume.get("projects") or ""), height=140)
    with section[4]:
        st.code(render_resume_preview(resume, template), language="text")
    with section[5]:
        if selected_job:
            items = compare_resume_to_job(selected_job, resume)
            for item in items:
                st.write(f"{item['status']}: {item['requirement']}")
            if st.button("Generate tailoring suggestions", key="resume-suggest"):
                ai = build_ai_service("mock")
                result = ai.tailor_resume(resume, job=selected_job, candidate=profile)
                suggestions = result.get("suggestions") or result.get("tailored", {}).get("tailoring_notes") or []
                if suggestions:
                    st.json(suggestions)
                    try:
                        document_id = repository.create_resume_document(title, document_type="master" if document_type == "Master Resume" else "job_specific", template=template, document_json=resume, source="manual", version_label="v1")
                    except Exception:
                        document_id = None
                    for suggestion in suggestions:
                        if document_id is not None:
                            repository.save_resume_suggestion(
                                document_id,
                                original_content=str(suggestion.get("value") or ""),
                                suggested_content=str(suggestion.get("value") or ""),
                                reason=str(suggestion.get("reason") or "Tailoring recommendation"),
                                related_job_requirement=str(selected_job.get("title") or "Role"),
                                evidence="Candidate profile data only",
                                status="pending",
                            )
                else:
                    st.info("No tailoring suggestions were produced; the supplied profile did not contain direct evidence for that job.")
        else:
            st.info("Select a job to compare resume evidence against requirements.")

    col_save, col_pdf = st.columns(2)
    if col_save.button("Save version", key="resume-save-version"):
        document_id = repository.create_resume_document(title, document_type="master" if document_type == "Master Resume" else "job_specific", template=template, document_json=resume, source="manual", version_label="v1")
        repository.create_resume_version(document_id, version_label="v1", title=title, template=template, content_json=resume)
        st.success(f"Saved {title} as version v1.")
    if col_pdf.button("Export PDF", key="resume-export-pdf"):
        pdf = export_resume_pdf_bytes(resume)
        st.download_button("Download PDF", data=pdf, file_name=f"{title or 'resume'}.pdf", mime="application/pdf")


def render_jobs_resume(repository: ContentRepository, settings) -> None:
    candidate_tab, radar_tab, studio_tab, tracker_tab = st.tabs(["Candidate Profile", "Job Radar", "Resume Studio", "Applications"])
    with candidate_tab:
        st.caption("This is your single source-of-truth profile. Save here once; the persisted values are reused by Job Radar, matching, resumes, and application context.")
        profile = _render_profile(repository)
        st.subheader("Master resume / tailored preview")
        st.caption("Drafts contain only profile data supplied by you. Tailoring never adds unsupported qualifications.")
        if profile and st.button("Save master resume draft", key="save-master-resume"):
            draft_id = repository.create_resume_draft("Master resume", {key: profile.get(key) for key in PROFILE_FIELDS})
            st.success(f"Saved draft #{draft_id}.")
        for draft in repository.list_resume_drafts():
            st.markdown(f"**{draft['title']}** · {draft['source']}")
            st.json(json.loads(draft["content_json"]))
    with radar_tab:
        st.caption("Job Radar reads the saved Candidate Profile for transparent matching. Refresh checks only configured or manual sources; it does not fabricate listings.")
        _render_radar(repository, repository.get_candidate_profile() or {})
    with studio_tab:
        st.caption("Resume Studio starts from the saved Candidate Profile. Choose Master Resume or a saved job for a job-specific version.")
        _render_resume_studio(repository)
    with tracker_tab:
        st.caption("Applications link back to persisted jobs and the Candidate Profile; status changes are explicit user actions.")
        status_filter = st.selectbox("Status filter", ["All", *STATUSES], key="application-status-filter")
        applications = repository.list_applications(status=None if status_filter == "All" else status_filter, limit=20)
        if not applications:
            st.info("No applications tracked yet.")
        else:
            for application in applications:
                app_status = application["status"]
                st.markdown(f"### {application['company']} — {application['title']}")
                st.caption(f"Status: {app_status} · Source: {application['source']} · Applied: {application['applied_at'] or 'Not applied'}")
                cols = st.columns(3)
                with cols[0]:
                    if application.get("official_application_url"):
                        st.link_button("Open official link", application["official_application_url"])
                with cols[1]:
                    if st.button("View job", key=f"tracker-view-{application['id']}"):
                        st.session_state["selected_application_id"] = application["id"]
                with cols[2]:
                    if st.button("Confirm applied", key=f"tracker-confirm-{application['id']}"):
                        repository.upsert_application(application["job_id"], "applied", notes=application["notes"] or "Confirmed by user", applied_at=date.today().isoformat(), official_application_url=application.get("official_application_url"), source_url=application.get("source_url"))
                        st.success("Application status confirmed.")
                        st.rerun()
                status = st.selectbox("Update status", STATUSES, index=STATUSES.index(app_status) if app_status in STATUSES else 0, key=f"tracker-status-{application['id']}")
                if st.button("Update tracker", key=f"tracker-update-{application['id']}"):
                    repository.upsert_application(application["job_id"], status, notes=application["notes"] or "", applied_at=application["applied_at"], official_application_url=application.get("official_application_url"), source_url=application.get("source_url"))
                    st.success("Application tracker updated.")
                    st.rerun()
                st.write(application["notes"] or "No notes yet.")
