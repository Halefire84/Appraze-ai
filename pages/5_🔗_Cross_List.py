"""Appraze Cross-List — marketplace-neutral listing workspace.

The page reuses the same master listing created by Flip Ledger. For eBay,
publishing is real: a connected eBay seller account and one click actually
creates a live eBay listing via ebay_listing.py's Sell Inventory API
integration. Every other marketplace remains draft-only by design --
Mercari/Poshmark/Depop/Facebook Marketplace have no public API for
third-party listing tools, and this app does not do browser automation
against a marketplace's own web form to fake one (see
SECURITY_RELEASE_CHECKLIST.md's anti-bot-bypass rule).
"""
import json
import secrets as _secrets_module

import pandas as pd
import streamlit as st

import ebay_listing
import ebay_sell
from listing_store import upsert_listing, transition_listing
from storage import load_table, save_table
from telemetry import log_event

st.set_page_config(page_title="Appraze — Cross-List", page_icon="🔗", layout="wide")
from auth import require_auth
require_auth()
st.title("🔗 Appraze Cross-List")
st.caption("ONE MASTER LISTING → marketplace-ready drafts → real eBay publishing, manual export elsewhere")

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


# ---------------------------------------------------------------------------
# eBay OAuth connect/callback. This is the one marketplace with a real,
# rules-compliant listing-creation path -- see ebay_listing.py's docstring
# for the eBay-side prerequisites (RuName redirect, business policies).
# ---------------------------------------------------------------------------
_code = st.query_params.get("code")
_returned_state = st.query_params.get("state")
if _code and _returned_state and _returned_state == st.session_state.get("_ebay_oauth_state"):
    try:
        creds = ebay_listing.exchange_code_for_tokens(_code)
        if ebay_listing.save_credentials(creds):
            st.success("eBay account connected.")
            log_event("INFO", "ebay_listing", "pages/5_Cross_List", "eBay account connected")
        else:
            st.error("eBay confirmed the connection but saving it failed. Try again.")
    except ebay_listing.EbayListingError as e:
        st.error(f"Couldn't connect eBay: {e}")
        log_event("ERROR", "ebay_listing", "pages/5_Cross_List", "eBay OAuth callback failed", {"error": str(e)})
    st.session_state.pop("_ebay_oauth_state", None)
    st.query_params.clear()

