"""Interview evaluation and adaptive mission views."""

import json

import streamlit as st

from data.repositories import ContentRepository
from services.ai import build_ai_service


def _session_options(repository: ContentRepository):
    sessions = repository.list_interview_sessions()
    if not sessions:
        return []
    return [
        {
            "label": f"#{row['id']} · {row['role']} · {row['interview_type']} · {row['status']}",
            "row": row,
        }
        for row in sessions
    ]


def render_evaluation_page(repository: ContentRepository, settings) -> None:
    st.subheader("Interview evaluation")
    ai_service = build_ai_service(getattr(settings, "ai_provider", "mock"), getattr(settings, "ai_api_key", None), getattr(settings, "ai_model", None))
    sessions = repository.list_interview_sessions()
    if not sessions:
        st.info("Start a live interview to generate the first evaluation.")
        return

    options = _session_options(repository)
    choice = st.selectbox("Select interview", [item["label"] for item in options])
    selected = next(item["row"] for item in options if item["label"] == choice)
    evaluation = repository.get_interview_evaluation(selected["id"])

    if st.button("Generate or refresh evaluation"):
        payload = ai_service.evaluate_interview(dict(selected), repository)
        saved = repository.save_interview_evaluation(selected["id"], payload)
        weaknesses = ai_service.detect_weaknesses(payload, repository)
        for weakness in weaknesses:
            repository.save_weakness(selected["id"], weakness, evaluation_id=int(saved["id"]))
        recommendations = ai_service.recommend_practice(weaknesses, repository)
        for recommendation in recommendations:
            repository.save_recommendation(selected["id"], recommendation, evaluation_id=int(saved["id"]))
        ai_service.update_adaptive_mission(selected["id"], repository=repository, evaluation=payload)
        evaluation = repository.get_interview_evaluation(selected["id"])

    if evaluation is None:
        st.info("No evaluation recorded yet. Generate one to review strengths, gaps, and next steps.")
        return

    payload = json.loads(evaluation["evaluation_json"] or "{}") if evaluation["evaluation_json"] else {}
    st.markdown(f"**Overall summary**: {payload.get('overall_summary') or evaluation['overall_summary'] or 'Summary unavailable.'}")
    st.caption(payload.get('note') or "Deterministic fallback review.")

    strengths = payload.get("strengths") or []
    if strengths:
        st.markdown("**Strengths**")
        for item in strengths:
            st.write(f"- {item}")

    weaknesses = repository.list_weaknesses(selected["id"])
    if weaknesses:
        st.markdown("**Weaknesses**")
        for item in weaknesses:
            st.write(f"- {item['name']} — {item['description'] or 'Needs more detail.'}")
    else:
        st.write("- No major gaps identified in the recorded answers.")

    recommendations = repository.list_recommendations(selected["id"])
    if recommendations:
        st.markdown("**Recommendations**")
        for item in recommendations:
            st.write(f"- {item['weakness']} — {item['reason'] or item['practice_objective']}")
            if item["recommended_question"]:
                st.caption(item["recommended_question"])

    st.markdown("**Key observations**")
    for item in payload.get("key_observations") or ["No key observations captured."]:
        st.write(f"- {item}")

    st.markdown("**Question-by-question review**")
    for item in payload.get("question_evaluations") or []:
        with st.container(border=True):
            st.markdown(f"**{item.get('question') or 'Question review'}**")
            st.caption(f"Completeness: {item.get('answer_completeness') or 'unknown'} | Relevance: {item.get('relevance') or 'unknown'}")
            if item.get("answer"):
                st.write(item["answer"])
            if item.get("improvement_guidance"):
                st.caption(item["improvement_guidance"])


def render_mission_page(repository: ContentRepository, settings) -> None:
    st.subheader("20-Day Mission")
    adaptations = repository.list_mission_adaptations()
    if not adaptations:
        st.info("No mission adaptations yet. Complete an interview evaluation to prioritize the next practice goals.")
        return

    for adaptation in adaptations:
        priority = str(adaptation["priority"]).lower()
        if priority == "high":
            color = "🔴"
        elif priority == "medium":
            color = "🟡"
        else:
            color = "🟢"
        with st.container(border=True):
            st.markdown(f"**{color} {adaptation['weakness_name']}**")
            st.caption(f"Priority: {adaptation['priority']} | Session: #{adaptation['session_id']}")
            st.write(adaptation["reason"] or "Focus on targeted practice and answer structure.")
            if adaptation.get("topic_name"):
                st.caption(f"Topic: {adaptation['topic_name']}")

    st.subheader("Adaptive preparation")
    recs = repository.list_preparation_recommendations()
    if not recs:
        st.info("No recommendations yet.")
    else:
        for rec in recs[:10]:
            with st.container(border=True):
                st.markdown(f"**{rec['weakness_name']}**")
                st.caption(f"Priority: {rec['priority']} | Action: {rec['action']}")
                st.write(rec["recommendation"])


def render_progress_page(repository: ContentRepository, settings) -> None:
    st.subheader("Progress")
    summary = repository.get_progress_summary()
    cols = st.columns(5)
    for column, (label, value) in zip(cols, summary.items()):
        column.metric(label.replace("_", " ").title(), value)

    st.markdown("**Recent preparation activity**")
    events = repository.list_progress_events(limit=10)
    if not events:
        st.info("No progress events recorded yet. Interview evaluations and mission updates will populate this view.")
        return

    for event in events:
        with st.container(border=True):
            st.markdown(f"**{event['title']}**")
            st.caption(f"{event['event_type']} · {event['status']} · {event['created_at']}")
            if event.get("description"):
                st.write(event["description"])
            if event.get("category"):
                st.caption(f"Category: {event['category']}")
