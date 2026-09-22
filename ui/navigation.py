"""Application navigation definitions and sidebar rendering."""

from dataclasses import dataclass
import streamlit as st


@dataclass(frozen=True)
class NavigationItem:
    key: str
    label: str
    description: str


NAVIGATION_ITEMS = (
    NavigationItem("home", "Home / Command Center", "Your Phase 0 preparation workspace."),
    NavigationItem("hr", "HR Screening", "Behavioral interview preparation."),
    NavigationItem("sql", "SQL Technical Notes", "SQL study notes and practice."),
    NavigationItem("technical", "Technical Round", "Technical interview preparation."),
    NavigationItem("project", "Project & Practical", "Project discussion and practical preparation."),
    NavigationItem("candidate", "Candidate Profile", "Your user-provided profile and resume information."),
    NavigationItem("jobs", "Jobs + Resume", "Job and resume preparation foundation."),
    NavigationItem("live", "Non-Technical + Live Interview", "Communication and live interview preparation."),
    NavigationItem("evaluation", "Evaluation", "Interview review, weakness detection, and practice recommendations."),
    NavigationItem("mission", "20-Day Mission", "Adaptive mission priorities from evaluation feedback."),
    NavigationItem("progress", "Progress", "Future progress tracking workspace."),
    NavigationItem("settings", "Settings", "Application configuration."),
)


def render_sidebar() -> str:
    st.sidebar.title("SHYAM-MANUAL")
    st.sidebar.caption("Interview preparation command center")
    return st.sidebar.radio("Navigate", [item.label for item in NAVIGATION_ITEMS])
