"""CRTC Holy Grail Finder — opportunity intelligence UI.

The page deliberately uses only legitimate acquisition paths exposed by the
source layer. Active eBay listings are clearly labeled as asking prices;
CRTC never represents them as sold comps.
"""
import pandas as pd
import streamlit as st

from opportunity_sources import scan_ebay, source_scan_status
from source_registry import default_source_registry

st.set_page_config(page_title="CRTC — Holy Grail Finder", page_icon="🔥", layout="wide")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🔥 CRTC Holy Grail Finder")
st.caption("Find the listings other buyers missed — then verify the opportunity before you buy.")

st.markdown(
    "**FIND → IDENTIFY → VALUE → DECIDE**  ·  typo listings · bad categories · weak descriptions · value gaps"
)

# ---------------------------------------------------------------------------
# Scanner controls
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.subheader("🔎 Scan the Market")
    c1, c2, c3 = st.columns([2.5, 1, 1])
    with c1:
        query = st.text_input(
            "What are you hunting?",
            placeholder="e.g. Rolex, sterling silver, vintage camera, brass lamp",
            label_visibility="visible",
        )
    with c2:
        limit = st.number_input("Listings", min_value=5, max_value=50, value=25, step=5)
    with c3:
        min_score = st.number_input("Min score", min_value=0, max_value=95, value=25, step=5)

    scan_clicked = st.button("🔥 FIND HIDDEN DEALS", type="primary", use_container_width=True)

if scan_clicked:
    if not query.strip():
        st.error("Enter an item, brand, category, or keyword to hunt for.")
    else:
        status = source_scan_status()["ebay"]
        if status["status"] != "ready":
            st.warning("eBay is not configured yet. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to the deployment secrets, then scan again.")
        else:
            try:
                with st.spinner("Scanning active eBay listings and looking for overlooked opportunities…"):
                    scan = scan_ebay(query, limit=int(limit), min_score=float(min_score))
                st.session_state["crtc_holy_grail_scan"] = scan
            except Exception as exc:
                st.error(f"The market scan failed: {exc}")

scan = st.session_state.get("crtc_holy_grail_scan")

# ---------------------------------------------------------------------------
# Source coverage
# ---------------------------------------------------------------------------
with st.expander("🌎 CRTC source coverage", expanded=False):
    registry = default_source_registry()
    ready = source_scan_status().get("ebay", {})
    rows = []
    for source in registry.all():
        if source.key == "ebay":
            state = "READY"
            method = "Official API"
        else:
            state = "PLANNED"
            method = ", ".join(source.acquisition_methods)
        rows.append({"Source": source.name, "Status": state, "Acquisition": method})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("CRTC is designed for many legitimate sources. Sources without an approved adapter stay planned rather than using scraping or anti-bot bypasses.")

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if scan is not None:
    opportunities = scan.opportunities
    st.success(f"Scanned {scan.fetched} active eBay listings · {len(opportunities)} passed the {min_score:g}+ Radar threshold.")
    st.caption("Evidence type: **ACTIVE ASKING PRICE**. This is not sold-price evidence.")

    if not opportunities:
        st.info("No qualifying opportunities yet. Lower the minimum score, broaden the search, or try a different term.")
    else:
        tier_counts = {}
        for item in opportunities:
            tier_counts[item.tier] = tier_counts.get(item.tier, 0) + 1
        metric_cols = st.columns(5)
        for col, tier in zip(metric_cols, ["HOLY GRAIL", "EXTREME OPPORTUNITY", "STRONG BUY LEAD", "INVESTIGATE", "WATCH"]):
            with col:
                st.metric(tier, tier_counts.get(tier, 0))

        rows = []
        for item in opportunities:
            listing = item.listing
            rows.append({
                "Score": round(item.score),
                "Tier": item.tier,
                "Asking": listing.get("price"),
                "Title": listing.get("title", "Untitled"),
                "Condition": listing.get("condition", ""),
                "Why it surfaced": "; ".join(signal["message"] for signal in item.signals),
            })
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={"Asking": st.column_config.NumberColumn(format="$%.2f")},
        )

        st.markdown("### 🎯 Top opportunities")
        for rank, item in enumerate(opportunities[:10], start=1):
            listing = item.listing
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"### #{rank} · {item.tier}")
                    st.markdown(f"**{listing.get('title', 'Untitled')}**")
                    price = float(listing.get("price") or 0)
                    st.write(f"**Asking price:** ${price:,.2f}  ·  **CRTC Radar:** {item.score:.0f}/100")
                    if item.signals:
                        st.markdown("**Why CRTC surfaced it:**")
                        for signal in item.signals:
                            st.write(f"• {signal['message']}")
                    else:
                        st.write("• Passed the current Radar threshold; investigate manually.")
                with right:
                    st.metric("Radar", f"{item.score:.0f}/100")
                    if listing.get("url"):
                        st.link_button("Open listing", listing["url"], use_container_width=True)
                    st.caption("Lead only — verify authenticity, condition, shipping, fees, and market evidence before buying.")
else:
    st.info("Start with a brand, item, or category above. CRTC will look for weak terminology, category errors, typos, and other signals that can hide a good deal.")

st.markdown("---")
st.caption("CRTC principle: the Radar finds the lead; evidence and your judgment make the purchase decision.")
