"""Phase 7 live interview flow built on the existing repository and AI abstraction."""

import json
from datetime import datetime

import streamlit as st

from data.repositories import ContentRepository
from services.ai import build_ai_service

TOPIC_CHOICES = [
    "SQL", "Joins", "Aggregation", "Window Functions", "Subqueries",
    "CTEs", "Performance", "Database Design", "Project", "Business Analysis",
    "Data Quality", "Mixed",
]


def _parse_topics(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()] if str(raw).strip() else []


def _session_meta(session) -> dict:
    if session is None:
        return {}
    try:
        payload = json.loads(session["metadata_json"] or "{}")
    except (TypeError, ValueError):
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _session_dict(session) -> dict:
    """Normalize repository rows at the UI boundary before dict-style access."""
    return dict(session) if session is not None else {}


def _set_active_session_key(repository: ContentRepository, session_key: str | None) -> None:
    if session_key:
        st.session_state["live_session_key"] = session_key
        return
    active = next((row for row in repository.list_interview_sessions() if row["status"] in {"active", "paused"}), None)
    if active:
        st.session_state["live_session_key"] = active["session_key"]


def _active_session(repository: ContentRepository):
    session_key = st.session_state.get("live_session_key")
    if session_key:
        session = repository.get_interview_session(session_key)
        if session is not None:
            return _session_dict(session)
    for row in repository.list_interview_sessions():
        if row["status"] in {"active", "paused"}:
            st.session_state["live_session_key"] = row["session_key"]
            return _session_dict(row)
    return None


def _build_question_ids(repository: ContentRepository, role: str, interview_type: str,
                        difficulty: str, selected_topics: list[str], question_count: int):
    rows = repository.build_interview_questions(
        role=role,
        interview_type=interview_type,
        difficulty=difficulty.lower(),
        selected_topics=selected_topics,
        question_count=question_count,
    )
    return [int(row["id"]) for row in rows]


def _question_prompt(repository: ContentRepository, question_id: int | None, session, ai_service,
                    mode: str, question_index: int):
    if question_id is None:
        return "Walk me through your experience and explain your decision-making in detail."
    question = repository.get_question(question_id)
    if question is None:
        return "Describe how you would approach this challenge and what you would validate first."
    base = question["question"]
    if mode in {"AI Follow-up Interview", "Mixed Interview"} and question_index > 0:
        last_user = None
        for message in repository.list_interview_messages(session["id"]):
            if message["speaker"] == "user":
                last_user = message["message"]
        if last_user:
            result = ai_service.generate_follow_up(base, last_user, session["role"], session["interview_type"], session["difficulty"], _parse_topics(session["selected_topics"]))
            return result.get("question") or base
    return base


def _generate_interview_evaluation(repository: ContentRepository, session, ai_service) -> dict:
    payload = ai_service.evaluate_interview(dict(session), repository)
    saved = repository.save_interview_evaluation(session["id"], payload)
    weaknesses = ai_service.detect_weaknesses(payload, repository)
    for weakness in weaknesses:
        repository.save_weakness(session["id"], weakness, evaluation_id=int(saved["id"]))
    recommendations = ai_service.recommend_practice(weaknesses, repository)
    for recommendation in recommendations:
        repository.save_recommendation(session["id"], recommendation, evaluation_id=int(saved["id"]))
    ai_service.update_adaptive_mission(session["id"], repository=repository, evaluation=payload)
    return payload


