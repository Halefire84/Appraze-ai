"""CRTC government electronics hunting page."""
import streamlit as st

from source_profiles import get_hunt_profile

st.set_page_config(page_title="CRTC — Government Electronics", page_icon="🏛️", layout="wide")

st.title("🏛️ Government & Electronics Hunt")
st.caption("Find computers, phones, tablets and institutional surplus without guessing what a lot is worth.")

profile = get_hunt_profile("modern_computers")

c1, c2, c3, c4 = st.columns(4)
c1.metric("CPU floor", "Intel 8th gen+", "preferred")
c2.metric("Risk focus", "Locks / MDM", "penalized")
c3.metric("Best sourcing", "Local lots", "freight avoided")
c4.metric("Decision", "MAX BID", "not retail value")

st.info("CRTC will value the usable inventory, subtract fees/freight/repairs, model recovery rate, and calculate a maximum acquisition price. A large retail-value number is never treated as profit by itself.")

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

st.subheader("🔎 Current hunt targets")
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
**BUY** — modeled net profit and downside both pass the configured threshold.

**INVESTIGATE** — potentially excellent, but critical facts such as model, lock status, quantity, condition or freight are missing.

**PASS** — apparent retail value is not enough to justify the acquisition risk.
""")

st.warning("Live source collection is only enabled where CRTC has a legitimate API, feed, public catalog, permitted export, or user-provided listing route. No CAPTCHA bypassing, private API reverse-engineering, or anti-bot evasion.")
