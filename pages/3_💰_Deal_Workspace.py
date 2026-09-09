"""CRTC Deal Workspace — verify a lead before buying."""
import pandas as pd
import streamlit as st

from deal_workspace import build_deal_workspace
from inventory_bridge import build_inventory_intake

st.set_page_config(page_title="CRTC — Deal Workspace", page_icon="💰", layout="wide")
st.title("💰 CRTC Deal Workspace")
st.caption("Verify value, account for real acquisition costs, make the decision, then prepare a BUY for inventory intake.")

saved = st.session_state.setdefault("saved_opportunities", [])
if not saved:
    st.info("No saved opportunities are loaded in this session. Save a lead from Opportunity Radar, or enter one below.")

selected_index = st.selectbox(
    "Saved opportunity",
    options=[-1] + list(range(len(saved))),
    format_func=lambda i: "Manual entry" if i == -1 else f"#{i + 1} — {saved[i].get('title', 'Untitled')}",
)
selected = saved[selected_index] if selected_index >= 0 else {}

with st.container(border=True):
    st.markdown("### Deal inputs")
    title = st.text_input("Item / lot title", value=str(selected.get("title", "")))
    source = st.text_input("Source", value=str(selected.get("source", "eBay")))
    price = st.number_input("Current price / bid", min_value=0.0, value=float(selected.get("price", 0) or 0), step=5.0)
    market_value = st.number_input("Market value", min_value=0.0, value=float(selected.get("market_value", 0) or 0), step=10.0)
    confidence = st.selectbox("Market evidence confidence", ["UNKNOWN", "LOW", "MEDIUM", "HIGH"], index=2)
    auction = source.lower() in {"ctbids / estate auctions", "shopgoodwill", "hibid"} or "auction" in source.lower()

    buyer_premium = None
    shipping = None
    if auction:
        buyer_premium_input = st.number_input("Buyer premium %", min_value=0.0, value=0.0, step=1.0, help="Enter the published premium. Do not guess it.")
        shipping = st.number_input("Shipping / handling", min_value=0.0, value=0.0, step=5.0)
        premium_known = st.checkbox("I verified the buyer premium", value=False)
        buyer_premium = buyer_premium_input if premium_known else None

    listing = {
        "title": title,
        "source": source,
        "price": price,
        "buyer_premium": buyer_premium,
        "shipping": shipping,
        "source_listing_id": selected.get("source_listing_id", ""),
        "url": selected.get("url", ""),
    }

    if st.button("🎯 MAKE CRTC DECISION", type="primary", use_container_width=True):
        result = build_deal_workspace(listing, market_value or None, confidence)
        st.session_state["crtc_deal_result"] = result
        st.session_state["crtc_deal_listing"] = listing

result = st.session_state.get("crtc_deal_result")
result_listing = st.session_state.get("crtc_deal_listing", listing)
if result:
    st.markdown("## Decision")
    decision = result["decision"]
    if decision == "BUY":
        st.success(f"🟢 **BUY** — {result['reason']}")
    elif decision == "PASS":
        st.error(f"🔴 **PASS** — {result['reason']}")
    elif decision == "BORDERLINE":
        st.warning(f"🟡 **BORDERLINE** — {result['reason']}")
    else:
        st.info(f"🔎 **REVIEW** — {result['reason']}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Market value", f"${result['market_value']:,.2f}" if result.get("market_value") is not None else "—")
    c2.metric("Maximum bid / buy", f"${result['max_bid']:,.2f}" if result.get("max_bid") is not None else "UNKNOWN")
    c3.metric("Confidence", result.get("confidence", "UNKNOWN"))
    all_in = result.get("all_in") or {}
    c4.metric("All-in now", f"${all_in.get('all_in_cost', 0):,.2f}" if all_in else "—")

    if all_in and not all_in.get("complete", True):
        st.warning("⚠️ Acquisition cost is incomplete. Verify the auction's buyer premium before treating the maximum bid as actionable.")

    if decision == "BUY":
        st.markdown("### 📦 Inventory intake")
        intake = build_inventory_intake(result_listing, result)
        st.write("CRTC has prepared this item for inventory. Physical receipt and final cost still need verification.")
        st.json(intake)
        if st.button("📥 ADD TO INVENTORY INTAKE", type="primary", use_container_width=True):
            inventory = st.session_state.setdefault("crtc_inventory_intake", [])
            inventory.append(intake)
            st.success("Added to this session's inventory intake queue.")

    st.markdown("### Purchase checklist")
    checks = [
        "Confirm the exact item/model and condition from the original listing.",
        "Verify market evidence is comparable to the actual item, not merely a similar-looking listing.",
        "Verify buyer premium and shipping/pickup costs before bidding.",
        "Never exceed CRTC's maximum acquisition price without deliberately overriding the model.",
        "If evidence is weak or conflicting, keep the decision at REVIEW.",
    ]
    for i, item in enumerate(checks):
        st.checkbox(item, key=f"check_{i}")

st.markdown("### Decision history")
history = st.session_state.setdefault("crtc_decision_history", [])
if result and st.button("💾 Save this decision"):
    history.append({"Title": title, "Source": source, "Price": price, "Market value": result.get("market_value"), "Max buy": result.get("max_bid"), "Decision": result.get("decision"), "Confidence": result.get("confidence")})
if history:
    st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)

st.markdown("### 📦 Inventory intake queue")
intake_queue = st.session_state.get("crtc_inventory_intake", [])
if intake_queue:
    st.dataframe(pd.DataFrame(intake_queue), use_container_width=True, hide_index=True)
else:
    st.caption("BUY decisions added here are pending physical acquisition and final receipt verification.")

st.caption("CRTC · FIND → IDENTIFY → VALUE → DECIDE → BUY → TRACK → LIST → SELL → MEASURE")
