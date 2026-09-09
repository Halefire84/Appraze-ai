"""CRTC Holy Grail Finder — opportunity intelligence UI.

Radar finds leads; the canonical opportunity contract makes the purchase
recommendation only when market-value evidence is available.
"""
import json

import pandas as pd
import streamlit as st

from auction_radar import rank_auction_catalog
from opportunity_sources import enrich_ebay_opportunities, scan_ebay, source_scan_status
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
            with st.spinner("Scanning eBay and building market evidence for the strongest leads…"):
                scan = scan_ebay(query, limit=int(limit), min_score=float(min_score))
                evidence = enrich_ebay_opportunities(scan.opportunities, limit=10, comps_limit=12)
                st.session_state["crtc_holy_grail_scan"] = scan
                st.session_state["crtc_holy_grail_evidence"] = evidence
                st.session_state.pop("crtc_auction_scan", None)
        except Exception as exc:
            st.error(f"The market scan failed: {exc}")

with st.container(border=True):
    st.subheader("📦 Auction Catalog Import")
    st.caption("Import a permitted CSV/JSON catalog or export. CRTC does not scrape or bypass auction-site controls.")
    a1, a2 = st.columns([1, 2])
    with a1:
        auction_source = st.selectbox(
            "Auction source",
            options=["ctbids", "shopgoodwill", "hibid"],
            format_func=lambda key: {"ctbids": "CTBids / Estate Auctions", "shopgoodwill": "ShopGoodwill", "hibid": "HiBid"}[key],
        )
        auction_min_score = st.number_input("Import Min Radar", min_value=0, max_value=95, value=25, step=5, key="auction_min_score")
    with a2:
        catalog_file = st.file_uploader("Catalog file", type=["csv", "json"], key="crtc_auction_catalog")
    import_clicked = st.button("🔥 SCAN AUCTION CATALOG", type="secondary", use_container_width=True)

if import_clicked:
    if catalog_file is None:
        st.error("Choose a CSV or JSON catalog/export first.")
    else:
        try:
            if catalog_file.name.lower().endswith(".csv"):
                records = pd.read_csv(catalog_file).where(pd.notna(pd.read_csv(catalog_file)), None).to_dict(orient="records")
            else:
                payload = json.load(catalog_file)
                records = payload if isinstance(payload, list) else payload.get("records", [])
            if not isinstance(records, list):
                raise ValueError("JSON catalog must be a list of records or an object containing a 'records' list.")
            with st.spinner(f"Normalizing and scoring {len(records)} auction records…"):
                ranked = rank_auction_catalog(auction_source, records, min_score=float(auction_min_score))
            st.session_state["crtc_auction_scan"] = {
                "source": auction_source,
                "fetched": len(records),
                "opportunities": ranked,
            }
            st.session_state.pop("crtc_holy_grail_scan", None)
            st.session_state.pop("crtc_holy_grail_evidence", None)
        except Exception as exc:
            st.error(f"Auction catalog import failed: {exc}")

auction_scan = st.session_state.get("crtc_auction_scan")

with st.expander("🌎 CRTC source coverage", expanded=False):
    registry = default_source_registry()
    rows = []
    for source in registry.all():
        if source.key == "ebay":
            state, method = "READY", "Official API"
        elif source.key in {"ctbids", "shopgoodwill", "hibid"}:
            state, method = "IMPORT READY", "Catalog / permitted export / user file"
        else:
            state, method = "PLANNED", ", ".join(source.acquisition_methods)
        rows.append({"Source": source.name, "Status": state, "Acquisition": method})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Unsupported sources remain planned until CRTC has a legitimate acquisition path. No anti-bot bypassing.")

if auction_scan is not None:
    opportunities = auction_scan["opportunities"]
    st.success(f"Imported {auction_scan['fetched']} {auction_scan['source']} records · {len(opportunities)} passed the {auction_min_score:g}+ Radar threshold.")
    if not opportunities:
        st.info("No qualifying auction opportunities yet. Lower the minimum score or import a broader catalog.")
    else:
        rows = [{
            "Radar": round(item.score),
            "Tier": item.tier,
            "Asking": item.listing.get("price"),
            "Title": item.listing.get("title", ""),
            "Lot ID": item.listing.get("source_listing_id", ""),
        } for item in opportunities]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     column_config={"Asking": st.column_config.NumberColumn(format="$%.2f")})
        st.markdown("### 🎯 Top auction opportunities")
        for rank, item in enumerate(opportunities[:10], start=1):
            listing = item.listing
            with st.container(border=True):
                left, right = st.columns([4, 1])
                with left:
                    st.markdown(f"### #{rank} · {item.tier}")
                    st.markdown(f"**{listing.get('title') or 'Untitled'}**")
                    asking = listing.get("price")
                    asking_text = f"${float(asking):,.2f}" if asking is not None else "Not provided"
                    st.write(f"**Asking/current bid:** {asking_text} · **Radar:** {item.score:.0f}/100")
                    st.info("**CRTC decision: REVIEW** — catalog Radar identifies a lead; market-value evidence is still required before buying.")
                    if item.signals:
                        st.markdown("**Why CRTC surfaced it:**")
                        for signal in item.signals:
                            st.write(f"• {signal['message']}")
                with right:
                    st.metric("Radar", f"{item.score:.0f}/100")
                    if listing.get("source_listing_id"):
                        st.caption(f"Lot: {listing['source_listing_id']}")
                    if listing.get("source_url") or listing.get("url"):
                        st.link_button("Open listing", listing.get("source_url") or listing.get("url"), use_container_width=True)
                    st.caption("Verify condition, fees, pickup/shipping, authenticity, and sold comps before bidding.")

scan = st.session_state.get("crtc_holy_grail_scan")
evidence = st.session_state.get("crtc_holy_grail_evidence", {})

if scan is not None:
    opportunities = scan.opportunities
    st.success(f"Scanned {scan.fetched} active eBay listings · {len(opportunities)} passed the {min_score:g}+ Radar threshold.")
    if evidence:
        sold_total = sum(v.get("sold_count", 0) for v in evidence.values())
        active_total = sum(v.get("active_count", 0) for v in evidence.values())
        if sold_total:
            st.caption(f"Market evidence: **{sold_total} sold comps** across the top leads, plus {active_total} active comps.")
        else:
            st.caption(f"Market evidence: **{active_total} active asking-price comps**. Sold-price evidence is not available for this account, so confidence remains low.")

    if not opportunities:
        st.info("No qualifying opportunities yet. Lower the minimum score, broaden the search, or try a different term.")
    else:
        rows = []
        for index, item in enumerate(opportunities):
            result = evidence.get(index, {}).get("result")
            if result is None:
                from holy_grail_pipeline import opportunity_result
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
            result = evidence.get(rank - 1, {}).get("result")
            meta = evidence.get(rank - 1, {})
            if result is None:
                from holy_grail_pipeline import opportunity_result
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
                        st.caption(f"Evidence: {meta.get('sold_count', 0)} sold · {meta.get('active_count', 0)} active")
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
    if auction_scan is None:
        st.info("Start with a brand, item, or category, or import an auction catalog. CRTC will hunt for terminology errors, category mistakes, weak descriptions, and value gaps.")

st.markdown("---")
st.caption("CRTC principle: Radar finds the lead. Market evidence and economics make the purchase decision.")
