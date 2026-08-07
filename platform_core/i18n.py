from __future__ import annotations

import streamlit as st


LANGUAGE_KEY = "platform_language"


def language_selector() -> str:
    labels = {"zh": "中文", "en": "English"}
    current = st.session_state.get(LANGUAGE_KEY, "zh")
    selected = st.sidebar.selectbox(
        "语言 / Language",
        list(labels),
        index=list(labels).index(current) if current in labels else 0,
        format_func=labels.get,
        key=LANGUAGE_KEY,
    )
    return str(selected)


def language() -> str:
    return str(st.session_state.get(LANGUAGE_KEY, "zh"))


def tr(zh: str, en: str) -> str:
    return zh if language() == "zh" else en
