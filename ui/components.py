"""Reusable, presentation-only Streamlit components."""

import streamlit as st


def render_page_header(title: str, description: str) -> None:
    st.title(title)
    st.caption(description)


def render_section_header(title: str) -> None:
    st.subheader(title)


def render_empty_state(message: str) -> None:
    st.info(message)


def render_error(message: str) -> None:
    st.error(message)
