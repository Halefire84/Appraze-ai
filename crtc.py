"""CRTC Cross-List prototype.

Central inventory -> marketplace-specific listing drafts.
Prototype publishers are intentionally mocked; production connectors should use
approved marketplace APIs/integrations.

Run:
    streamlit run crtc.py
"""

from dataclasses import dataclass, asdict
from typing import Dict, List
import json
import pandas as pd
import streamlit as st

st.set_page_config(page_title="CRTC — Cross-List", page_icon="🛒", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(180deg,#090d12 0%,#111720 100%); }
.block-container { max-width: 1250px; padding-top: 2rem; }
.crtc-title { font-size:2.7rem; font-weight:800; letter-spacing:-.04em; }
.crtc-sub { color:#8e99a8; margin-top:-12px; }
.card { background:#151c25; border:1px solid #263140; border-radius:16px;
        padding:18px; margin-bottom:12px; }
</style>
""", unsafe_allow_html=True)

MARKETPLACES = [
    "eBay", "Etsy", "Facebook Marketplace",
    "Mercari", "Poshmark", "Depop"
]

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
    limits = {
        "eBay": 80, "Etsy": 140, "Facebook Marketplace": 100,
        "Mercari": 80, "Poshmark": 80, "Depop": 65
    }
    return {
        "marketplace": marketplace,
        "sku": item.sku,
        "title": item.title[:limits.get(marketplace, 80)],
        "description": item.description,
        "category": item.category,
        "price": item.price,
        "quantity": item.quantity,
        "condition": item.condition,
        "photos": item.photos,
        "status": "DRAFT",
        "external_id": None,
    }

def publish_mock(draft: Dict) -> Dict:
    """Prototype only: never contacts a marketplace."""
    return {
        **draft,
        "status": "READY_TO_PUBLISH",
        "external_id": (
            f"DEMO-{draft['sku']}-"
            f"{draft['marketplace'].upper().replace(' ', '-')[:8]}"
        ),
    }

if "master" not in st.session_state:
    st.session_state.master = MasterItem(
        sku="CRTC-000001",
        title="Vintage Martin Acoustic-Electric Guitar",
        description=(
            "Vintage acoustic-electric guitar in very good used condition. "
            "Includes case. See photos for condition details."
        ),
        category="Musical Instruments",
        price=1249.00,
        cost=350.00,
        quantity=1,
        condition="Used — Very Good",
        photos=["photo-1", "photo-2", "photo-3"],
    )

if "drafts" not in st.session_state:
    st.session_state.drafts = {}

st.markdown('<div class="crtc-title">CRTC</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="crtc-sub">Cooper River Trading Co. · Cross-List Command Center</div>',
    unsafe_allow_html=True,
)
st.divider()

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
            price = st.number_input(
                "List price", min_value=0.0, value=float(m.price), step=1.0
            )
        with c2:
            cost = st.number_input(
                "Cost basis", min_value=0.0, value=float(m.cost), step=1.0
            )
            quantity = st.number_input(
                "Quantity", min_value=1, value=int(m.quantity), step=1
            )

        conditions = [
            "New", "Like New", "Used — Very Good",
            "Used — Good", "For Parts"
        ]
        condition = st.selectbox(
            "Condition", conditions, index=conditions.index(m.condition)
        )

        save = st.form_submit_button(
            "Save Master Item", type="primary", use_container_width=True
        )

    if save:
        st.session_state.master = MasterItem(
            sku, title, description, category, price,
            cost, quantity, condition, m.photos
        )
        st.session_state.drafts = {}
        st.success("Master item saved. Marketplace drafts regenerated from this master.")

    m = st.session_state.master
    profit = m.price - m.cost
    margin = (profit / m.price * 100) if m.price else 0

    st.markdown(
        f'<div class="card"><b>Gross profit</b> ${profit:,.2f}'
        f' &nbsp; · &nbsp; <b>Gross margin</b> {margin:.1f}%'
        f' &nbsp; · &nbsp; <b>Inventory</b> {m.quantity}</div>',
        unsafe_allow_html=True,
    )

with right:
    st.subheader("Choose Marketplaces")
    selected = st.multiselect(
        "Publish targets",
        MARKETPLACES,
        default=["eBay", "Facebook Marketplace", "Mercari"],
    )

    if st.button(
        "⚡ Generate All Listings",
        type="primary",
        use_container_width=True,
    ):
        st.session_state.drafts = {
            name: adapt_item(st.session_state.master, name)
            for name in selected
        }
        st.success(
            f"Generated {len(selected)} marketplace-specific drafts "
            "from one master listing."
        )

    if st.session_state.drafts:
        rows = [
            {
                "Marketplace": name,
                "Status": draft["status"],
                "SKU": draft["sku"],
                "Price": draft["price"],
            }
            for name, draft in st.session_state.drafts.items()
        ]
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

st.divider()
st.subheader("Marketplace Listings")

if not st.session_state.drafts:
    st.info(
        "Generate listings above. CRTC keeps one master inventory record "
        "and creates a marketplace-specific draft for each target."
    )
else:
    for marketplace, draft in list(st.session_state.drafts.items()):
        with st.expander(
            f"{marketplace} · {draft['status']}",
            expanded=True,
        ):
            a, b = st.columns([2, 1])

            with a:
                new_title = st.text_input(
                    "Marketplace title",
                    draft["title"],
                    key=f"title-{marketplace}",
                )
                new_desc = st.text_area(
                    "Marketplace description",
                    draft["description"],
                    key=f"desc-{marketplace}",
                )

            with b:
                new_price = st.number_input(
                    "Price",
                    value=float(draft["price"]),
                    key=f"price-{marketplace}",
                )
                st.caption(f"SKU: {draft['sku']}")

                if st.button(
                    f"Mark {marketplace} Ready",
                    key=f"ready-{marketplace}",
                    use_container_width=True,
                ):
                    draft.update({
                        "title": new_title,
                        "description": new_desc,
                        "price": new_price,
                    })
                    st.session_state.drafts[marketplace] = publish_mock(draft)
                    st.rerun()

st.divider()
st.subheader("Cross-Listing Controls")

q1, q2, q3 = st.columns(3)

with q1:
    if st.button("↻ Sync Quantity", use_container_width=True):
        st.toast(
            f"Master quantity is {st.session_state.master.quantity}. "
            "Prototype sync complete."
        )

with q2:
    payload = {
        "master": asdict(st.session_state.master),
        "marketplace_drafts": st.session_state.drafts,
    }
    st.download_button(
        "💾 Export Listing Package",
        json.dumps(payload, indent=2),
        "crtc-listing-package.json",
        "application/json",
        use_container_width=True,
    )

with q3:
    if st.button("Mark Item Sold", use_container_width=True):
        for draft in st.session_state.drafts.values():
            draft["status"] = "SOLD / DEACTIVATE"
        st.session_state.master.quantity = 0
        st.success(
            "Master inventory marked sold. All marketplace drafts are "
            "flagged for deactivation."
        )

st.caption(
    "Prototype boundary: CRTC does not bypass marketplace protections or "
    "simulate human browser activity. Production connectors will use "
    "approved marketplace APIs/integrations where available."
)
