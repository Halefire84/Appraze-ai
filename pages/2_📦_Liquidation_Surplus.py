"""CRTC Liquidation & Surplus acquisition hunter."""
import streamlit as st

from acquisition_hunter import PROFILES, estimate_max_bid, score_acquisition

st.set_page_config(page_title="CRTC — Liquidation & Surplus", page_icon="📦", layout="wide")
from auth import require_auth
require_auth()

st.title("📦 CRTC Liquidation & Surplus")
st.caption("Government surplus • computers • phones • Amazon/retail returns • pallets • IT liquidation")
st.info("CRTC evaluates the economics and risk of a lot. It does not assume every pallet is profitable: recovery rate, freight, repairs, locks, missing parts, and buyer costs matter.")

st.markdown("### 🔎 Hunt the right marketplaces")
links = {
    "🏛 GovDeals Electronics": "https://www.govdeals.com/consumer-electronics",
    "💻 GovDeals Laptops": "https://www.govdeals.com/computers-laptops",
    "📦 Amazon Liquidation / B-Stock": "https://bstock.com/amazon/",
    "🛒 B-Stock All Liquidation": "https://bstock.com/",
    "🏛 GSA Auctions": "https://www.gsaauctions.gov/",
}
cols = st.columns(3)
for i, (label, url) in enumerate(links.items()):
    with cols[i % 3]:
        st.link_button(label, url, use_container_width=True)

st.markdown("### 🎯 Acquisition profile")
profile_key = st.selectbox("What are we hunting?", list(PROFILES), format_func=lambda k: PROFILES[k].name)

with st.container(border=True):
    st.markdown("#### Lot economics")
    c1, c2, c3 = st.columns(3)
    with c1:
        current_bid = st.number_input("Current bid / asking", min_value=0.0, value=100.0, step=10.0)
        expected_resale = st.number_input("Expected resale if everything worked", min_value=0.0, value=1000.0, step=100.0)
        recovery_rate = st.slider("Expected usable/recoverable %", 0, 100, 75) / 100
    with c2:
        buyer_premium = st.number_input("Buyer premium / fees", min_value=0.0, value=0.0, step=10.0)
        tax = st.number_input("Tax", min_value=0.0, value=0.0, step=10.0)
        freight = st.number_input("Freight / pickup cost", min_value=0.0, value=0.0, step=10.0)
    with c3:
        repair_cost = st.number_input("Repairs", min_value=0.0, value=0.0, step=10.0)
        accessory_cost = st.number_input("Chargers / parts / accessories", min_value=0.0, value=0.0, step=10.0)
        other_costs = st.number_input("Other costs", min_value=0.0, value=0.0, step=10.0)

with st.expander("🧠 Evidence & risk — fill what the listing actually says", expanded=True):
    a, b, c = st.columns(3)
    with a:
        title = st.text_input("Lot title", placeholder="e.g. 12 Dell Latitude laptops — untested")
        condition = st.selectbox("Condition", ["unknown", "tested", "working", "refurbished", "new"])
        tested = st.checkbox("Seller explicitly says tested/working")
        manifested = st.checkbox("Manifest provided")
    with b:
        cpu_generation = st.number_input("Intel CPU generation (0 if unknown)", min_value=0, max_value=20, value=0)
        locked = st.checkbox("Generic device lock risk")
        activation_lock = st.checkbox("Phone activation-lock risk")
        mdm_lock = st.checkbox("MDM / enterprise-lock risk")
    with c:
        unmanifested = st.checkbox("Unmanifested / contents uncertain")
        missing_charger = st.checkbox("Missing chargers/accessories")
        pickup_only = st.checkbox("Pickup only")
        description = st.text_area("Description / notes", height=100)

listing = {
    "title": title,
    "description": description,
    "condition": condition,
    "tested": tested,
    "manifested": manifested,
    "cpu_generation": cpu_generation or None,
    "locked": locked,
    "activation_lock": activation_lock,
    "mdm_lock": mdm_lock,
    "unmanifested": unmanifested,
    "missing_charger": missing_charger,
    "pickup_only": pickup_only,
    "current_bid": current_bid,
    "expected_resale": expected_resale,
    "recovery_rate": recovery_rate,
    "buyer_premium": buyer_premium,
    "tax": tax,
    "freight": freight,
    "repair_cost": repair_cost,
    "accessory_cost": accessory_cost,
    "other_costs": other_costs,
}

if st.button("🧮 RUN CRTC ACQUISITION VERDICT", type="primary", use_container_width=True):
    result = score_acquisition(listing, profile_key)
    economics = result["economics"]
    verdict = result["decision"]
    if verdict == "BUY_CANDIDATE":
        st.success(f"🟢 BUY CANDIDATE — {result['score']:.0f}/100")
    elif verdict == "INVESTIGATE":
        st.warning(f"🟡 INVESTIGATE — {result['score']:.0f}/100")
    else:
        st.error(f"🔴 PASS — {result['score']:.0f}/100")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Effective resale", f"${economics['effective_resale']:,.0f}")
    m2.metric("All-in fixed costs", f"${economics['fixed_costs']:,.0f}")
    m3.metric("Max total acquisition", f"${economics['max_total_acquisition']:,.0f}")
    m4.metric("Bid headroom", f"${economics['headroom']:,.0f}")
    st.markdown("**CRTC evidence / risk signals**")
    for signal in result["signals"]:
        st.write(f"• `{signal}`")

st.markdown("### 📋 Modern-computer quick rule")
st.caption("For the computer preset, 8th-gen Intel or newer is treated as modern when the generation is explicitly known. Unknown CPU generation is not silently treated as modern. Locked devices and unknown condition reduce the score.")

st.markdown("### ⚠️ Amazon liquidation reality")
st.caption("Amazon Liquidation Auctions on B-Stock includes overstock, customer returns, and warehouse-damaged inventory. Amazon's official storefront says buyers must be approved and submit a valid reseller certificate; shipments and lot quantities can also have operational uncertainties. CRTC therefore treats manifests, shortages, freight, and recovery rate as first-class inputs rather than using retail MSRP as profit.")

st.caption("CRTC · FIND → IDENTIFY → VALUE → DECIDE → BUY → TRACK → LIST → SELL → MEASURE")
