"""Phase 1 database-driven command center and content management UI."""

import json
import streamlit as st

from data.repositories import ContentRepository
from ui.components import render_empty_state, render_error


def _copy_buttons(question: str, answer: str | None, key_prefix: str) -> None:
    values = json.dumps({"question": question or "", "answer": answer or ""})
    st.html(
        f"""<div style="display:flex;gap:4px">
        <button id="{key_prefix}-q" style="padding:5px 10px;cursor:pointer">Copy question</button>
        {f'<button id="{key_prefix}-a" style="padding:5px 10px;cursor:pointer">Copy answer</button>' if answer else ""}
        </div>
        <script>
        const values = {values};
        async function copyValue(button, value) {{
          try {{ await navigator.clipboard.writeText(value); button.innerText = "Copied"; }}
          catch (e) {{ window.prompt("Copy this text:", value); }}
        }}
        document.getElementById("{key_prefix}-q").onclick = function() {{
          copyValue(this, values.question);
        }};
        {f'document.getElementById("{key_prefix}-a").onclick = function() {{ copyValue(this, values.answer); }};' if answer else ""}
        </script>""",
        unsafe_allow_javascript=True,
    )


def _question_card(question, repository: ContentRepository, editable: bool = True,
                   key_prefix: str = "question") -> None:
    with st.container(border=True):
        st.markdown(f"**{question['question']}**")
        st.caption(" · ".join(filter(None, [question["question_type"], question["difficulty"],
                                             question["category_name"], question["module_name"],
                                             question["topic_name"]])))
        if question["tag_names"]:
            st.caption(f"Tags: {question['tag_names']}")
        if question["interview_style"] or question["interviewer_expectation"]:
            st.caption("Interview style: " + (question["interview_style"] or "technical"))
            if question["interviewer_expectation"]:
                st.info(f"Interviewer expects: {question['interviewer_expectation']}")
        left, right = st.columns([3, 1])
        with left:
            if st.toggle("Show answer", key=f"{key_prefix}-answer-{question['id']}"):
                st.write(question["answer"] or "No answer recorded.")
                if question["personal_answer"]:
                    st.markdown("**My personal answer**")
                    st.write(question["personal_answer"])
                if question["explanation"]:
                    st.caption(question["explanation"])
                for label, key in (("Thinking approach", "thinking_approach"),
                                   ("SQL solution", "sql_solution"),
                                   ("Alternative solution", "alternative_solution"),
                                   ("Common trap", "common_trap"),
                                   ("Follow-up", "follow_up")):
                    if question[key]:
                        st.markdown(f"**{label}**")
                        st.code(question[key], language="sql") if "solution" in key else st.write(question[key])
        with right:
            _copy_buttons(question["question"], question["answer"],
                          f"{key_prefix}-copy-{question['id']}")
            if editable:
                if st.button("Edit", key=f"edit-{question['id']}"):
                    st.session_state["edit_question_id"] = question["id"]
                    st.rerun()
                if st.button("Delete", key=f"delete-{question['id']}"):
                    st.session_state["delete_question_id"] = question["id"]
                    st.rerun()


def _question_form(repository: ContentRepository, categories, modules, topics, question=None) -> None:
    editing = question is not None
    st.subheader("Edit question" if editing else "Add question")
    category_options = {row["name"]: row["id"] for row in categories}
    module_options = {"(none)": None, **{row["name"]: row["id"] for row in modules}}
    topic_options = {"(none)": None, **{row["name"]: row["id"] for row in topics}}
    category_name = next((name for name, value in category_options.items()
                          if value == (question["category_id"] if editing else None)), next(iter(category_options), ""))
    module_name = next((name for name, value in module_options.items()
                        if value == (question["module_id"] if editing else None)), "(none)")
    topic_name = next((name for name, value in topic_options.items()
                       if value == (question["topic_id"] if editing else None)), "(none)")
    form_key = f"question-form-{question['id']}" if editing else "question-form-new"
    with st.form(form_key):
        category = st.selectbox("Category", list(category_options), index=list(category_options).index(category_name))
        module = st.selectbox("Module", list(module_options), index=list(module_options).index(module_name))
        topic = st.selectbox("Topic", list(topic_options), index=list(topic_options).index(topic_name))
        text = st.text_area("Question", value=question["question"] if editing else "")
        answer = st.text_area("Answer", value=question["answer"] or "" if editing else "")
        personal_answer = st.text_area(
            "Personal answer / notes",
            value=question["personal_answer"] or "" if editing else "",
            help="Add your own truthful answer or placeholders; never invent personal facts.",
        )
        explanation = st.text_area("Explanation", value=question["explanation"] or "" if editing else "")
        qtype, difficulty = st.columns(2)
        with qtype:
            question_type = st.text_input("Type", value=question["question_type"] if editing else "general")
        with difficulty:
            level = st.selectbox("Difficulty", ["easy", "medium", "hard"],
                                 index=["easy", "medium", "hard"].index(question["difficulty"])
                                 if editing and question["difficulty"] in {"easy", "medium", "hard"} else 1)
        tags = st.text_input("Tags (comma-separated)",
                             value=", ".join(repository.get_question_tags(question["id"])) if editing else "")
        trick = st.text_area("Interview trick", value=question["interview_trick"] or "" if editing else "")
        follow_up = st.text_area("Follow-up", value=question["follow_up"] or "" if editing else "")
        metadata = {}
        if True:
            for label, key in (("Interviewer expectation", "interviewer_expectation"),
                               ("Thinking approach", "thinking_approach"),
                               ("SQL solution", "sql_solution"),
                               ("Alternative solution", "alternative_solution"),
                               ("Common trap", "common_trap"),
                               ("Interview style", "interview_style"),
                               ("Source", "source")):
                metadata[key] = st.text_area(label, value=(question[key] or "") if editing else "")
        submitted = st.form_submit_button("Save question")
    if submitted:
        try:
            values = {"category_id": category_options[category], "module_id": module_options[module],
                      "topic_id": topic_options[topic], "question": text, "answer": answer,
                      "personal_answer": personal_answer, "explanation": explanation,
                      "question_type": question_type, "difficulty": level, "tags": tags}
            values["interview_trick"] = trick
            values["follow_up"] = follow_up
            values.update(metadata)
            if editing:
                repository.update_question(question["id"], values)
            else:
                repository.create_question(values)
            st.session_state.pop("edit_question_id", None)
            st.success("Question saved.")
            st.rerun()
        except (ValueError, KeyError) as exc:
            render_error(str(exc))