def _render_setup(repository: ContentRepository, ai_service) -> None:
    st.subheader("Interview setup")
    with st.form("live-interview-setup"):
        role = st.text_input("Role", value="SQL Developer")
        interview_type = st.selectbox("Interview type", ["HR", "SQL Technical", "Technical Round", "Project", "Practical", "Mixed", "Custom", "Job-Based", "Resume-Based"])
        difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
        question_count = st.selectbox("Number of questions", [5, 10, 15])
        selected_topics = st.multiselect("Interview focus", TOPIC_CHOICES, default=["SQL", "Joins"])
        mode = st.selectbox("Mode", ["Structured Interview", "AI Follow-up Interview", "Mixed Interview", "Job Mode", "Resume Mode", "Realistic Mode"])
        voice_mode = st.checkbox("Voice Mode ON", value=False, help="Uses a safe, truthful voice fallback. If a browser microphone is unavailable, the app remains in text mode.")
        submitted = st.form_submit_button("Start interview")
    if submitted:
        question_ids = _build_question_ids(repository, role, interview_type, difficulty.lower(), selected_topics, question_count)
        session = repository.create_interview_session({
            "role": role,
            "interview_type": interview_type,
            "difficulty": difficulty.lower(),
            "selected_topics": selected_topics,
            "question_count": question_count,
            "status": "active",
            "current_question": 0,
            "completed_questions": 0,
            "mode": mode,
            "voice_mode": voice_mode,
            "metadata_json": {"mode": mode, "voice_mode": voice_mode, "question_ids": question_ids, "question_index": 0},
        })
        meta = _session_meta(session)
        if meta.get("question_ids"):
            first_prompt = _question_prompt(repository, meta["question_ids"][0], session, ai_service, mode, 0)
            repository.add_interview_message(session["id"], "interviewer", first_prompt,
                                            question_id=meta["question_ids"][0],
                                            source_question_id=meta["question_ids"][0],
                                            voice_mode=bool(voice_mode))
        repository.update_interview_session(session["id"], {"status": "active", "current_question": 1, "started_at": datetime.utcnow().isoformat(timespec="seconds"), "mode": mode, "voice_mode": voice_mode})
        st.session_state["live_session_key"] = session["session_key"]
        st.success("Interview started.")
        st.rerun()


