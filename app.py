"""SHYAM-MANUAL Streamlit entry point."""

import streamlit as st

from config.settings import get_settings
from data.database import DatabaseError, initialize_database
from data.repositories import ContentRepository
from ui.navigation import NAVIGATION_ITEMS, render_sidebar
from ui.components import render_empty_state, render_page_header
from ui.content_engine import render_content_page, render_home, render_settings
from ui.jobs_resume import render_jobs_resume
from ui.live_interview import render_live_interview
from ui.evaluation import render_evaluation_page, render_mission_page, render_progress_page


@st.cache_resource(show_spinner=False)
def prepare_database(database_path: str) -> None:
    initialize_database(database_path)


def main() -> None:
    settings = get_settings()
    st.set_page_config(
        page_title="SHYAM-MANUAL",
        page_icon="📘",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    try:
        prepare_database(str(settings.database_path))
    except DatabaseError:
        st.error("The local database could not be initialized. Check the logs and DATABASE_PATH.")
        st.stop()

    repository = ContentRepository(settings.database_path)
    selected_page = render_sidebar()
    page = next(item for item in NAVIGATION_ITEMS if item.label == selected_page)
    render_page_header(page.label, page.description)

    if page.key == "home":
        render_home(repository)
    elif page.key == "settings":
        render_settings(repository, settings)
    elif page.key in {"candidate", "jobs"}:
        render_jobs_resume(repository, settings)
    elif page.key == "live":
        render_live_interview(repository, settings)
    elif page.key == "evaluation":
        render_evaluation_page(repository, settings)
    elif page.key == "mission":
        render_mission_page(repository, settings)
    elif page.key == "progress":
        render_progress_page(repository, settings)
    elif page.key in {"hr", "sql", "technical", "project"}:
        category_slugs = {
            "hr": "hr-screening", "sql": "sql-technical-notes", "technical": "technical-round",
            "project": "project-practical",
        }
        category = next((row for row in repository.list_categories()
                         if row["slug"] == category_slugs[page.key]), None)
        if category:
            render_content_page(repository, category)
        else:
            render_empty_state("Category is not available.")
    else:
        render_empty_state("Module will be implemented in a later phase.")


if __name__ == "__main__":
    main()