def render_home(repository: ContentRepository) -> None:
    questions = repository.count_questions()
    categories = repository.list_categories()
    modules = len(repository.list_modules())
    topics = len(repository.list_topics())
    st.subheader("Command center")
    cols = st.columns(4)
    for col, label, value in zip(cols, ("Questions", "Categories", "Modules", "Topics"),
                                 (questions, len(categories), modules, topics)):
        col.metric(label, value)
    st.info("Preparation status: content engine ready and adaptive interview follow-up is active.")
    if st.button("Start Today's Mission", type="primary"):
        st.info("Open the 20-Day Mission page to review the latest adaptive priorities.")
    st.subheader("Quick navigation")
    st.caption("Choose a category from the sidebar to browse modules, topics, and questions.")
    for category in categories[:6]:
        st.markdown(f"**{category['name']}** — {category['description'] or 'No description yet.'}")
    global_search = st.text_input("Search all content", placeholder="Question, answer, topic, tag, module, or category")
    if global_search:
        results = repository.search_questions(global_search, limit=20)
        st.caption(f"{len(results)} matching question(s)")
        if not results:
            render_empty_state("No matching content found.")
        for question in results:
            _question_card(question, repository, editable=False, key_prefix="global-search")
    st.subheader("Recent content")
    recent = repository.recent_questions(5)
    if not recent:
        render_empty_state("No questions yet. Add your first question from a content section.")
    for question in recent:
        _question_card(question, repository, editable=False, key_prefix="recent")
    st.subheader("Recently updated")
    updated = repository.list_questions(sort_by="updated_at", limit=5)
    if not updated:
        render_empty_state("No content has been updated yet.")
    for question in updated:
        _question_card(question, repository, editable=False, key_prefix="updated")


def _render_sql_learning(repository: ContentRepository, topic) -> None:
    st.subheader("Learning manual")
    notes = repository.list_notes(topic_id=topic["id"])
    examples = repository.list_examples(topic_id=topic["id"])
    tricks = repository.list_tricks(topic_id=topic["id"])
    sections = {"Concept / mental model": [n for n in notes if n["title"] == "Concept and mental model"],
                "Syntax": [n for n in notes if n["title"] == "Syntax"],
                "Real-world use": [n for n in notes if n["title"] == "Real-world use"],
                "Common mistakes": [n for n in notes if n["title"] == "Common mistakes"],
                "Examples": examples, "Memory tricks": tricks}
    for title, rows in sections.items():
        if rows:
            st.markdown(f"**{title}**")
            for row in rows:
                st.caption(row["title"])
                if title in {"Syntax", "Examples"}:
                    st.code(row["body"], language="sql")
                else:
                    st.write(row["body"])


