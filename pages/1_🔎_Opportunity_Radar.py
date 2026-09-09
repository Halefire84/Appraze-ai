"""CRTC Opportunity Radar command center."""
import pandas as pd
import streamlit as st

from comps_adapters import EbayAuthError
from opportunity_radar import analyze_listing, rank_listings
from opportunity_sources import scan_ebay
from opportunity_store import save_opportunity, remove_opportunity
from source_registry import default_source_registry
from source_search import public_search_url

st.set_page_config(page_title="CRTC — Opportunity Radar", page_icon="🔎", layout="wide")
st.title("🔎 CRTC Opportunity Radar")
st.caption("Find overlooked value, rank the leads, verify the economics, and save the ones worth hunting.")

registry = default_source_registry()
all_sources = registry.all()
enabled_sources = registry.enabled()

# ---------------------------------------------------------------------------
# COMMAND CENTER
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown("### 🎯 Hunt Command Center")
    q1, q2, q3, q4 = st.columns([3, 1, 1, 1])
    with q1:
        hunt_query = st.text_input("Hunt", value=st.session_state.get("hunt_query", "gold jewelry"), placeholder="gold jewelry, vintage tools, cameras…")
    with q2:
        hunt_limit = st.number_input("Listings", 5, 50, 50, 5)
    with q3:
        hunt_ceiling = st.selectbox("Bid ceiling", [100, 125, 150], index=0, format_func=lambda x: f"${x}")
    with q4:
        min_radar = st.number_input("Min Radar", 0.0, 100.0, 25.0, 5.0)
    if st.button("🚨 RUN HUNT", type="primary", use_container_width=True):
        if not hunt_query.strip():
            st.warning("Enter a hunt term first.")
        else:
            try:
                with st.spinner("Searching → normalizing → ranking opportunity signals…"):
                    scan = scan_ebay(hunt_query, limit=int(hunt_limit), min_score=float(min_radar))
                st.session_state["radar_scan"] = scan
                st.session_state["hunt_query"] = hunt_query
                st.session_state["hunt_ceiling"] = int(hunt_ceiling)
            except EbayAuthError:
                st.error("eBay is not configured. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to Streamlit Secrets.")
            except Exception as exc:
                st.error(f"Hunt failed: {exc}")

# ---------------------------------------------------------------------------
# SOURCE COVERAGE
# ---------------------------------------------------------------------------
st.markdown("## 🌎 Source coverage")
sc1, sc2 = st.columns([1, 3])
with sc1:
    st.metric("Sources mapped", len(all_sources))
    st.metric("Automated now", len(enabled_sources))
with sc2:
    st.caption("CRTC maps legitimate marketplaces, estate auctions, government surplus and specialty sources. Automated acquisition is limited to approved APIs/feeds/public catalogs/user exports; no CAPTCHA or anti-bot bypassing.")
    source_status = pd.DataFrame([{"Source": s.name, "Mode": "AUTOMATED" if s in enabled_sources else "RESEARCH ROUTE", "Type": s.source_type} for s in all_sources])
    st.dataframe(source_status, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# LIVE RESULTS + FILTERS
# ---------------------------------------------------------------------------
scan = st.session_state.get("radar_scan")
if scan:
    ceiling = int(st.session_state.get("hunt_ceiling", 100))
    st.markdown(f"## 🧭 Ranked opportunities · {scan.source}")
    st.caption(f"{scan.fetched} listings examined · Radar minimum {min_radar:.0f} · hunt ceiling ${ceiling}")
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        tier_filter = st.multiselect("Tiers", ["HOLY GRAIL", "EXTREME OPPORTUNITY", "STRONG BUY LEAD", "INVESTIGATE", "WATCH"], default=[])
    with fc2:
        signal_filter = st.selectbox("Signal focus", ["All signals", "Typos", "Category mismatch", "Description contradiction", "Value gap", "Hidden brand/model"])
    with fc3:
        sort_mode = st.selectbox("Sort", ["Radar score", "Lowest price", "Highest value gap"])

    candidates = [c for c in scan.opportunities if c.listing.get("price") is not None and float(c.listing["price"]) <= ceiling]
    if tier_filter:
        candidates = [c for c in candidates if c.tier in tier_filter]
    if signal_filter != "All signals":
        terms = {"Typos": "typo", "Category mismatch": "category", "Description contradiction": "contrad", "Value gap": "value", "Hidden brand/model": "brand"}
        candidates = [c for c in candidates if any(terms[signal_filter] in str(s.get("message", "")).lower() for s in c.signals)]
    if sort_mode == "Lowest price":
        candidates.sort(key=lambda c: float(c.listing.get("price", 0)))
    elif sort_mode == "Highest value gap":
        candidates.sort(key=lambda c: float(c.listing.get("estimated_value", 0) or 0) - float(c.listing.get("price", 0) or 0), reverse=True)
    else:
        candidates.sort(key=lambda c: c.score, reverse=True)

    st.caption(f"Showing {len(candidates)} qualifying leads")
    rows = []
    for c in candidates:
        rows.append({"Radar": round(c.score), "Tier": c.tier, "Price": c.listing.get("price"), "Title": c.listing.get("title", ""), "Source": c.listing.get("source", ""), "Lot": c.listing.get("source_listing_id", "")})
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, column_config={"Price": st.column_config.NumberColumn(format="$%.2f")})
    else:
        st.warning("No leads match the current filters.")

    st.markdown("### 🔥 Top leads")
    saved = st.session_state.setdefault("saved_opportunities", [])
    for rank, candidate in enumerate(candidates[:15], 1):
        listing = candidate.listing
        with st.container(border=True):
            title = listing.get("title") or "Untitled listing"
            st.markdown(f"### #{rank} · {candidate.tier} · {candidate.score:.0f}/100")
            st.write(f"**{title}**")
            a, b, c, d = st.columns(4)
            price = listing.get("price")
            a.metric("Current price", f"${float(price):,.2f}" if price is not None else "—")
            b.metric("Radar", f"{candidate.score:.0f}/100")
            c.metric("Signals", len(candidate.signals))
            d.metric("Ceiling", f"${ceiling:,.0f}")
            if candidate.signals:
                st.caption(" · ".join(str(s["message"]) for s in candidate.signals[:3]))
            key = (str(listing.get("source", "")), str(listing.get("source_listing_id", "")), str(listing.get("url", "")))
            is_saved = any((str(x.get("source", "")), str(x.get("source_listing_id", "")), str(x.get("url", ""))) == key for x in saved)
            bc1, bc2 = st.columns(2)
            with bc1:
                if not is_saved and st.button("⭐ SAVE OPPORTUNITY", key=f"save_{rank}_{key}", use_container_width=True):
                    saved = save_opportunity(saved, {"source": listing.get("source", ""), "source_listing_id": listing.get("source_listing_id", ""), "url": listing.get("url", ""), "title": title, "price": price, "radar_score": candidate.score, "tier": candidate.tier})
                    st.session_state["saved_opportunities"] = saved
                    st.rerun()
                elif is_saved:
                    st.success("Saved")
            with bc2:
                if listing.get("url"):
                    st.link_button("OPEN LISTING", listing["url"], use_container_width=True)

