"""CRTC Holy Grail Finder — primary opportunity-intelligence workflow."""

import pandas as pd
import streamlit as st

from comps_adapters import EbayAuthError
from opportunity_radar import analyze_listing, rank_listings
from opportunity_sources import scan_ebay
from source_registry import default_source_registry

st.set_page_config(page_title="CRTC — Holy Grail Finder", page_icon="🏆", layout="wide")

st.markdown("""
<div style="padding:10px 0 4px 0">
  <div style="font-size:2.25rem;font-weight:800;letter-spacing:-.03em">🏆 Holy Grail Finder</div>
  <div style="font-size:1.02rem;color:#8b96a5;margin-top:4px">
    Find the listings other buyers miss — then decide what they are really worth.
  </div>
</div>
""", unsafe_allow_html=True)

h1, h2, h3 = st.columns(3)
with h1: st.metric("FIND", "Hidden deals", "typos + miscategories")
with h2: st.metric("VALUE", "Evidence first", "active ≠ sold")
with h3: st.metric("DECIDE", "0–100 Radar", "ranked opportunity")

st.info("**CRTC does not simply search for expensive items.** It looks for weak titles, spelling errors, category mismatches, value gaps, and other signals that can hide a good buy. A Radar score is a lead — always verify authenticity, condition, sold comps, shipping, and fees.")

registry = default_source_registry()
all_sources = registry.all()
enabled_sources = registry.enabled()

with st.expander("🌎 Source coverage", expanded=False):
    st.caption("CRTC keeps a broad source map, but automation is enabled only where a legitimate API, feed, export, public catalog, or user-provided route exists. No anti-bot bypassing.")
    cols = st.columns(4)
    for i, source in enumerate(all_sources):
        with cols[i % 4]:
            status = "🟢 Automated" if source in enabled_sources else "⚪ Ready for adapter"
            st.write(f"**{source.name}**")
            st.caption(status)

# ---------------------------------------------------------------------------
# PRIMARY SEARCH
# ---------------------------------------------------------------------------
st.markdown("## 🔎 Find hidden opportunities")
st.caption("CRTC starts with official eBay search and can also launch permitted public auction research from one place.")

with st.container(border=True):
    e1, e2, e3 = st.columns([3, 1, 1])
    with e1:
        ebay_query = st.text_input("What are you hunting?", placeholder="e.g. Rolex, sterling silver, vintage tools, Martin guitar", help="Use normal buyer terms. CRTC scores what the seller actually wrote.")
    with e2:
        ebay_limit = st.number_input("Listings", min_value=5, max_value=50, value=25, step=5)
    with e3:
        ebay_min_score = st.number_input("Minimum Radar", min_value=0.0, max_value=100.0, value=25.0, step=5.0)

    if st.button("🚀 FIND HIDDEN DEALS", type="primary", use_container_width=True):
        if not ebay_query.strip():
            st.warning("Enter something to hunt for first.")
        else:
            try:
                with st.spinner("Searching eBay → normalizing listings → looking for hidden signals…"):
                    scan = scan_ebay(ebay_query, limit=int(ebay_limit), min_score=float(ebay_min_score))
                st.session_state["ebay_scan"] = scan
            except EbayAuthError:
                st.error("eBay is not configured in this deployment yet. CRTC needs EBAY_CLIENT_ID and EBAY_CLIENT_SECRET in Streamlit Secrets for automatic API searching.")
                st.info("You do **not** need to give CRTC your eBay password. The official Browse API uses application OAuth credentials.")
            except Exception as exc:
                st.error(f"eBay scan failed: {exc}")

# ---------------------------------------------------------------------------
# IMAGE SEARCH
# ---------------------------------------------------------------------------
st.markdown("## 📷 Scan an item")
st.caption("Upload a photo and CRTC will use eBay's documented image-search endpoint to find visually similar active listings when your eBay API is configured.")
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
    st.markdown(f"## 🎯 {scan.source} hunt: `{scan.query}`")
    st.caption(f"{scan.fetched} active listings examined · asking prices only · sold prices are never represented as active evidence")
    if not scan.opportunities:
        st.info("No listings met the selected Radar threshold. Try a broader search or lower the minimum score.")
    else:
        for candidate in scan.opportunities:
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
                c4.metric("Review", "YES" if candidate.review else "—")
                if candidate.listing.get("url"):
                    st.link_button("Open listing", candidate.listing["url"])
                if candidate.signals:
                    st.markdown("**Why CRTC flagged it**")
                    for signal in candidate.signals:
                        st.write(f"**{signal['severity'].upper()} · +{signal['score']:.0f}** — {signal['message']}")
                else:
                    st.caption("No individual anomaly signals were returned for this candidate.")

# ---------------------------------------------------------------------------
# PUBLIC AUCTION RESEARCH HUB
# ---------------------------------------------------------------------------
st.markdown("## 🌎 Research more auction sources")
st.caption("For sources without an approved API adapter, CRTC now gives you a one-tap public research launch. These links open the source's own site; CRTC does not bypass logins, CAPTCHAs, or access controls.")

from source_search import public_search_url

research_query = st.text_input("Research term", value=ebay_query, placeholder="e.g. vintage Rolex")
source_keys = [
    ("ctbids", "CTBids / Estate Auctions"), ("shopgoodwill", "ShopGoodwill"),
    ("hibid", "HiBid"), ("proxibid", "Proxibid"),
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

# ---------------------------------------------------------------------------
# MANUAL LISTING ANALYSIS
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# BATCH IMPORT
# ---------------------------------------------------------------------------
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
