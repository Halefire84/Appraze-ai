"""CRTC Holy Grail Finder — live scanner UI."""
import pandas as pd
import streamlit as st

from comps_adapters import EbayAuthError, EbayBrowseAdapter, is_ebay_configured
from holy_grail_pipeline import rank_opportunities

st.set_page_config(page_title="CRTC — Holy Grail Finder", page_icon="🔥", layout="wide")

st.title("🔥 CRTC Holy Grail Finder")
st.caption("Find overlooked listings, score the opportunity, then investigate before buying.")

with st.sidebar:
    st.subheader("Search")
    query = st.text_input("What are you hunting?", placeholder="e.g. sterling silver watch")
    limit = st.slider("Listings to scan", 5, 50, 20)
    min_score = st.slider("Minimum Opportunity Score", 0, 95, 25)

if not is_ebay_configured():
    st.warning("eBay is not configured yet. Add EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to the deployment secrets, then return here.")
    st.info("The Radar and demo mode still work without eBay credentials.")
else:
    if st.button("🔎 Scan eBay", type="primary", use_container_width=True):
        if not query.strip():
            st.error("Enter something to hunt for first.")
        else:
            try:
                with st.spinner("Scanning eBay and scoring listings…"):
                    comps = EbayBrowseAdapter().fetch_comps(query, limit=limit)
                    raw = []
                    for comp in comps:
                        raw.append({
                            "source": comp.source,
                            "title": comp.title,
                            "price": comp.price,
                            "shipping": comp.shipping,
                            "condition": comp.condition,
                            "url": comp.url,
                        })
                    results = rank_opportunities(raw, min_score=min_score)
                    st.session_state["crtc_holy_grail_results"] = results
                    st.session_state["crtc_holy_grail_scanned"] = len(comps)
            except EbayAuthError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"The eBay scan failed: {exc}")

results = st.session_state.get("crtc_holy_grail_results", [])
scanned = st.session_state.get("crtc_holy_grail_scanned", 0)

if scanned:
    st.success(f"Scanned {scanned} live eBay listings. {len(results)} met the current review threshold.")

if results:
    rows = []
    for item in results:
        listing = item.listing
        rows.append({
            "Score": round(item.score, 1),
            "Tier": item.tier,
            "Price": listing.get("price"),
            "Title": listing.get("title"),
            "Condition": listing.get("condition", ""),
            "Signals": "; ".join(s["message"] for s in item.signals),
            "URL": listing.get("url", ""),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### Top opportunities")
    for item in results[:10]:
        listing = item.listing
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{item.tier} — {listing.get('title', 'Untitled')}**")
                st.write(f"Asking: **${listing.get('price', 0):,.2f}** · Score: **{item.score:.0f}/100**")
                for signal in item.signals:
                    st.write(f"• {signal['message']}")
            with c2:
                if listing.get("url"):
                    st.link_button("Open listing", listing["url"], use_container_width=True)
                st.caption("Radar = lead, not proof. Verify condition, authenticity, shipping, fees, and comps before buying.")