# ---------------------------------------------------------------------------
# SAVED HUNT LIST
# ---------------------------------------------------------------------------
st.markdown("## ⭐ Saved opportunities")
saved = st.session_state.setdefault("saved_opportunities", [])
if saved:
    for i, item in enumerate(saved):
        with st.container(border=True):
            c1, c2, c3 = st.columns([4, 1, 1])
            with c1:
                st.write(f"**{item.get('title', 'Untitled')}**")
                st.caption(f"{item.get('source', '')} · {item.get('source_listing_id', '')} · Radar {float(item.get('radar_score', 0)):.0f}")
            with c2:
                if item.get("url"): st.link_button("Open", item["url"], use_container_width=True)
            with c3:
                if st.button("Remove", key=f"remove_saved_{i}", use_container_width=True):
                    st.session_state["saved_opportunities"] = remove_opportunity(saved, i)
                    st.rerun()
else:
    st.info("Save a lead and it will stay available during this session for quick follow-up.")

# ---------------------------------------------------------------------------
# RESEARCH HUB / MANUAL ANALYZER
# ---------------------------------------------------------------------------
st.markdown("## 🌎 Research more sources")
research_query = st.text_input("Research term", value=hunt_query, key="research_query")
source_keys = [("ctbids", "CTBids / Estate Auctions"), ("shopgoodwill", "ShopGoodwill"), ("hibid", "HiBid"), ("proxibid", "Proxibid"), ("liveauctioneers", "LiveAuctioneers"), ("invaluable", "Invaluable"), ("auctionzip", "AuctionZip"), ("ebth", "EBTH"), ("maxsold", "MaxSold"), ("gsa", "GSA Auctions"), ("govdeals", "GovDeals"), ("publicsurplus", "Public Surplus"), ("govplanet", "GovPlanet"), ("propertyroom", "PropertyRoom"), ("municibid", "Municibid"), ("purplewave", "Purple Wave"), ("ebay", "eBay")]
cols = st.columns(4)
for i, (key, label) in enumerate(source_keys):
    url = public_search_url(key, research_query)
    if url:
        with cols[i % 4]: st.link_button(label, url, use_container_width=True)

with st.expander("🧪 Analyze a listing you found anywhere"):
    c1, c2 = st.columns([2, 1])
    with c1:
        title = st.text_input("Title", placeholder="vinta ge 14k gold chain")
        description = st.text_area("Description", height=100)
    with c2:
        category = st.text_input("Category", placeholder="Jewelry")
        price = st.number_input("Price", min_value=0.0, value=0.0, step=5.0)
        estimated_value = st.number_input("Estimated value", min_value=0.0, value=0.0, step=10.0)
        expected = st.text_input("Expected keywords", placeholder="gold, chain, jewelry")
    if st.button("Analyze listing", type="primary", use_container_width=True):
        listing = {"title": title, "description": description, "category": category, "price": price, "estimated_value": estimated_value or None, "expected_keywords": [x.strip() for x in expected.split(",") if x.strip()]}
        st.session_state["radar_last"] = analyze_listing(listing)

if "radar_last" in st.session_state:
    result = st.session_state["radar_last"]
    st.metric("Opportunity Score", f"{result.opportunity_score:.0f}/100")
    for signal in result.signals:
        st.write(f"**{signal.severity.upper()} · +{signal.score:.0f}** — {signal.message}")

st.caption("CRTC · FIND → IDENTIFY → VALUE → DECIDE → BUY → TRACK → LIST → SELL → MEASURE")