def render_content_page(repository: ContentRepository, category) -> None:
    st.subheader(f"{category['name']} content")
    modules = repository.list_modules(category["id"])
    module_names = ["All modules"] + [row["name"] for row in modules]
    selected_module = st.selectbox("Browse module", module_names)
    module = next((row for row in modules if row["name"] == selected_module), None)
    topics = (repository.list_topics(module["id"]) if module else
              repository.list_topics_for_category(category["id"]))
    topic_names = ["All topics"] + [row["name"] for row in topics]
    selected_topic = st.selectbox("Browse topic", topic_names)
    topic = next((row for row in topics if row["name"] == selected_topic), None)
    if category["slug"] == "sql-technical-notes" and topic:
        _render_sql_learning(repository, topic)
    practice_size = 10
    practice_difficulty = None
    practice_style = None
    if category["slug"] in {"technical-round", "project-practical"}:
        with st.expander("Practice set", expanded=True):
            practice_size = st.slider("Questions", 1, 30, 10)
            practice_difficulty = st.selectbox("Practice difficulty", ["All", "easy", "medium", "hard"])
            if category["slug"] == "project-practical":
                style_labels = {
                    "All": None, "Project Explanation": "project-explanation",
                    "SQL Practical": "sql-practical", "Business Scenario": "business-scenario",
                    "Data Quality": "data-quality", "Mixed Project": None,
                    "Follow-up": "follow-up",
                }
                selected_style = st.selectbox("Practice set type", list(style_labels))
                practice_style = style_labels[selected_style]
            else:
                practice_style = st.selectbox("Interview style", ["All", "technical"])
            if st.button("Start practice set"):
                st.session_state["practice_questions"] = repository.practice_set(
                    category_id=category["id"], module_id=module["id"] if module else None,
                    topic_id=topic["id"] if topic else None,
                    difficulty=None if practice_difficulty == "All" else practice_difficulty,
                    interview_type=None if practice_style == "All" else practice_style,
                    size=practice_size, randomize=True)
        if st.session_state.get("practice_questions"):
            st.subheader("Practice set")
            for question in st.session_state["practice_questions"]:
                _question_card(question, repository, editable=False, key_prefix="practice")
    with st.expander("+ ADD QUESTION"):
        _question_form(repository, [category], modules, topics)
    with st.expander("Search and filter", expanded=True):
        search = st.text_input("Search questions, answers, topics, tags, modules, or categories")
        difficulty = st.selectbox("Difficulty", ["All", "easy", "medium", "hard"])
        question_types = repository.list_question_types(category["id"])
        question_type = st.selectbox("Question type", ["All"] + question_types)
        tags = [row["name"] for row in repository.list_tags()]
        selected_tags = st.multiselect("Tags", tags)
        sort = st.selectbox("Sort", ["updated_at", "created_at", "question", "difficulty"])
    edit_id = st.session_state.get("edit_question_id")
    if edit_id:
        existing = repository.get_question(edit_id)
        if existing:
            _question_form(repository, [category], modules, topics, existing)
    if st.session_state.get("delete_question_id"):
        delete_id = st.session_state["delete_question_id"]
        st.warning("Delete this question permanently?")
        if st.button("Confirm delete", key="confirm-delete"):
            repository.delete_question(delete_id)
            st.session_state.pop("delete_question_id")
            st.rerun()
    filters = dict(category_id=category["id"], module_id=module["id"] if module else None,
                   topic_id=topic["id"] if topic else None, search=search,
                   difficulty=None if difficulty == "All" else difficulty,
                   question_type=None if question_type == "All" else question_type,
                   tags=selected_tags, sort_by=sort)
    total_questions = repository.count_questions(**filters)
    page_size = st.selectbox("Questions per page", [10, 20, 50], index=1, key="content-page-size")
    page_count = max(1, (total_questions + page_size - 1) // page_size)
    page_number = st.number_input("Question page", min_value=1, max_value=page_count,
                                  value=min(st.session_state.get("content-page-number", 1), page_count),
                                  step=1, key="content-page-number")
    rows = repository.list_questions(**filters, limit=page_size, offset=(page_number - 1) * page_size)
    st.caption(f"Showing {((page_number - 1) * page_size) + 1 if total_questions else 0}-"
               f"{min(page_number * page_size, total_questions)} of {total_questions} question(s)")
    if not rows:
        render_empty_state("No questions added yet. Use + ADD QUESTION to create the first one.")
    for question in rows:
        _question_card(question, repository)


def render_settings(repository: ContentRepository, settings) -> None:
    st.subheader("Settings")
    st.write("Configuration is loaded from environment variables.")
    st.write(f"Database status: {'Connected' if repository.list_categories() else 'Unavailable'}")
    st.write(f"AI provider status: {'Configured' if settings.ai_api_key else 'Safe mock mode'}")
    st.write(f"Configuration status: {'Valid' if settings.database_path else 'Incomplete'}")
    st.write("Application version: Phase 6")
    st.write("System: SQLite + Streamlit")
    st.code(f"DATABASE_PATH={settings.database_path}\nAI_PROVIDER={settings.ai_provider}\n"
            f"AI_MODEL={settings.ai_model or '(not configured)'}")
    st.caption("API keys are never displayed.")
