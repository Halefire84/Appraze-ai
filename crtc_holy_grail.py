"""CRTC Holy Grail Finder — opportunity intelligence UI.

Radar finds leads; the canonical opportunity contract makes the purchase
recommendation only when market-value evidence is available.
"""
import pandas as pd
import streamlit as st

from holy_grail_pipeline import opportunity_result
from opportunity_sources import scan_ebay, source_scan_status
from source_registry import default_source_registry

st.set_page_config(page_title="CRTC — Holy Grail Finder", page_icon="🔥", layout="wide")
st.title("🔥 CRTC Holy Grail Finder")
st.caption("Find the listings other buyers missed — then verify the opportunity before you buy.")
st.markdown("**FIND → IDENTIFY → VALUE → DECIDE** · Radar finds the lead; evidence makes the decision.")

with st.container(border=True):
    st.subheader("🔎 Scan the Market")
    c1, c2, c3 = st.columns([2.5, 1, 1])
    with c1:
        query = st.text_input("What are you hunting?", placeholder="e.g. Rolex, sterling silver, vintage camera, brass lamp")
    with c2:
        limit = st.number_input("Listings", min_value=5, max_value=50, value=25, step=5)
    with c3:
        min_score = st.number_input("Min Radar", min_value=0, max_value=95, value=25, step=5)
    scan_clicked = st.button("🔥 FIND HIDDEN DEALS", type="primary", use_container_width=True)

if scan_clicked:
    if not query.strip():
        st.error("Enter an item, brand, category, or keyword to hunt for.")
    elif source_scan_status()["ebay"]["status"] != "ready":
        st.warning("eBay is not configured yet. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to deployment secrets.")
    else:
        try:
            with st.spinner("Scanning active eBay listings and looking for overlooked opportunities…"):
                st.session_state["crtc_holy_grail_scan"] = scan_ebay(query, limit=int(limit), min_score=float(min_score))
        except Exception as exc:
            st.error(f"The market scan failed: {exc}")

scan = st.session_state.get("crtc_holy_grail_scan")

with st.expander("🌎 CRTC source coverage", expanded=False):
    registry = default_source_registry()
    rows = []
    for source in registry.all():
        if source.key == "ebay":
            state, method = "READY", "Official API"
        else:
            state, method = "PLANNED", ", ".join(source.acquisition_methods)
        rows.append({"Source": source.name, "Status": state, "Acquisition": method})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Unsupported sources remain planned until CRTC has a legitimate acquisition path. No anti-bot bypassing.")

if scan is not None:
    opportunities = scan.opportunities
    st.success(f"Scanned {scan.fetched} active eBay listings · {len(opportunities)} passed the {min_score:g}+ Radar threshold.")
    st.caption("Evidence type: **ACTIVE ASKING PRICE** — not sold-price evidence.")

    if not opportunities:
        st.info("No qualifying opportunities yet. Lower the minimum score, broaden the search, or try a different term.")
    else:
        rows = []
        for item in opportunities:
            result = opportunity_result(item)
            rows.append({
                "Radar": round(result["radar_score"]),
                "Decision": result["decision"],
                "Asking": result["asking_price"],
                "Market value": result["market_value"],
                "Max buy": result["max_buy_price"],
                "Confidence": result["market_confidence"],
                "Title": result["title"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     column_config={
                         "Asking": st.column_config.NumberColumn(format="$%.2f"),
                         "Market value": st.column_config.NumberColumn(format="$%.2f"),
                         "Max buy": st.column_config.NumberColumn(format="$%.2f"),
                     })

        st.markdown("### 🎯 Top opportunities")
        for rank, item in enumerate(opportunities[:10], start=1):
            result = opportunity_result(item)
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"### #{rank} · {result['radar_tier']}")
                    st.markdown(f"**{result['title'] or 'Untitled'}**")
                    asking = result["asking_price"]
                    st.write(f"**Asking:** ${asking:,.2f}  ·  **Radar:** {result['radar_score']:.0f}/100")
                    if result["market_value"] is not None:
                        st.write(f"**Market value:** ${result['market_value']:,.2f}  ·  **Max buy:** ${result['max_buy_price']:,.2f}")
                        st.write(f"**Market confidence:** {result['market_confidence']}")
                    else:
                        st.warning("REVIEW — market-value evidence is required before CRTC recommends buying.")
                    st.info(f"**CRTC decision: {result['decision']}** — {result['reason']}")
                    if item.signals:
                        st.markdown("**Why CRTC surfaced it:**")
                        for signal in item.signals:
                            st.write(f"• {signal['message']}")
                with right:
                    st.metric("Decision", result["decision"])
                    st.metric("Radar", f"{result['radar_score']:.0f}/100")
                    if result["max_buy_price"] is not None:
                        st.metric("Max buy", f"${result['max_buy_price']:,.2f}")
                    if result["url"]:
                        st.link_button("Open listing", result["url"], use_container_width=True)
                    st.caption("Verify authenticity, condition, shipping, fees, and sold comps before buying.")
else:
    st.info("Start with a brand, item, or category. CRTC will hunt for terminology errors, category mistakes, weak descriptions, and value gaps.")

st.markdown("---")
st.caption("CRTC principle: Radar finds the lead. Market evidence and economics make the purchase decision.")