with st.container(border=True):
    st.markdown("### eBay account")
    if ebay_listing.is_connected():
        st.success("Connected. Real listings you mark READY_TO_PUBLISH below can be published directly to eBay.")
        if st.button("Disconnect eBay"):
            ebay_listing.disconnect()
            st.rerun()
    else:
        st.info(
            "Not connected. Connecting lets Appraze create real eBay listings on your behalf "
            "(you'll be sent to eBay to approve it, nothing happens without your consent there)."
        )
        try:
            state = _secrets_module.token_urlsafe(16)
            st.session_state["_ebay_oauth_state"] = state
            st.link_button("Connect eBay", ebay_listing.authorization_url(state), type="primary")
        except ebay_listing.EbayListingError as e:
            st.caption(f"eBay connection isn't configured in this deployment yet: {e}")

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
        status = draft.get("status", "DRAFT")
        with st.container(border=True):
            a, b = st.columns([3, 1])
            with a:
                st.markdown(f"**{marketplace}** · `{status}`")
                st.write(draft.get("title", "Untitled"))
                st.caption(f"${float(draft.get('price') or 0):,.2f} · SKU {draft.get('sku', '')}")
                if draft.get("external_id") and str(draft.get("external_id")).isdigit():
                    st.link_button("View live listing", f"https://www.ebay.com/itm/{draft['external_id']}")
            with b:
                if status == "DRAFT":
                    if st.button("MARK READY", key=f"ready_{i}", use_container_width=True):
                        updated = transition_listing(draft, "READY_TO_PUBLISH")
                        drafts = upsert_listing(drafts, updated)
                        result = save_rows(drafts, DRAFT_TABLE)
                        st.session_state["crtc_cross_list_message"] = "Draft marked READY_TO_PUBLISH." if result.success else f"Updated locally; save failed: {result.error}"
                        st.rerun()
                elif status == "READY_TO_PUBLISH" and marketplace == "eBay" and ebay_listing.is_connected():
                    if st.button("PUBLISH TO EBAY", key=f"publish_ebay_{i}", type="primary", use_container_width=True):
                        st.session_state[f"_show_ebay_publish_{i}"] = True
                        st.rerun()
                elif status == "READY_TO_PUBLISH" and marketplace == "eBay" and ebay_sell.is_authorized():
                    # Separate SANDBOX-only path (ebay_sell.py), independent of the
                    # production ebay_listing.py connection above -- hardcoded to
                    # *.sandbox.ebay.com, for proving the publish round-trip works
                    # without needing a live connected production eBay account.
                    if st.button("PUBLISH TO EBAY (SANDBOX TEST)", key=f"publish_ebay_sandbox_{i}", use_container_width=True):
                        st.session_state[f"_show_ebay_sandbox_publish_{i}"] = True
                        st.rerun()

            if marketplace == "eBay" and status == "READY_TO_PUBLISH" and st.session_state.get(f"_show_ebay_publish_{i}"):
                st.markdown("---")
                if not ebay_listing.is_connected():
                    st.warning("Connect eBay above first.")
                else:
                    policies = st.session_state.get("_ebay_policies_cache")
                    if policies is None:
                        policies = ebay_listing.get_business_policies()
                        st.session_state["_ebay_policies_cache"] = policies
                    missing = [k for k in ("payment", "return", "fulfillment") if not policies.get(k)]
                    if missing:
                        st.error(
                            f"No {', '.join(missing)} policy is set up on your eBay account yet. "
                            "Create one of each in Seller Hub → Account → Business Policies, then refresh this page."
                        )
                    else:
                        p1, p2, p3 = st.columns(3)
                        pay_choice = p1.selectbox("Payment policy", policies["payment"], format_func=lambda x: x["name"], key=f"pay_{i}")
                        ret_choice = p2.selectbox("Return policy", policies["return"], format_func=lambda x: x["name"], key=f"ret_{i}")
                        ful_choice = p3.selectbox("Fulfillment policy", policies["fulfillment"], format_func=lambda x: x["name"], key=f"ful_{i}")
                        category_id = st.text_input(
                            "eBay category ID", key=f"cat_{i}",
                            help="Find this via eBay's category search — publishing fails clearly if it's wrong, nothing is guessed.",
                        )
                        confirm = st.checkbox("This creates a REAL, live eBay listing.", key=f"confirm_{i}")
                        if st.button("Confirm publish", key=f"confirm_publish_{i}", disabled=not (confirm and category_id), use_container_width=True):
                            sku = str(draft.get("sku", ""))
                            item = {
                                "title": draft.get("title", ""),
                                "description": draft.get("description", ""),
                                "condition": "USED_GOOD",
                                "imageUrls": draft.get("imageUrls", []) or [],
                                "quantity": draft.get("quantity", 1),
                            }
                            offer = {
                                "price": draft.get("price"),
                                "quantity": draft.get("quantity", 1),
                                "category_id": category_id,
                                "description": draft.get("description", ""),
                                "payment_policy_id": pay_choice["id"],
                                "return_policy_id": ret_choice["id"],
                                "fulfillment_policy_id": ful_choice["id"],
                            }
                            with st.spinner("Publishing to eBay..."):
                                result = ebay_listing.publish_listing(sku, item, offer)
                            if result.ok:
                                updated = transition_listing(draft, "ACTIVE", external_id=result.listing_id)
                                drafts = upsert_listing(drafts, updated)
                                save_rows(drafts, DRAFT_TABLE)
                                st.session_state.pop(f"_show_ebay_publish_{i}", None)
                                st.session_state["crtc_cross_list_message"] = f"Published to eBay: {result.listing_url}"
                                log_event("INFO", "ebay_listing", "pages/5_Cross_List", "listing published", {"sku": sku, "listing_id": result.listing_id})
                                st.rerun()
                            else:
                                st.error(f"Publishing failed at the {result.step} step: {result.error}")
                                log_event("ERROR", "ebay_listing", "pages/5_Cross_List", f"publish failed at {result.step}", {"sku": sku, "error": result.error})

            if marketplace == "eBay" and status == "READY_TO_PUBLISH" and st.session_state.get(f"_show_ebay_sandbox_publish_{i}"):
                st.markdown("---")
                st.caption("Sandbox test publish (ebay_sell.py) — this listing is only visible on eBay's sandbox, never real eBay.")
                confirm_sandbox = st.checkbox("This creates a real SANDBOX eBay listing (not production).", key=f"confirm_sandbox_{i}")
                if st.button("Confirm sandbox publish", key=f"confirm_sandbox_publish_{i}", disabled=not confirm_sandbox, use_container_width=True):
                    with st.spinner("Publishing to eBay sandbox..."):
                        try:
                            published = ebay_sell.publish_master({**master, **draft})
                        except ebay_sell.EbaySellError as exc:
                            st.error(f"eBay sandbox publish failed: {exc}")
                            log_event("ERROR", "ebay_sell", "pages/5_Cross_List", "sandbox publish failed", {"sku": draft.get("sku", ""), "error": str(exc)})
                        else:
                            updated = transition_listing(draft, "ACTIVE", external_id=published["listing_id"])
                            updated["ebay_offer_id"] = published["offer_id"]
                            updated["ebay_environment"] = "sandbox"
                            drafts = upsert_listing(drafts, updated)
                            save_rows(drafts, DRAFT_TABLE)
                            st.session_state.pop(f"_show_ebay_sandbox_publish_{i}", None)
                            st.session_state["crtc_cross_list_message"] = f"Published to eBay sandbox — listing {published['listing_id']} (offer {published['offer_id']})."
                            log_event("INFO", "ebay_sell", "pages/5_Cross_List", "sandbox listing published", {"sku": draft.get("sku", ""), "listing_id": published["listing_id"]})
                            st.rerun()

st.divider()
st.caption(
    "eBay publishing above is real. Every other marketplace here is draft-only by design: "
    "Mercari, Poshmark, Depop, and Facebook Marketplace have no public API for third-party "
    "listing tools, and this app does not automate a marketplace's own web form to fake one."
)
if not ebay_sell.is_authorized():
    st.caption("eBay sandbox test publishing (separate from the production connection above) is not authorized yet — see docs/EBAY_SELL_SETUP.md.")

with st.expander("Export listing package"):
    st.download_button("Download JSON", json.dumps({"master": master, "drafts": matching}, indent=2), "crtc-listing-package.json", "application/json", use_container_width=True)
