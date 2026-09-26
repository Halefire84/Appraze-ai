"""Commercial provenance and ownership watermark for Appraze.

This module is intentionally small and dependency-free. It provides a visible
ownership signal in the running application while the repository license
establishes the actual reuse restrictions.
"""

import streamlit as st

OWNER = "Cooper River Trading Co."
PRODUCT = "Appraze"
COPYRIGHT = "© 2026 Cooper River Trading Co. — Proprietary Commercial Software"


def render_proprietary_watermark() -> None:
    """Render a subtle, persistent provenance notice in the app UI."""
    st.markdown(
        f"""<div style="margin-top:1.5rem;padding:8px 12px;border-top:1px solid #d8e0ea;
font-size:.72rem;color:#5b6b7f;text-align:center;letter-spacing:.02em;">
{COPYRIGHT} · {PRODUCT} · Unauthorized copying or redistribution is not permitted.
</div>""",
        unsafe_allow_html=True,
    )
