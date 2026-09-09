"""Appraze Opportunity Radar — marketplace listing triage."""

import pandas as pd
import streamlit as st

from opportunity_radar import analyze_listing, rank_listings

st.set_page_config(page_title="Appraze — Opportunity Radar", page_icon="🔎", layout="wide")

st.title("🔎 Opportunity Radar")
st.caption("Find listings that deserve a second look before other buyers notice them.")

st.info(
    "Radar signals are leads, not proof of value. Always verify authenticity, condition, "
    "sold comps, shipping, and category before buying."
)

with st.expander("Add a listing manually", expanded=True):
    c1, c2 = st.columns([2, 1])
    with c1:
        title = st.text_input("Title", placeholder="e.g. vinta ge 14k gold chain")
        description = st.text_area("Description", height=120)
    with c2:
        category = st.text_input("Category", placeholder="Jewelry")
        price = st.number_input("Asking price", min_value=0.0, value=0.0, step=5.0)
        estimated_value = st.number_input("Estimated value (optional)", min_value=0.0, value=0.0, step=10.0)
        expected = st.text_input("Expected category keywords", placeholder="gold, chain, jewelry")

    if st.button("Analyze listing", type="primary", use_container_width=True):
        listing = {
            "title": title,
            "description": description,
            "category": category,
            "price": price,
            "estimated_value": estimated_value or None,
            "expected_keywords": [x.strip() for x in expected.split(",") if x.strip()],
        }
        result = analyze_listing(listing)
        st.session_state["radar_last"] = result

if "radar_last" in st.session_state:
    result = st.session_state["radar_last"]
    score = result.opportunity_score
    if score >= 70:
        st.success(f"🔥 HIGH-PRIORITY OPPORTUNITY — {score:.0f}/100")
    elif score >= 40:
        st.warning(f"🟡 WORTH REVIEW — {score:.0f}/100")
    elif score >= 25:
        st.info(f"🔎 REVIEW — {score:.0f}/100")
    else:
        st.caption(f"Radar score: {score:.0f}/100")

    if result.signals:
        st.markdown("#### Why it was flagged")
        for signal in result.signals:
            st.write(f"**{signal.severity.upper()} · +{signal.score:.0f}** — {signal.message}")
    else:
        st.write("No strong anomaly signals detected.")

st.markdown("---")
st.markdown("#### Batch scan")
st.caption("Upload a CSV with columns such as title, description, category, price, and estimated_value.")

uploaded = st.file_uploader("Listing CSV", type=["csv"])
if uploaded:
    try:
        source = pd.read_csv(uploaded)
        records = source.to_dict("records")
        ranked = rank_listings(records)
        rows = []
        for listing, result in ranked:
            rows.append({
                "Opportunity Score": result.opportunity_score,
                "Title": listing.get("title", ""),
                "Price": listing.get("price", ""),
                "Estimated Value": listing.get("estimated_value", ""),
                "Review": "YES" if result.review_required else "—",
                "Signals": " | ".join(s.message for s in result.signals),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"Could not scan this CSV: {exc}")
