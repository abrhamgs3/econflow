"""
EconFlow — Streamlit Entry Point
=================================
This file is a placeholder. The full research dashboard for the
*AI Adoption and Total Factor Productivity* paper has moved to::

    examples/ai_productivity_paper/app/streamlit_app.py

To launch the paper dashboard::

    streamlit run examples/ai_productivity_paper/app/streamlit_app.py

To build your own EconFlow-powered dashboard, see the EconFlow API docs
and use this file as your starting point.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="EconFlow",
    page_icon="📊",
    layout="centered",
)

st.title("📊 EconFlow")
st.markdown(
    """
    This is the EconFlow framework placeholder app.

    For the **AI & Productivity** paper dashboard, run:

    ```bash
    streamlit run examples/ai_productivity_paper/app/streamlit_app.py
    ```
    """
)