def _render_active_interview(repository: ContentRepository, session, ai_service) -> None:
    session = _session_dict(session)
    session_key = session["session_key"]
    meta = _session_meta(session)
    mode = meta.get("mode", "Structured Interview")
    question_ids = meta.get("question_ids", [])
    question_index = int(meta.get("question_index", 0) or 0)
    if not question_ids:
        question_ids = _build_question_ids(
            repository,
            session["role"],
            session["interview_type"],
            session["difficulty"],
            _parse_topics(session["selected_topics"]),
            int(session["question_count"]),
        )
        meta["question_ids"] = question_ids
        meta["question_index"] = 0
        repository.update_interview_session(session["id"], {"metadata_json": meta})
        session = _session_dict(repository.get_interview_session(session_key))
        meta = _session_meta(session)

    left, right = st.columns([2, 1])
    with left:
        st.subheader(f"{session['role']} — {session['interview_type']} ({session['difficulty']})")
    with right:
        if st.button("Pause"):
            repository.update_interview_session(session["id"], {"status": "paused"})
            st.rerun()
        if st.button("Abandon"):
            repository.update_interview_session(session["id"], {"status": "abandoned", "ended_at": datetime.utcnow().isoformat(timespec="seconds")})
            st.warning("Interview abandoned. You can resume later from the history below.")
            st.session_state.pop("live_session_key", None)
            st.rerun()

    st.caption(f"Question {min(question_index + 1, len(question_ids))}/{len(question_ids)} · Mode: {mode}")

    if session["status"] == "paused":
        st.info("Session paused. Resume when you are ready.")
        if st.button("Resume interview"):
            repository.update_interview_session(session["id"], {"status": "active"})
            st.rerun()

    if bool(session.get("voice_mode") or meta.get("voice_mode", False)):
        st.info("Voice interview mode is enabled. Browser microphone support is not guaranteed here; transcript fallback remains available and the app stays in text mode when voice capture is unavailable.")
        if st.button("Use microphone fallback"):
            st.warning("Voice transcription unavailable — use Text Mode")
        st.caption("Speech-to-text and text-to-speech are safe fallbacks only; no fabricated transcript or fake voice output is produced.")

    if question_index < len(question_ids):
        current_question_id = question_ids[question_index]
        current_prompt = _question_prompt(repository, current_question_id, session, ai_service, mode, question_index)
        if not any(message["question_id"] == current_question_id and message["speaker"] == "interviewer" for message in repository.list_interview_messages(session["id"])):
            repository.add_interview_message(session["id"], "interviewer", current_prompt,
                                            question_id=current_question_id, source_question_id=current_question_id,
                                            voice_mode=bool(session.get("voice_mode") or meta.get("voice_mode", False)))

    messages = repository.list_interview_messages(session["id"])
    for message in messages:
        if message["speaker"] == "system":
            st.info(message["message"])
        elif message["speaker"] == "interviewer":
            with st.chat_message("assistant"):
                st.write(message["message"])
        else:
            with st.chat_message("user"):
                st.write(message["message"])

    if session["status"] == "completed":
        if not repository.get_interview_evaluation(session["id"]):
            _generate_interview_evaluation(repository, session, ai_service)
        st.success("Interview completed. Evaluation and mission recommendations were saved.")
        return

    if session["status"] not in {"active", "paused"}:
        return

    answer = st.text_area("Your answer", key=f"live-answer-{session['id']}", height=140)
    if bool(session.get("voice_mode") or meta.get("voice_mode", False)):
        transcript = st.text_input("Transcript", placeholder="Voice transcription unavailable — use Text Mode", key=f"live-transcript-{session['id']}")
        if transcript.strip():
            answer = transcript.strip()
    if st.button("Submit answer"):
        if not answer.strip():
            st.error("Please enter an answer before submitting.")
            return
        current_question_id = question_ids[question_index] if question_index < len(question_ids) else None
        repository.add_interview_message(session["id"], "user", answer.strip(), question_id=current_question_id, source_question_id=current_question_id,
                                        transcript_text=answer.strip() if bool(session.get("voice_mode") or meta.get("voice_mode", False)) else None,
                                        voice_mode=bool(session.get("voice_mode") or meta.get("voice_mode", False)))
        if question_index + 1 >= len(question_ids):
            repository.update_interview_session(
                session["id"],
                {"status": "completed", "current_question": len(question_ids), "completed_questions": len(question_ids), "ended_at": datetime.utcnow().isoformat(timespec="seconds")},
            )
            evaluation = _generate_interview_evaluation(repository, repository.get_interview_session(session["id"]), ai_service)
            repository.add_interview_message(session["id"], "system", "Interview completed. Evaluation and mission recommendations were saved.")
            st.success("Interview completed.")
            st.rerun()
            return
        next_index = question_index + 1
        updated_meta = dict(meta)
        updated_meta["question_index"] = next_index
        repository.update_interview_session(session["id"], {"metadata_json": updated_meta, "current_question": next_index + 1, "completed_questions": next_index})
        next_question_id = question_ids[next_index]
        next_prompt = _question_prompt(repository, next_question_id, session, ai_service, mode, next_index)
        repository.add_interview_message(session["id"], "interviewer", next_prompt, question_id=next_question_id, source_question_id=next_question_id,
                                       voice_mode=bool(session.get("voice_mode") or meta.get("voice_mode", False)))
        st.rerun()

    if st.button("Complete interview"):
        repository.update_interview_session(session["id"], {"status": "completed", "current_question": len(question_ids), "completed_questions": len(question_ids), "ended_at": datetime.utcnow().isoformat(timespec="seconds")})
        updated_session = repository.get_interview_session(session["id"])
        _generate_interview_evaluation(repository, updated_session, ai_service)
        repository.add_interview_message(session["id"], "system", "Interview completed. Evaluation and mission recommendations were saved.")
        st.success("Interview completed.")
        st.rerun()


def render_live_interview(repository: ContentRepository, settings) -> None:
    st.caption("Live interview engine built on the shared database and question bank.")
    ai_service = build_ai_service(getattr(settings, "ai_provider", "mock"), getattr(settings, "ai_api_key", None), getattr(settings, "ai_model", None))
    active = _active_session(repository)
    if active is not None and active["status"] in {"active", "paused", "completed"}:
        _render_active_interview(repository, active, ai_service)
    else:
        _render_setup(repository, ai_service)

    st.subheader("Interview history")
    sessions = repository.list_interview_sessions()
    if not sessions:
        st.info("No interview sessions yet. Start one above to create the first session.")
        return
    for item in sessions[:10]:
        status = item["status"]
        with st.container(border=True):
            st.markdown(f"**{item['role']}** · {item['interview_type']} · {item['difficulty']} · {status}")
            st.caption(f"Questions: {item['question_count']} | Progress: {item['completed_questions']}/{item['question_count']} | topics: {item['selected_topics'] or 'General'}")
            if status in {"active", "paused"}:
                if st.button(f"Resume #{item['id']}", key=f"resume-session-{item['id']}"):
                    st.session_state["live_session_key"] = item["session_key"]
                    repository.update_interview_session(item["id"], {"status": "active"})
                    st.rerun()
