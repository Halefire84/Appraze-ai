"""Appraze Opportunity Radar — marketplace listing triage."""

import pandas as pd
import streamlit as st

from comps_adapters import EbayAuthError
from opportunity_radar import analyze_listing, rank_listings
from opportunity_sources import scan_ebay

st.set_page_config(page_title="Appraze — Opportunity Radar", page_icon="🔎", layout="wide")

st.title("🔎 Opportunity Radar")
st.caption("Find listings that deserve a second look before other buyers notice them.")

st.info(
    "Radar signals are leads, not proof of value. Always verify authenticity, condition, "
    "sold comps, shipping, and category before buying."
)

with st.expander("🚨 Scan eBay for hidden opportunities", expanded=True):
    e1, e2, e3 = st.columns([3, 1, 1])
    with e1:
        ebay_query = st.text_input("Search terms", placeholder="e.g. sterling silver watch")
    with e2:
        ebay_limit = st.number_input("Listings", min_value=5, max_value=50, value=25, step=5)
    with e3:
        ebay_min_score = st.number_input("Minimum score", min_value=0.0, max_value=100.0, value=25.0, step=5.0)

    if st.button("Scan eBay", type="primary", use_container_width=True):
        try:
            with st.spinner("Searching eBay and ranking opportunities…"):
                scan = scan_ebay(ebay_query, limit=int(ebay_limit), min_score=float(ebay_min_score))
            st.session_state["ebay_scan"] = scan
        except EbayAuthError:
            st.error("eBay is not configured yet. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to Streamlit secrets.")
        except Exception as exc:
            st.error(f"eBay scan failed: {exc}")

if "ebay_scan" in st.session_state:
    scan = st.session_state["ebay_scan"]
    st.markdown(f"### {scan.source} results for `{scan.query}`")
    st.caption(f"Fetched {scan.fetched} active listings. Asking prices are not sold prices.")
    if not scan.opportunities:
        st.info("No listings met the selected opportunity threshold.")
    for candidate in scan.opportunities:
        label = f"{candidate.tier} · {candidate.score:.0f}/100"
        with st.expander(f"{label} — {candidate.listing.get('title', 'Untitled listing')}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Asking", f"${candidate.listing.get('price', 0):,.2f}" if candidate.listing.get('price') is not None else "—")
            c2.metric("Radar", f"{candidate.score:.0f}/100")
            c3.metric("Signals", str(len(candidate.signals)))
            if candidate.listing.get("url"):
                st.link_button("Open listing", candidate.listing["url"])
            if candidate.signals:
                for signal in candidate.signals:
                    st.write(f"**{signal['severity'].upper()} · +{signal['score']:.0f}** — {signal['message']}")
            else:
                st.write("No strong anomaly signals detected.")

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
        st.session_state["radar_last"] = analyze_listing(listing)

if "radar_last" in st.session_state:
    result = st.session_state["radar_last"]
    score = result.opportunity_score
    if score >= 95:
        st.success(f"🏆 HOLY GRAIL — {score:.0f}/100")
    elif score >= 85:
        st.success(f"🔥 EXTREME OPPORTUNITY — {score:.0f}/100")
    elif score >= 70:
        st.success(f"🟢 STRONG BUY LEAD — {score:.0f}/100")
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
                "Tier": "HOLY GRAIL" if result.opportunity_score >= 95 else "EXTREME" if result.opportunity_score >= 85 else "STRONG" if result.opportunity_score >= 70 else "INVESTIGATE" if result.opportunity_score >= 50 else "WATCH",
                "Title": listing.get("title", ""),
                "Price": listing.get("price", ""),
                "Estimated Value": listing.get("estimated_value", ""),
                "Review": "YES" if result.review_required else "—",
                "Signals": " | ".join(s.message for s in result.signals),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"Could not scan this CSV: {exc}")
