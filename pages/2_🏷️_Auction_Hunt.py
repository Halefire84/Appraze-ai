"""CRTC Auction Hunt — import permitted auction catalogs and score the best leads."""
import json

import pandas as pd
import streamlit as st

from auction_radar import rank_auction_catalog
from auction_valuation import value_auction_opportunities

SOURCES = {
    "CTBids / Estate Auctions": "ctbids",
    "ShopGoodwill": "shopgoodwill",
    "HiBid": "hibid",
}

st.set_page_config(page_title="CRTC — Auction Hunt", page_icon="🏷️", layout="wide")
st.title("🏷️ CRTC Auction Hunt")
st.caption("Import a permitted auction catalog/export, then let the same CRTC Radar find the strongest leads.")
st.markdown("**SOURCE → NORMALIZE → RADAR → VALUE → ALL-IN COST → DECIDE**")

with st.container(border=True):
    source_name = st.selectbox("Auction source", list(SOURCES))
    min_score = st.number_input("Minimum Radar score", min_value=0, max_value=95, value=25, step=5)
    uploaded = st.file_uploader("Upload CSV or JSON catalog/export", type=["csv", "json"])
    scan_clicked = st.button("🔥 SCAN AUCTION CATALOG", type="primary", use_container_width=True)

if scan_clicked:
    if uploaded is None:
        st.error("Upload a permitted CSV or JSON auction catalog/export first.")
    else:
        try:
            if uploaded.name.lower().endswith(".csv"):
                frame = pd.read_csv(uploaded)
                records = frame.where(pd.notna(frame), None).to_dict("records")
            else:
                payload = json.load(uploaded)
                records = payload if isinstance(payload, list) else payload.get("records", [])
            if not isinstance(records, list):
                raise ValueError("Catalog must contain a list of records.")
            opportunities = rank_auction_catalog(SOURCES[source_name], records, min_score=float(min_score))
            evidence = value_auction_opportunities(opportunities, limit=10, comps_limit=12)
            st.session_state["crtc_auction_opportunities"] = opportunities
            st.session_state["crtc_auction_evidence"] = evidence
            st.session_state["crtc_auction_source"] = source_name
            st.success(f"Imported {len(records)} catalog records and found {len(opportunities)} Radar opportunities.")
        except Exception as exc:
            st.error(f"Auction catalog scan failed: {exc}")

opportunities = st.session_state.get("crtc_auction_opportunities", [])
evidence = st.session_state.get("crtc_auction_evidence", {})
source_name = st.session_state.get("crtc_auction_source", source_name)

if opportunities:
    rows = []
    for index, candidate in enumerate(opportunities):
        meta = evidence.get(index, {})
        result = meta.get("result")
        cost = meta.get("acquisition_cost") or {}
        rows.append({
            "Radar": round(candidate.score),
            "Decision": result["decision"] if result else "REVIEW",
            "Bid": result["asking_price"] if result else candidate.listing.get("price"),
            "All-in cost": cost.get("all_in_cost"),
            "Market value": result["market_value"] if result else None,
            "Max bid": meta.get("max_bid"),
            "Confidence": result["market_confidence"] if result else "UNKNOWN",
            "Source": candidate.listing.get("source", source_name),
            "Lot ID": candidate.listing.get("source_listing_id", ""),
            "Title": candidate.listing.get("title", ""),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                 column_config={
                     "Bid": st.column_config.NumberColumn(format="$%.2f"),
                     "All-in cost": st.column_config.NumberColumn(format="$%.2f"),
                     "Market value": st.column_config.NumberColumn(format="$%.2f"),
                     "Max bid": st.column_config.NumberColumn(format="$%.2f"),
                 })

    st.markdown("### 🎯 Best auction opportunities")
    for rank, candidate in enumerate(opportunities[:10], start=1):
        meta = evidence.get(rank - 1, {})
        result = meta.get("result")
        cost = meta.get("acquisition_cost") or {}
        with st.container(border=True):
            st.markdown(f"### #{rank} · {candidate.tier}")
            st.write(f"**{candidate.listing.get('title') or 'Untitled'}**")
            asking = candidate.listing.get("price")
            if asking is not None:
                st.write(f"**Current bid:** ${float(asking):,.2f} · **Radar:** {candidate.score:.0f}/100 · **Lot:** {candidate.listing.get('source_listing_id', '')}")
            else:
                st.write(f"**Radar:** {candidate.score:.0f}/100 · **Lot:** {candidate.listing.get('source_listing_id', '')}")

            if cost:
                premium = cost.get("buyer_premium_pct")
                shipping = cost.get("shipping")
                premium_text = f"{premium:.1f}%" if premium is not None else "UNKNOWN"
                shipping_text = f"${shipping:,.2f}" if shipping is not None else "UNKNOWN"
                st.write(f"**All-in at current bid:** ${cost['all_in_cost']:,.2f} · **Buyer premium:** {premium_text} · **Shipping:** {shipping_text}")

            if result and result["market_value"] is not None:
                max_bid = meta.get("max_bid")
                max_bid_text = f"${max_bid:,.2f}" if max_bid is not None else "UNKNOWN"
                st.write(f"**Market value:** ${result['market_value']:,.2f} · **70% max bid:** {max_bid_text}")
                st.write(f"**Confidence:** {result['market_confidence']} · **Evidence:** {meta.get('sold_count', 0)} sold / {meta.get('active_count', 0)} active")
                if result["decision"] == "BUY":
                    st.success(f"CRTC: **BUY** — {result['reason']}")
                elif result["decision"] == "REVIEW":
                    st.warning(f"CRTC: **REVIEW** — {result['reason']}")
                else:
                    st.info(f"CRTC: **{result['decision']}** — {result['reason']}")
            else:
                st.warning("REVIEW — no usable market-value evidence yet.")
            url = candidate.listing.get("source_url") or candidate.listing.get("url")
            if url:
                st.link_button("Open original auction lot", url)
            for signal in candidate.signals[:5]:
                st.caption(f"• {signal['message']}")
else:
    st.info("Upload a catalog/export to start hunting. CRTC will not scrape or bypass auction-site controls.")
