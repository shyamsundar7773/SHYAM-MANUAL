"""Safe provider abstraction for deterministic, non-fabricating job intelligence."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Protocol


class SpeechToTextProvider(Protocol):
    def transcribe(self, *, text: str | None = None, audio_data: Any | None = None,
                   source: str = "microphone") -> dict[str, Any]: ...


class TextToSpeechProvider(Protocol):
    def synthesize(self, text: str, *, voice: str = "default") -> dict[str, Any]: ...


class MockSpeechToTextProvider:
    def transcribe(self, *, text: str | None = None, audio_data: Any | None = None,
                   source: str = "microphone") -> dict[str, Any]:
        transcript = (text or "").strip()
        if not transcript:
            return {
                "provider": "mock",
                "status": "unavailable",
                "transcript": "",
                "message": "Voice transcription unavailable — use Text Mode",
                "source": source,
                "note": "No browser microphone support was detected in this environment.",
            }
        return {
            "provider": "mock",
            "status": "available",
            "transcript": transcript,
            "message": "Transcript captured.",
            "source": source,
        }


class MockTextToSpeechProvider:
    def synthesize(self, text: str, *, voice: str = "default") -> dict[str, Any]:
        content = (text or "").strip()
        if not content:
            return {"provider": "mock", "status": "unavailable", "audio_available": False, "message": "No spoken response generated."}
        return {
            "provider": "mock",
            "status": "available",
            "audio_available": False,
            "voice": voice,
            "message": "Text-to-speech is not configured in this environment; the response remains in text mode.",
            "text": content,
        }


class AIProvider(Protocol):
    def generate(self, prompt: str) -> str: ...

    def analyze_job(self, job_text: str, candidate: dict[str, Any]) -> dict[str, Any]: ...

    def tailor_resume(self, resume: dict[str, Any], job: dict[str, Any] | None = None,
                     candidate: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def start_interview(self, role: str, interview_type: str, difficulty: str,
                       selected_topics: list[str] | None, question_count: int) -> dict[str, Any]: ...

    def generate_next_question(self, role: str, interview_type: str, difficulty: str,
                              selected_topics: list[str] | None, previous_questions: list[str] | None,
                              conversation: list[dict[str, str]] | None) -> dict[str, Any]: ...

    def generate_follow_up(self, question: str, answer: str, role: str, interview_type: str,
                           difficulty: str, selected_topics: list[str] | None,
                           *, job_context: dict[str, Any] | None = None,
                           resume_context: dict[str, Any] | None = None,
                           context: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def complete_interview(self, role: str, interview_type: str, difficulty: str,
                          question_count: int, answered_count: int) -> dict[str, Any]: ...

    def evaluate_answer(self, question: str, answer: str, role: str, interview_type: str,
                        difficulty: str, selected_topics: list[str] | None) -> dict[str, Any]: ...

    def evaluate_interview(self, session: dict[str, Any], repository: Any | None = None) -> dict[str, Any]: ...


class MockAIProvider:
    configured = False

    def generate(self, prompt: str) -> str:
        return "AI provider is not configured. Add a provider to enable analysis."

    def analyze_job(self, job_text: str, candidate: dict[str, Any]) -> dict[str, Any]:
        if not job_text.strip():
            return {"available": False, "reason": "No job text supplied.", "explicit": [], "inferred": []}
        candidate_text = " ".join(str(candidate.get(key) or "") for key in ("skills", "tools", "sql", "experience", "education")).lower()
        words = sorted(set(re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", job_text)))
        explicit = [word for word in words if word.lower() in candidate_text]
        return {
            "available": True,
            "provider": "mock",
            "explicit": [{"term": term, "evidence": "appears in supplied candidate data"} for term in explicit],
            "inferred": [],
            "unverified": [word for word in words if word not in explicit][:30],
            "note": "Deterministic comparison only; no qualifications were inferred.",
        }

    def tailor_resume(self, resume: dict[str, Any], job: dict[str, Any] | None = None,
                     candidate: dict[str, Any] | None = None) -> dict[str, Any]:
        profile = (candidate or {}).copy()
        content = dict(resume or {})
        job_text = " ".join(filter(None, [job.get("title"), job.get("company"), job.get("requirements"), job.get("description")])) if job else ""
        relevant_skills = [item.strip() for item in str(profile.get("skills") or "").split(",") if item.strip()]
        if job_text:
            tokens = sorted(set(re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", job_text.lower())))
            matching = [token for token in tokens if token in " ".join(relevant_skills).lower()]
        else:
            matching = []
        updated = {**content}
        updated.setdefault("summary", profile.get("summary") or "")
        updated.setdefault("skills", {"technical": relevant_skills[:10], "sql": [], "tools": []})
        if matching:
            updated["tailoring_notes"] = [
                {"action": "emphasize", "value": skill, "reason": "Matches the selected job requirement evidence."}
                for skill in matching[:6]
            ]
        else:
            updated["tailoring_notes"] = [{
                "action": "review",
                "value": "No directly matching evidence found in the supplied candidate data.",
                "reason": "Keep the resume truthful and preserve missing/unclear items.",
            }]
        return {
            "provider": "mock",
            "status": "safe-fallback",
            "tailored": updated,
            "suggestions": [],
            "note": "No unverified qualifications were invented; suggestions are reviewable and non-destructive.",
        }

    def match_candidate(self, job_text: str, candidate: dict[str, Any]) -> dict[str, Any]:
        analysis = self.analyze_job(job_text, candidate)
        explicit = [item["term"] for item in analysis.get("explicit", [])]
        unclear = analysis.get("unverified", [])
        return {
            "available": analysis.get("available", False),
            "matched": explicit,
            "missing": [],
            "unclear": unclear,
            "inferred": [],
            "note": "Missing qualifications are not asserted without explicit candidate evidence.",
        }

    def start_interview(self, role: str, interview_type: str, difficulty: str,
                       selected_topics: list[str] | None, question_count: int) -> dict[str, Any]:
        return {
            "provider": "mock",
            "status": "ready",
            "message": f"Starting a {difficulty} {interview_type.lower()} interview for {role}.",
            "question_count": max(1, int(question_count)),
            "selected_topics": selected_topics or ["general"],
            "mode": "safe-fallback",
            "note": "The provider is not configured; this is a deterministic fallback and no AI-generated claims are made.",
        }

    def generate_next_question(self, role: str, interview_type: str, difficulty: str,
                              selected_topics: list[str] | None, previous_questions: list[str] | None,
                              conversation: list[dict[str, str]] | None) -> dict[str, Any]:
        topics = selected_topics or ["general"]
        focus = topics[0]
        hint = "Please give a clear answer with an example when possible."
        question = (
            f"For a {difficulty} {interview_type.lower()} interview in {role}, explain how you would approach "
            f"{focus} and what trade-offs you would consider. {hint}"
        )
        return {"provider": "mock", "question": question, "mode": "safe-fallback",
                "source": "deterministic-fallback", "note": "This is a safe fallback question, not a fabricated AI interview."}

    def generate_follow_up(self, question: str, answer: str, role: str, interview_type: str,
                           difficulty: str, selected_topics: list[str] | None,
                           *, job_context: dict[str, Any] | None = None,
                           resume_context: dict[str, Any] | None = None,
                           context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        job_context = job_context or context.get("job") or {}
        resume_context = resume_context or context.get("resume") or {}
        topic = (selected_topics or ["general"])[0]
        if job_context.get("title"):
            follow_up = (
                f"Good. For the {job_context.get('title')} role at {job_context.get('company') or 'the company'}, "
                f"what would you change in your answer if the business goal shifted or the data quality were poor?"
            )
        elif resume_context.get("title"):
            follow_up = (
                f"Good. Based on your {resume_context.get('title') or 'resume'} experience, how would you explain the trade-off "
                f"you made and what you learned from it?"
            )
        else:
            follow_up = (
                f"Good. For {topic}, how would your answer change if the requirements were unclear or the data quality were poor?"
            )
        return {"provider": "mock", "question": follow_up, "mode": "safe-fallback",
                "source": "deterministic-fallback", "note": "Follow-up is contextual but generated from a safe deterministic template."}

    def complete_interview(self, role: str, interview_type: str, difficulty: str,
                          question_count: int, answered_count: int) -> dict[str, Any]:
        return {
            "provider": "mock",
            "status": "completed",
            "message": f"Interview completed for {role} with {answered_count}/{max(1, int(question_count))} responses captured.",
            "mode": "safe-fallback",
            "note": "No evaluation or score was generated in this phase.",
        }

    def evaluate_answer(self, question: str, answer: str, role: str, interview_type: str,
                        difficulty: str, selected_topics: list[str] | None) -> dict[str, Any]:
        text = (answer or "").strip()
        word_count = len(re.findall(r"\b\w+\b", text)) if text else 0
        brief = word_count < 12
        contains_example = any(token in text.lower() for token in ("example", "for example", "e.g.", "because"))
        completeness = "strong" if word_count >= 40 and contains_example else "moderate" if word_count >= 20 else "limited"
        relevance = "high" if text else "missing"
        clarity = "clear" if word_count >= 15 else "brief"
        reasoning = "sound" if "because" in text.lower() or "since" in text.lower() else "limited"
        structure = "organized" if any(marker in text.lower() for marker in ("first", "then", "finally", "because")) else "basic"
        return {
            "provider": "mock",
            "status": "structured-fallback",
            "question": question,
            "answer": answer,
            "answer_completeness": completeness,
            "relevance": relevance,
            "clarity": clarity,
            "reasoning": reasoning,
            "structure": structure,
            "technical_correctness": "not_assessed" if interview_type.lower() != "hr" else "documented",
            "follow_up_handling": "pending" if not text else "observed",
            "what_went_well": ["The candidate provided a direct answer."] if text else ["No answer was provided for the question."],
            "what_was_missing": ["Add a concrete example or clearer reasoning."] if brief else [],
            "improvement_guidance": "Add a structure, an example, and a clear conclusion.",
            "source": "structured-fallback",
            "note": "This is a structured non-AI analysis based on answer presence and topic context; it does not claim a real AI evaluation.",
        }

    def evaluate_interview(self, session: dict[str, Any], repository: Any | None = None) -> dict[str, Any]:
        if not session:
            raise ValueError("session is required")
        role = str(session.get("role") or "Candidate")
        interview_type = str(session.get("interview_type") or "Mixed")
        difficulty = str(session.get("difficulty") or "medium")
        selected_topics = list(session.get("selected_topics") or [])
        if isinstance(selected_topics, str):
            selected_topics = [item.strip() for item in selected_topics.split(",") if item.strip()]
        session_id = session.get("id")
        question_evaluations: list[dict[str, Any]] = []
        if repository is not None and session_id is not None:
            messages = repository.list_interview_messages(int(session_id))
            questions: list[dict[str, Any]] = []
            pending_answer = None
            for item in messages:
                if item["speaker"] == "interviewer":
                    pending_answer = {
                        "question": item["message"],
                        "question_id": item["question_id"],
                    }
                elif item["speaker"] == "user" and pending_answer is not None:
                    pending_answer["answer"] = item["message"]
                    questions.append(pending_answer)
                    pending_answer = None
            if pending_answer is not None:
                pending_answer["answer"] = ""
                questions.append(pending_answer)
            if questions:
                for item in questions:
                    question = item.get("question") or ""
                    answer = item.get("answer") or ""
                    evaluation = self.evaluate_answer(question, answer, role, interview_type, difficulty, selected_topics)
                    evaluation["question_id"] = item.get("question_id")
                    evaluation["question"] = question
                    evaluation["answer"] = answer
                    question_evaluations.append(evaluation)
        if not question_evaluations:
            question_evaluations = [{
                "question": "Interview response review",
                "answer": "No explicit answer text was captured for this interview.",
                "question_id": None,
                "answer_completeness": "limited",
                "relevance": "missing",
                "clarity": "brief",
                "reasoning": "limited",
                "structure": "basic",
                "technical_correctness": "not_assessed",
                "follow_up_handling": "pending",
                "what_went_well": ["The interview started and was recorded."],
                "what_was_missing": ["Add specific examples and clearer reasoning."],
                "improvement_guidance": "Document a clear answer structure and at least one concrete example.",
                "source": "structured-fallback",
            }]

        scored = [item for item in question_evaluations if item.get("answer_completeness") in {"limited", "moderate", "strong"}]
        strong = sum(1 for item in scored if item.get("answer_completeness") == "strong")
        weak = sum(1 for item in scored if item.get("answer_completeness") in {"limited", "moderate"})
        strengths = ["The interview included recorded questions and answers." ]
        if strong:
            strengths.append(f"{strong} answer(s) showed strong structure and detail.")
        if weak:
            strengths.append(f"{weak} answer(s) could be tightened with clearer examples and reasoning.")
        summary = {
            "interview_id": session.get("id"),
            "status": "structured-fallback",
            "overall_summary": (
                "Structured fallback analysis reviewed answer clarity, structure, and topic relevance. "
                f"{strong} responses were strong and {weak} needed improvement."
            ),
            "strengths": strengths,
            "weaknesses": ["Responses with limited detail need clearer examples and a stronger conclusion."] if weak else [],
            "key_observations": [
                "No external AI provider was configured, so this evaluation uses the safe deterministic fallback.",
                f"Selected focus: {', '.join(selected_topics) if selected_topics else 'general'}.",
            ],
            "recommended_next_steps": [
                "Review the weakest answers and rewrite them with a short structure, an example, and a clear conclusion.",
                "Practice the problem areas highlighted in the follow-up recommendations.",
            ],
            "mode": "structured-fallback",
            "note": "This is a deterministic, non-AI evaluation designed to remain truthful and safe.",
        }
        summary["question_evaluations"] = question_evaluations
        return summary


@dataclass
class AIService:
    provider: AIProvider
    speech_to_text_provider: SpeechToTextProvider = None
    text_to_speech_provider: TextToSpeechProvider = None

    def __post_init__(self):
        if self.speech_to_text_provider is None:
            self.speech_to_text_provider = MockSpeechToTextProvider()
        if self.text_to_speech_provider is None:
            self.text_to_speech_provider = MockTextToSpeechProvider()

    def generate(self, prompt: str) -> str:
        if not prompt.strip():
            raise ValueError("AI prompt cannot be empty")
        return self.provider.generate(prompt)

    def analyze_job(self, job_text: str, candidate: dict[str, Any]) -> dict[str, Any]:
        return self.provider.analyze_job(job_text, candidate)

    def tailor_resume(self, resume: dict[str, Any], job: dict[str, Any] | None = None,
                     candidate: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.provider.tailor_resume(resume, job=job, candidate=candidate)

    def match_candidate(self, job_text: str, candidate: dict[str, Any]) -> dict[str, Any]:
        return self.provider.match_candidate(job_text, candidate)

    def start_interview(self, role: str, interview_type: str, difficulty: str,
                       selected_topics: list[str] | None, question_count: int) -> dict[str, Any]:
        return self.provider.start_interview(role, interview_type, difficulty, selected_topics, question_count)

    def generate_next_question(self, role: str, interview_type: str, difficulty: str,
                              selected_topics: list[str] | None, previous_questions: list[str] | None,
                              conversation: list[dict[str, str]] | None) -> dict[str, Any]:
        return self.provider.generate_next_question(role, interview_type, difficulty, selected_topics,
                                                  previous_questions, conversation)

    def generate_follow_up(self, question: str, answer: str, role: str, interview_type: str,
                           difficulty: str, selected_topics: list[str] | None,
                           *, job_context: dict[str, Any] | None = None,
                           resume_context: dict[str, Any] | None = None,
                           context: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.provider.generate_follow_up(
            question,
            answer,
            role,
            interview_type,
            difficulty,
            selected_topics,
            job_context=job_context,
            resume_context=resume_context,
            context=context,
        )

    def transcribe_audio(self, *, text: str | None = None, audio_data: Any | None = None,
                        source: str = "microphone") -> dict[str, Any]:
        return self.speech_to_text_provider.transcribe(text=text, audio_data=audio_data, source=source)

    def synthesize_speech(self, text: str, *, voice: str = "default") -> dict[str, Any]:
        return self.text_to_speech_provider.synthesize(text, voice=voice)

    def complete_interview(self, role: str, interview_type: str, difficulty: str,
                          question_count: int, answered_count: int) -> dict[str, Any]:
        return self.provider.complete_interview(role, interview_type, difficulty, question_count, answered_count)

    def evaluate_answer(self, question: str, answer: str, role: str, interview_type: str,
                        difficulty: str, selected_topics: list[str] | None) -> dict[str, Any]:
        return self.provider.evaluate_answer(question, answer, role, interview_type, difficulty, selected_topics)

    def evaluate_interview(self, session: dict[str, Any], repository: Any | None = None) -> dict[str, Any]:
        return self.provider.evaluate_interview(session, repository)

    def detect_weaknesses(self, evaluation: dict[str, Any], repository: Any | None = None) -> list[dict[str, Any]]:
        weaknesses: list[dict[str, Any]] = []
        for item in evaluation.get("question_evaluations", []):
            if item.get("answer_completeness") in {"limited", "moderate"}:
                weakness_name = self._weakness_name(item.get("question") or "answer quality")
                weaknesses.append({
                    "name": weakness_name,
                    "description": "Answer completeness was limited or missing relevant detail.",
                    "evidence": item.get("answer") or "No answer captured.",
                    "question_id": item.get("question_id"),
                    "confidence": "medium",
                    "severity": "medium",
                    "category": "general",
                    "source": "structured-fallback",
                })
        return weaknesses

    def map_skills(self, weaknesses: list[dict[str, Any]], repository: Any | None = None) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        if repository is None:
            return mapped
        for weakness in weaknesses:
            name = str(weakness.get("name") or "")
            lower = name.lower()
            if "join" in lower:
                module = repository.list_modules()
                category = next((c for c in repository.list_categories() if c["slug"] == "sql-technical-notes"), None)
                rows = repository.list_questions(category_id=(category["id"] if category else None), search="join", limit=3)
            elif "window" in lower:
                category = next((c for c in repository.list_categories() if c["slug"] == "technical-round"), None)
                rows = repository.list_questions(category_id=(category["id"] if category else None), search="window", limit=3)
            elif "project" in lower or "architecture" in lower:
                category = next((c for c in repository.list_categories() if c["slug"] == "project-practical"), None)
                rows = repository.list_questions(category_id=(category["id"] if category else None), search="architecture", limit=3)
            else:
                rows = repository.list_questions(limit=3)
            mapped.append({"weakness": name, "related_questions": [dict(row) for row in rows], "category": weakness.get("category") or "general"})
        return mapped

    def recommend_practice(self, weaknesses: list[dict[str, Any]], repository: Any | None = None) -> list[dict[str, Any]]:
        recommendations: list[dict[str, Any]] = []
        for index, weakness in enumerate(weaknesses, 1):
            name = str(weakness.get("name") or "Practice area")
            mapped = self.map_skills([weakness], repository)
            questions = mapped[0]["related_questions"] if mapped else []
            recommendations.append({
                "priority": min(3, max(1, index)),
                "reason": weakness.get("description") or "Question quality needs more support.",
                "weakness": name,
                "recommended_question": questions[0]["question"] if questions else "Review the relevant manual notes and practice questions.",
                "practice_objective": f"Strengthen {name.lower()} with targeted review and a short practice set.",
                "source": weakness.get("source") or "structured-fallback",
            })
        return recommendations

    def update_adaptive_mission(self, session_id: int | str, repository: Any | None = None, evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
        if repository is None:
            return {"updated": False, "reason": "repository missing"}
        session = repository.get_interview_session(session_id)
        if session is None:
            return {"updated": False, "reason": "session missing"}
        items = evaluation.get("question_evaluations", []) if evaluation else []
        for item in items:
            if item.get("answer_completeness") in {"limited", "moderate"}:
                weakness_name = self._weakness_name(item.get("question") or "answer quality")
                repository.save_mission_adaptation({
                    "session_id": session["id"],
                    "weakness_name": weakness_name,
                    "priority": "high" if item.get("answer_completeness") == "limited" else "medium",
                    "reason": "Priority increased because this topic was identified as a weakness in the latest interview.",
                    "topic_name": weakness_name,
                    "status": "active",
                })
        return {"updated": True, "session_id": session["id"], "count": len(items)}

    @staticmethod
    def _weakness_name(question: str) -> str:
        lowered = (question or "").lower()
        if "join" in lowered:
            return "SQL JOIN reasoning"
        if "window" in lowered:
            return "Window Function understanding"
        if "project" in lowered or "architecture" in lowered:
            return "Explaining project architecture"
        if "behavior" in lowered or "story" in lowered or "describe" in lowered:
            return "Structured behavioral response"
        if "sql" in lowered or "query" in lowered:
            return "Query reasoning"
        return "Answer completeness"


def build_ai_service(provider_name: str = "mock", api_key: str | None = None,
                     model: str | None = None) -> AIService:
    return AIService(provider=MockAIProvider(),
                     speech_to_text_provider=MockSpeechToTextProvider(),
                     text_to_speech_provider=MockTextToSpeechProvider())
