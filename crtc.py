"""CRTC Cross-List Command Center.

One master inventory item produces marketplace-specific listing drafts.
Listing lifecycle is persisted separately from flip inventory. Publishing is
only performed by approved marketplace integrations; this prototype never
uses browser automation or anti-bot bypasses.
"""
from dataclasses import dataclass, asdict
from typing import Dict, List
import json
import pandas as pd
import streamlit as st
from listing_store import upsert_listing, transition_listing, mark_item_sold
from storage import load_table, save_table

st.set_page_config(page_title="CRTC — Cross-List", page_icon="🛒", layout="wide")

MARKETPLACES = ["eBay", "Etsy", "Facebook Marketplace", "Mercari", "Poshmark", "Depop"]
TITLE_LIMITS = {"eBay": 80, "Etsy": 140, "Facebook Marketplace": 100, "Mercari": 80, "Poshmark": 80, "Depop": 65}

@dataclass
class MasterItem:
    sku: str
    title: str
    description: str
    category: str
    price: float
    cost: float
    quantity: int
    condition: str
    photos: List[str]

def adapt_item(item: MasterItem, marketplace: str) -> Dict:
    return {
        "marketplace": marketplace,
        "sku": item.sku,
        "title": item.title[:TITLE_LIMITS.get(marketplace, 80)],
        "description": item.description,
        "category": item.category,
        "price": item.price,
        "quantity": item.quantity,
        "condition": item.condition,
        "photos": item.photos,
        "status": "DRAFT",
        "external_id": None,
    }

def persist_drafts() -> None:
    result = save_table(pd.DataFrame(list(st.session_state.drafts.values())), "listing_drafts")
    st.session_state["listing_storage_message"] = "Listing drafts saved." if result.success else f"Local drafts only; save failed: {result.error}"

def publish_mock(draft: Dict) -> Dict:
    """Demo transition only: never contacts a marketplace."""
    return transition_listing(draft, "READY_TO_PUBLISH", external_id=f"DEMO-{draft['sku']}-{draft['marketplace'].upper().replace(' ', '-')[:8]}")

if "master" not in st.session_state:
    master_rows = load_table("listing_masters")
    saved_master = (master_rows.payload or [])[-1] if master_rows.success and master_rows.payload else None
    if saved_master:
        st.session_state.master = MasterItem(
            str(saved_master.get("sku") or "CRTC-ITEM"),
            str(saved_master.get("title") or "Untitled item"),
            str(saved_master.get("description") or ""),
            str(saved_master.get("category") or ""),
            float(saved_master.get("price") or 0),
            float(saved_master.get("cost") or 0),
            max(1, int(saved_master.get("quantity") or 1)),
            str(saved_master.get("condition") or "Used"),
            list(saved_master.get("photos") or []),
        )
        st.session_state["master_source"] = "Flip Ledger"
    else:
        st.session_state.master = MasterItem("CRTC-000001", "Vintage Martin Acoustic-Electric Guitar", "Vintage acoustic-electric guitar in very good used condition. Includes case. See photos for condition details.", "Musical Instruments", 1249.00, 350.00, 1, "Used — Very Good", ["photo-1", "photo-2", "photo-3"])
        st.session_state["master_source"] = "Demo"

if "drafts" not in st.session_state:
    loaded = load_table("listing_drafts")
    rows = loaded.payload or [] if loaded.success else []
    st.session_state.drafts = {str(row.get("marketplace")): row for row in rows if row.get("marketplace")}
    st.session_state["listing_storage_message"] = "Loaded saved listing drafts." if loaded.success else f"Local listing drafts: {loaded.error}"

st.title("🛒 CRTC Cross-List Command Center")
st.caption("One master inventory record → marketplace-specific drafts → approved publishing integrations")
st.info(st.session_state.get("listing_storage_message", ""))
if st.session_state.get("master_source") == "Flip Ledger":
    st.success("Master listing received from Flip Ledger. Generate marketplace drafts below.")

