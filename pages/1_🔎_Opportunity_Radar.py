"""CRTC Holy Grail Finder — last-chance opportunity-intelligence workflow."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from comps_adapters import EbayAuthError
from opportunity_radar import analyze_listing, rank_listings
from opportunity_sources import scan_ebay
from source_registry import default_source_registry
from source_search import public_search_url

st.set_page_config(page_title="CRTC — Holy Grail Finder", page_icon="🏆", layout="wide")

st.markdown("""
<div style="padding:10px 0 4px 0">
  <div style="font-size:2.25rem;font-weight:800;letter-spacing:-.03em">🏆 Holy Grail Finder</div>
  <div style="font-size:1.02rem;color:#8b96a5;margin-top:4px">
    Find overlooked value before the auction closes — with a hard acquisition ceiling.
  </div>
</div>
""", unsafe_allow_html=True)

h1, h2, h3, h4 = st.columns(4)
with h1: st.metric("TIME", "≤ 24 hours", "primary hunt")
with h2: st.metric("BUY", "$100", "primary ceiling")
with h3: st.metric("EXPAND", "$150", "absolute ceiling")
with h4: st.metric("SIGNAL", "Information failure", "missing data wins")

st.info("**CRTC hunts for information failures, not ordinary bargains:** missing weight, bad photos, misidentification, wrong category, typos, hidden brands/models, incomplete descriptions, unknown/untested condition, and other reasons value may be overlooked. The $100 hunt expands to $125, then $150 only when qualifying results are scarce. Nothing above $150 is a Holy Grail buy recommendation.")

registry = default_source_registry()
all_sources = registry.all()
enabled_sources = registry.enabled()

with st.expander("🌎 Source coverage", expanded=False):
    st.caption("CRTC keeps a broad source map. Automated scanning is used only where a legitimate API/feed/export/public catalog route exists; public research links are provided for sources without an approved adapter. No anti-bot bypassing.")
    cols = st.columns(4)
    for i, source in enumerate(all_sources):
        with cols[i % 4]:
            status = "🟢 Automated" if source in enabled_sources else "⚪ Research route"
            st.write(f"**{source.name}**")
            st.caption(status)

st.markdown("## 🚨 Last-chance hunt")
st.caption("Primary filter: auctions/listings with 24 hours or less remaining. The scanner is intentionally broad, then ranks information-failure opportunities. Source adapters determine which live listings can be fetched automatically.")

with st.container(border=True):
    e1, e2, e3, e4 = st.columns([3, 1, 1, 1])
    with e1:
        ebay_query = st.text_input("What are you hunting?", value="gold jewelry", placeholder="e.g. gold jewelry, vintage tools, cameras, guitars")
    with e2:
        ebay_limit = st.number_input("Listings", min_value=5, max_value=50, value=50, step=5)
    with e3:
        price_ceiling = st.selectbox("Buy ceiling", [100, 125, 150], index=0, format_func=lambda x: f"${x} max")
    with e4:
        ebay_min_score = st.number_input("Minimum Radar", min_value=0.0, max_value=100.0, value=25.0, step=5.0)

    st.caption("Automatic fallback: $100 → $125 → $150 when too few qualifying opportunities are found. The 24-hour window remains in force until no qualifying source data is available; then broaden the time window manually rather than lowering the quality standard.")

    if st.button("🚨 HUNT LAST 24 HOURS", type="primary", use_container_width=True):
        if not ebay_query.strip():
            st.warning("Enter something to hunt for first.")
        else:
            try:
                with st.spinner("Searching eBay → normalizing → detecting information failures → ranking under the buy ceiling…"):
                    scan = scan_ebay(ebay_query, limit=int(ebay_limit), min_score=float(ebay_min_score))
                st.session_state["ebay_scan"] = scan
                st.session_state["holy_grail_ceiling"] = int(price_ceiling)
            except EbayAuthError:
                st.error("eBay is not configured in this deployment yet. CRTC needs EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in Streamlit Secrets for automatic API searching.")
            except Exception as exc:
                st.error(f"eBay scan failed: {exc}")

# ---------------------------------------------------------------------------
# IMAGE SEARCH
# ---------------------------------------------------------------------------
st.markdown("## 📷 Scan an item")
st.caption("Use eBay's documented image-search route for visually similar active listings when the API is configured.")
with st.container(border=True):
    photo = st.file_uploader("Item photo", type=["jpg", "jpeg", "png", "webp"], key="holy_grail_photo")
    image_limit = st.slider("Similar listings", 5, 50, 20, 5)
    if st.button("📷 SEARCH THIS ITEM", type="primary", use_container_width=True):
        if photo is None:
            st.warning("Upload an item photo first.")
        else:
            try:
                from ebay_image_scan import search_ebay_by_image
                with st.spinner("Sending image to eBay → finding similar listings → scoring opportunities…"):
                    comps = search_ebay_by_image(photo.getvalue(), photo.type or "image/jpeg", int(image_limit))
                records = [{"title": c.title, "price": c.price, "source": c.source, "url": c.url, "condition": c.condition} for c in comps]
                st.session_state["ebay_image_results"] = records
            except EbayAuthError:
                st.error("eBay API credentials are not configured yet. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to Streamlit Secrets.")
            except Exception as exc:
                st.error(f"Image search failed: {exc}")

if st.session_state.get("ebay_image_results"):
    st.markdown("### Similar eBay listings")
    st.dataframe(pd.DataFrame(st.session_state["ebay_image_results"]), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# RESULTS
# ---------------------------------------------------------------------------
if "ebay_scan" in st.session_state:
    scan = st.session_state["ebay_scan"]
    ceiling = int(st.session_state.get("holy_grail_ceiling", 100))
    st.markdown(f"## 🎯 {scan.source} hunt: `{scan.query}`")
    st.caption(f"{scan.fetched} active listings examined · asking prices only · sold prices are never represented as active evidence · buy ceiling ${ceiling}")
    opportunities = []
    for candidate in scan.opportunities:
        price = candidate.listing.get("price")
        if price is not None and float(price) <= ceiling:
            opportunities.append(candidate)
    if not opportunities:
        st.warning(f"NO QUALIFYING HOLY GRAILS at ${ceiling}. Use the automatic fallback: $125, then $150. If still empty, broaden the hunt time window without lowering the information-failure standard.")
    else:
        for candidate in opportunities:
            score = candidate.score
            if score >= 95: badge = "🏆 HOLY GRAIL"
            elif score >= 85: badge = "🔥 EXTREME OPPORTUNITY"
            elif score >= 70: badge = "🟢 STRONG BUY LEAD"
            elif score >= 50: badge = "🟡 INVESTIGATE"
            else: badge = "🔎 WATCH"
            title = candidate.listing.get("title", "Untitled listing")
            with st.container(border=True):
                st.markdown(f"### {badge} · {score:.0f}/100")
                st.markdown(f"**{title}**")
                c1, c2, c3, c4 = st.columns(4)
                price = candidate.listing.get("price")
                c1.metric("Asking", f"${price:,.2f}" if price is not None else "—")
                c2.metric("Radar", f"{score:.0f}/100")
                c3.metric("Signals", str(len(candidate.signals)))
                c4.metric("Buy", "QUALIFIES" if price is not None and float(price) <= ceiling else "OVER CEILING")
                if candidate.listing.get("url"):
                    st.link_button("Open listing", candidate.listing["url"])
                if candidate.signals:
                    st.markdown("**Why CRTC flagged it**")
                    for signal in candidate.signals:
                        st.write(f"**{signal['severity'].upper()} · +{signal['score']:.0f}** — {signal['message']}")

# ---------------------------------------------------------------------------
# PUBLIC AUCTION RESEARCH HUB
# ---------------------------------------------------------------------------
st.markdown("## 🌎 Research more auction sources")
st.caption("CTBids, ShopGoodwill, HiBid, eBay and other sources remain in the hunting map. Where no approved automated adapter exists, these buttons open the source's own public research route; CRTC does not bypass logins, CAPTCHAs, or access controls.")

research_query = st.text_input("Research term", value=ebay_query, placeholder="e.g. 14k gold ring missing weight")
source_keys = [
    ("ctbids", "CTBids / Estate Auctions"), ("shopgoodwill", "ShopGoodwill"),
    ("ebay", "eBay"), ("hibid", "HiBid"), ("proxibid", "Proxibid"),
    ("liveauctioneers", "LiveAuctioneers"), ("invaluable", "Invaluable"),
    ("auctionzip", "AuctionZip"), ("ebth", "EBTH"), ("maxsold", "MaxSold"),
    ("gsa", "GSA Auctions"), ("govdeals", "GovDeals"), ("publicsurplus", "Public Surplus"),
    ("govplanet", "GovPlanet"), ("propertyroom", "PropertyRoom"),
    ("municibid", "Municibid"), ("purplewave", "Purple Wave"),
]
cols = st.columns(4)
for i, (key, label) in enumerate(source_keys):
    with cols[i % 4]:
        url = public_search_url(key, research_query)
        if url:
            st.link_button(label, url, use_container_width=True)

with st.expander("🧪 Analyze a listing you found anywhere", expanded=False):
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
        listing = {"title": title, "description": description, "category": category, "price": price, "estimated_value": estimated_value or None, "expected_keywords": [x.strip() for x in expected.split(",") if x.strip()]}
        st.session_state["radar_last"] = analyze_listing(listing)

if "radar_last" in st.session_state:
    result = st.session_state["radar_last"]
    score = result.opportunity_score
    if score >= 95: st.success(f"🏆 HOLY GRAIL — {score:.0f}/100")
    elif score >= 85: st.success(f"🔥 EXTREME OPPORTUNITY — {score:.0f}/100")
    elif score >= 70: st.success(f"🟢 STRONG BUY LEAD — {score:.0f}/100")
    elif score >= 50: st.warning(f"🟡 INVESTIGATE — {score:.0f}/100")
    elif score >= 25: st.info(f"🔎 REVIEW — {score:.0f}/100")
    else: st.caption(f"Radar score: {score:.0f}/100")
    if result.signals:
        st.markdown("#### Why it was flagged")
        for signal in result.signals:
            st.write(f"**{signal.severity.upper()} · +{signal.score:.0f}** — {signal.message}")
    else:
        st.write("No strong anomaly signals detected.")

st.markdown("---")
st.markdown("## 📥 Batch scan")
st.caption("Upload a CSV with columns such as title, description, category, price, and estimated_value.")
uploaded = st.file_uploader("Listing CSV", type=["csv"])
if uploaded:
    try:
        source = pd.read_csv(uploaded)
        records = source.to_dict("records")
        ranked = rank_listings(records)
        rows = []
        for listing, result in ranked:
            rows.append({"Opportunity Score": result.opportunity_score, "Tier": "HOLY GRAIL" if result.opportunity_score >= 95 else "EXTREME" if result.opportunity_score >= 85 else "STRONG" if result.opportunity_score >= 70 else "INVESTIGATE" if result.opportunity_score >= 50 else "WATCH", "Title": listing.get("title", ""), "Price": listing.get("price", ""), "Estimated Value": listing.get("estimated_value", ""), "Review": "YES" if result.review_required else "—", "Signals": " | ".join(s.message for s in result.signals)})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"Could not scan this CSV: {exc}")

st.caption("CRTC · Cooper River Trading Co. · FIND → IDENTIFY → VALUE → DECIDE → BUY → TRACK → LIST → SELL → MEASURE")
