"""CRTC Cross-List — marketplace-neutral listing workspace.

The page reuses the same master listing created by Flip Ledger. Publishing remains
an approved-API adapter concern; this page only prepares, persists, and exports
marketplace-specific drafts.
"""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from listing_store import upsert_listing, transition_listing
from storage import load_table, save_table

st.set_page_config(page_title="CRTC — Cross-List", page_icon="🔗", layout="wide")
st.title("🔗 CRTC Cross-List")
st.caption("ONE MASTER LISTING → marketplace-ready drafts → approved publishing")

MASTER_TABLE = "listing_masters"
DRAFT_TABLE = "listing_drafts"
MARKETPLACES = ["eBay", "Etsy", "Facebook Marketplace", "Mercari", "Poshmark", "Depop"]
TITLE_LIMITS = {"eBay": 80, "Etsy": 140, "Facebook Marketplace": 100, "Mercari": 80, "Poshmark": 80, "Depop": 65}


def adapt_item(master, marketplace):
    item = dict(master)
    item["marketplace"] = marketplace
    item["title"] = str(item.get("title") or "Untitled item")[:TITLE_LIMITS.get(marketplace, 80)]
    item["status"] = "DRAFT"
    return item


def load_rows(table):
    result = load_table(table)
    return result.payload or [] if result.success else []


def save_rows(rows, table):
    return save_table(pd.DataFrame(rows), table)

masters = load_rows(MASTER_TABLE)
if masters:
    master = masters[-1]
else:
    master = st.session_state.get("crtc_master_listing")

if not master:
    st.warning("No master listing is ready yet. In Flip Ledger, move a PURCHASED item to LISTED first.")
    st.stop()

st.success(f"Master listing ready: **{master.get('title', 'Untitled')}** · SKU `{master.get('sku', '')}` · ${float(master.get('price') or 0):,.2f}")

with st.container(border=True):
    st.markdown("### 1. Master listing")
    c1, c2, c3 = st.columns(3)
    c1.metric("List price", f"${float(master.get('price') or 0):,.2f}")
    c2.metric("Cost basis", f"${float(master.get('cost') or 0):,.2f}")
    c3.metric("Quantity", int(master.get("quantity") or 1))
    st.write(master.get("description") or "No description yet.")
    if master.get("source_url"):
        st.link_button("Open source lot", master["source_url"])

with st.container(border=True):
    st.markdown("### 2. Generate marketplace drafts")
    selected = st.multiselect("Marketplaces", MARKETPLACES, default=MARKETPLACES)
    if st.button("GENERATE ALL DRAFTS", type="primary", use_container_width=True):
        drafts = load_rows(DRAFT_TABLE)
        for marketplace in selected:
            drafts = upsert_listing(drafts, adapt_item(master, marketplace))
        result = save_rows(drafts, DRAFT_TABLE)
        if result.success:
            st.session_state["crtc_cross_list_message"] = f"Generated {len(selected)} marketplace drafts."
        else:
            st.session_state["crtc_cross_list_message"] = f"Drafts prepared locally; save failed: {result.error}"
        st.rerun()

if st.session_state.get("crtc_cross_list_message"):
    st.info(st.session_state["crtc_cross_list_message"])

drafts = load_rows(DRAFT_TABLE)
matching = [d for d in drafts if str(d.get("sku")) == str(master.get("sku"))]
if matching:
    st.markdown("### 3. Listing pipeline")
    for i, draft in enumerate(matching):
        marketplace = draft.get("marketplace", "Marketplace")
        with st.container(border=True):
            a, b = st.columns([3, 1])
            with a:
                st.markdown(f"**{marketplace}** · `{draft.get('status', 'DRAFT')}`")
                st.write(draft.get("title", "Untitled"))
                st.caption(f"${float(draft.get('price') or 0):,.2f} · SKU {draft.get('sku', '')}")
            with b:
                if st.button("MARK READY", key=f"ready_{i}", use_container_width=True):
                    updated = transition_listing(draft, "READY_TO_PUBLISH")
                    drafts = upsert_listing(drafts, updated)
                    result = save_rows(drafts, DRAFT_TABLE)
                    st.session_state["crtc_cross_list_message"] = "Draft marked READY_TO_PUBLISH." if result.success else f"Updated locally; save failed: {result.error}"
                    st.rerun()

st.divider()
st.caption("Publishing is intentionally not simulated here. Live marketplace posting requires each marketplace's approved API/partner access.")

with st.expander("Export listing package"):
    st.download_button("Download JSON", json.dumps({"master": master, "drafts": matching}, indent=2), "crtc-listing-package.json", "application/json", use_container_width=True)
