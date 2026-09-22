"""CRTC government electronics hunting page."""
import json
import streamlit as st

from crtc_hunt_engine import analyze_listing
from opportunity_sources import scan_ebay
from source_profiles import get_hunt_profile

st.set_page_config(page_title="CRTC — Government Electronics", page_icon="🏛️", layout="wide")
from auth import require_auth
require_auth()

st.title("🏛️ Government, Liquidation & Electronics Hunt")
st.caption("Find computers, phones, tablets and surplus where the information is incomplete — then calculate the real maximum bid.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("CPU floor", "Intel 8th gen+", "preferred")
c2.metric("Risk focus", "Locks / MDM", "penalized")
c3.metric("Best sourcing", "Local lots", "freight avoided")
c4.metric("Decision", "MAX BID", "not retail value")

st.info("CRTC separates two questions: **Holy Grail** asks why the market may have missed the value; **Acquisition Brain** asks whether the lot still makes money after recovery rate, fees, freight, tax, repairs and lock risk.")

st.subheader("🎯 Hunting profile")
choice = st.selectbox("What do you want CRTC to hunt?", [
    "Modern Computers & Laptops",
    "Phones & Tablets",
    "Amazon / Retail Returns",
    "Government & Institutional Surplus",
])
profile_key = {
    "Modern Computers & Laptops": "modern_computers",
    "Phones & Tablets": "phones_tablets",
    "Amazon / Retail Returns": "amazon_returns",
    "Government & Institutional Surplus": "government_surplus",
}[choice]
profile = get_hunt_profile(profile_key)

st.write("**Preferred sources:**", ", ".join(profile.source_keys))
st.write("**Categories:**", ", ".join(profile.preferred_categories))
st.write("**Risk ceiling:**", f"{profile.max_risk:.0%}")
st.caption(profile.notes)

st.subheader("⚡ Live eBay last-chance hunt")
st.caption("eBay is currently the automated source. The hunt is restricted to auction listings ending within 24 hours and the existing $100 → $125 → $150 acquisition ceiling.")
query = st.text_input("Search eBay", "Dell Latitude laptop")
if st.button("🚨 HUNT eBay NOW", type="primary"):
    try:
        scan = scan_ebay(query, limit=25, min_score=25)
        st.success(f"Fetched {scan.fetched} qualifying eBay auction candidates.")
        for candidate in scan.opportunities:
            item = candidate.listing
            st.markdown(f"### {candidate.tier} · {candidate.score:.0f}/100")
            st.write(f"**{item.get('title', 'Untitled')}** — ${float(item.get('price') or 0):,.2f}")
            if item.get("url"):
                st.link_button("Open listing", item["url"])
            if candidate.signals:
                st.caption("Signals: " + ", ".join(s["code"] for s in candidate.signals))
    except Exception as exc:
        st.error(f"The live hunt failed safely: {exc}")

st.subheader("📋 Analyze a CTBids / Goodwill / GovDeals / auction listing")
st.caption("These sources are intentionally user-input/authorized-feed routes until an approved API, feed, export, or written automation permission is available. Paste the listing facts here and CRTC will run the same brains used by automated sources.")

with st.form("listing_intake"):
    title = st.text_input("Listing title")
    description = st.text_area("Description", height=130)
    source = st.selectbox("Source", ["CTBids", "ShopGoodwill", "GovDeals", "GSA", "PublicSurplus", "B-Stock", "Other"])
    url = st.text_input("Listing URL")
    left, right = st.columns(2)
    with left:
        current_bid = st.number_input("Current bid / price", min_value=0.0, value=0.0, step=5.0)
        expected_resale = st.number_input("Expected resale value of recoverable inventory", min_value=0.0, value=0.0, step=25.0)
        recovery_rate = st.slider("Recovery rate", 0.0, 1.0, 0.75, 0.05)
        quantity = st.number_input("Quantity", min_value=1, value=1, step=1)
    with right:
        cpu_generation = st.number_input("Intel CPU generation (0 = unknown)", min_value=0, max_value=20, value=0, step=1)
        buyer_premium = st.number_input("Buyer premium / fees", min_value=0.0, value=0.0, step=5.0)
        freight = st.number_input("Freight / travel", min_value=0.0, value=0.0, step=10.0)
        repair_cost = st.number_input("Repair/accessory cost", min_value=0.0, value=0.0, step=10.0)
    tested = st.checkbox("Tested / powers on")
    manifested = st.checkbox("Manifested / itemized")
    locked = st.checkbox("Activation/MDM/BIOS lock risk")
    pickup_only = st.checkbox("Pickup only")
    submitted = st.form_submit_button("🔬 RUN CRTC HUNT ENGINE", type="primary")

if submitted:
    listing = {
        "source": source,
        "source_listing_id": url,
        "url": url,
        "title": title,
        "description": description,
        "category": "laptop" if profile_key == "modern_computers" else source.lower(),
        "price": current_bid,
        "current_bid": current_bid,
        "expected_resale": expected_resale,
        "recovery_rate": recovery_rate,
        "quantity": quantity,
        "cpu_generation": cpu_generation or None,
        "buyer_premium": buyer_premium,
        "freight": freight,
        "repair_cost": repair_cost,
        "tested": tested,
        "manifested": manifested,
        "locked": locked,
        "pickup_only": pickup_only,
        "condition": "tested" if tested else "unknown",
    }
    result = analyze_listing(listing, profile_key)
    a, b, c, d = st.columns(4)
    a.metric("CRTC score", f"{result['combined_score']:.0f}/100")
    b.metric("Tier", result["tier"])
    c.metric("Max total acquisition", f"${result['acquisition']['economics']['max_total_acquisition']:,.2f}")
    d.metric("Headroom", f"${result['acquisition']['economics']['headroom']:,.2f}")

    if result["decision"] == "BUY_CANDIDATE":
        st.success("🟢 BUY CANDIDATE — still verify the listing and all auction terms before bidding.")
    elif result["decision"] == "INVESTIGATE":
        st.warning("🟡 INVESTIGATE — CRTC sees potential, but one or more important facts remain uncertain.")
    else:
        st.error("🔴 PASS — the modeled economics do not justify the risk yet.")

    st.write("**Holy Grail signals:**", ", ".join(result["holy_grail"]["signals"]) or "None")
    st.write("**Acquisition signals:**", ", ".join(result["acquisition"]["signals"]) or "None")
    st.json(result)

st.subheader("🎯 Current hunt targets")
st.markdown("""
- **Intel 8th generation or newer** laptops/desktops/workstations
- Business-class Dell Latitude/Precision, Lenovo ThinkPad, HP EliteBook/ProBook/ZBook
- iPhones/iPads and modern Android devices with clean activation status
- Government/municipal IT lots with inspection or pickup
- Liquidation lots with manifests and identifiable models
- Repair/parts lots only when salvage value makes the downside attractive
""")

st.subheader("🚦 CRTC rules")
st.markdown("""
**BUY** — modeled net economics pass the configured threshold.

**INVESTIGATE** — potentially excellent, but critical facts such as model, lock status, quantity, condition or freight are missing.

**PASS** — apparent retail value is not enough to justify the acquisition risk.
""")

st.warning("CRTC will not bypass CAPTCHAs, private APIs, robots controls, or anti-bot systems. For CTBids, ShopGoodwill, GovDeals and similar marketplaces, automated collection will only be enabled through an approved API/feed/export or written permission; otherwise the Android-friendly listing intake above is the live bridge.")
