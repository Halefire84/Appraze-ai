# Appraze™ — Complete Resale Business Suite
# © 2026 Christopher Hale / Cooper River Trading Co.
#
# In memory of my father, Christopher Hale, who tracked trucks in C++
# before I ever tracked a deal.

"""Beta feedback / bug reports.

2026-09-21: added for tomorrow's beta -- beta users need an easy, always-
visible way to report a bug or say what they think without leaving the
app or knowing an email address. Submissions are appended to a shared
table ("beta_feedback") via the same Apps Script save_data/load_data
backend every other table in this app already uses (see storage.py),
so Chris can read them straight out of the Sheet even without opening
this page -- no new external service, no new secret required.
"""

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Appraze — Feedback", page_icon="🐛", layout="wide")
from ui_theme import inject_theme
inject_theme()
from auth import require_auth, get_visit_count
require_auth()

from storage import load_table, save_table

FEEDBACK_TABLE = "beta_feedback"
CATEGORIES = ["Bug", "Something's confusing", "Feature idea", "Other"]

st.title("🐛 Feedback & Bug Reports")
st.caption("Beta is rough around the edges on purpose -- tell us what broke or what you'd want. This goes straight to Chris.")

with st.form("feedback_form", clear_on_submit=True):
    category = st.selectbox("What's this about?", CATEGORIES)
    message = st.text_area(
        "Tell us what happened (or what you'd want)",
        height=140,
        placeholder="The more specific, the faster it gets fixed -- what page were you on, what did you expect, what happened instead?",
    )
    submitted = st.form_submit_button("Send feedback", use_container_width=True)

    if submitted:
        if not message.strip():
            st.warning("Add a few words about what's going on first.")
        else:
            result = load_table(FEEDBACK_TABLE, shared=True)
            existing = result.payload if (result.success and result.payload) else []
            existing.append({
                "username": st.session_state.get("username", ""),
                "display_name": st.session_state.get("user_display_name", ""),
                "category": category,
                "message": message.strip(),
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            })
            save_result = save_table(pd.DataFrame(existing), FEEDBACK_TABLE, shared=True)
            if save_result.success:
                st.success("Thanks -- got it. Chris will see this.")
            else:
                st.error(f"Couldn't send that right now ({save_result.error or 'storage unreachable'}). Try again in a moment.")

if st.session_state.get("user_is_admin"):
    st.markdown("---")
    st.subheader("Admin — beta stats")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total visits", get_visit_count())
    with col2:
        result = load_table(FEEDBACK_TABLE, shared=True)
        entries = result.payload if (result.success and result.payload) else []
        st.metric("Feedback submitted", len(entries))

    if entries:
        st.dataframe(
            pd.DataFrame(entries).sort_values("submitted_at", ascending=False),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No feedback yet.")