left, right = st.columns([1.25, 1])
with left:
    st.subheader("Master Listing")
    m = st.session_state.master
    with st.form("master"):
        sku = st.text_input("SKU", m.sku)
        title = st.text_input("Title", m.title)
        description = st.text_area("Description", m.description, height=130)
        c1, c2 = st.columns(2)
        with c1:
            category = st.text_input("Category", m.category)
            price = st.number_input("List price", min_value=0.0, value=float(m.price), step=1.0)
        with c2:
            cost = st.number_input("Cost basis", min_value=0.0, value=float(m.cost), step=1.0)
            quantity = st.number_input("Quantity", min_value=1, value=int(m.quantity), step=1)
        conditions = ["New", "Like New", "Used — Very Good", "Used — Good", "For Parts"]
        condition = st.selectbox("Condition", conditions, index=conditions.index(m.condition) if m.condition in conditions else 2)
        save = st.form_submit_button("Save Master Item", type="primary", use_container_width=True)
    if save:
        st.session_state.master = MasterItem(sku, title, description, category, price, cost, quantity, condition, m.photos)
        st.session_state.drafts = {}
        persist_drafts()
        st.success("Master item saved. Generate fresh marketplace drafts.")
    m = st.session_state.master
    profit = m.price - m.cost
    margin = profit / m.price * 100 if m.price else 0
    st.metric("Projected gross profit", f"${profit:,.2f}", f"{margin:.1f}% margin")

with right:
    st.subheader("Choose Marketplaces")
    selected = st.multiselect("Publish targets", MARKETPLACES, default=["eBay", "Facebook Marketplace", "Mercari"])
    if st.button("⚡ Generate All Listings", type="primary", use_container_width=True):
        for name in selected:
            st.session_state.drafts[name] = adapt_item(st.session_state.master, name)
            rows = upsert_listing(st.session_state.drafts.values(), st.session_state.drafts[name])
            st.session_state.drafts = {str(row.get("marketplace")): row for row in rows if row.get("marketplace")}
        persist_drafts()
        st.success(f"Generated {len(selected)} marketplace-specific drafts.")

if st.session_state.drafts:
    st.dataframe(pd.DataFrame([{"Marketplace": n, "Status": d["status"], "SKU": d["sku"], "Price": d["price"]} for n,d in st.session_state.drafts.items()]), use_container_width=True, hide_index=True)

st.divider(); st.subheader("Marketplace Listings")
if not st.session_state.drafts:
    st.info("Generate listings above. CRTC keeps one master item and separate marketplace drafts.")
else:
    for marketplace, draft in list(st.session_state.drafts.items()):
        with st.expander(f"{marketplace} · {draft['status']}", expanded=True):
            a,b = st.columns([2,1])
            with a:
                new_title = st.text_input("Marketplace title", draft["title"], key=f"title-{marketplace}")
                new_desc = st.text_area("Marketplace description", draft["description"], key=f"desc-{marketplace}")
            with b:
                new_price = st.number_input("Price", value=float(draft["price"]), key=f"price-{marketplace}")
                st.caption(f"SKU: {draft['sku']} · External ID: {draft.get('external_id') or 'not published'}")
                if draft.get("status") not in {"SOLD", "DEACTIVATED"} and st.button(f"Mark {marketplace} Ready", key=f"ready-{marketplace}", use_container_width=True):
                    updated = dict(draft, title=new_title, description=new_desc, price=new_price)
                    st.session_state.drafts[marketplace] = publish_mock(updated)
                    persist_drafts(); st.rerun()

st.divider(); st.subheader("Cross-Listing Controls")
q1,q2,q3 = st.columns(3)
with q1:
    if st.button("↻ Sync Quantity", use_container_width=True):
        for draft in st.session_state.drafts.values():
            draft["quantity"] = st.session_state.master.quantity
        persist_drafts(); st.toast(f"Quantity synced to {st.session_state.master.quantity}.")
with q2:
    payload = {"master": asdict(st.session_state.master), "marketplace_drafts": st.session_state.drafts}
    st.download_button("💾 Export Listing Package", json.dumps(payload, indent=2), "crtc-listing-package.json", "application/json", use_container_width=True)
with q3:
    if st.button("Mark Item Sold", use_container_width=True):
        sold_rows = mark_item_sold(st.session_state.drafts.values())
        st.session_state.drafts = {str(row.get("marketplace")): row for row in sold_rows if row.get("marketplace")}
        st.session_state.master.quantity = 0
        persist_drafts()
        st.success("Master item marked sold; marketplace listings flagged SOLD for deactivation.")

st.caption("Prototype boundary: marketplace publishing uses approved APIs/integrations only. No anti-bot bypass or simulated browser activity.")
