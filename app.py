"""
Cooper River Trading Co. — Appraze
A Streamlit dashboard for tracking, evaluating, and AI-assisted
appraisal of resale/auction deals across CTBids, eBay, HiBid,
Facebook Marketplace, Mercari, Chairish, and Etsy.

Run locally (optional, no terminal needed for deployment - see DEPLOY.md):
    streamlit run app.py
"""

import base64
import io
import json
from datetime import date, datetime
from typing import Optional

import pandas as pd
import requests
import streamlit as st

from finance import (
    DEFAULT_FEE_PCT,
    DEFAULT_PREMIUM_PCT,
    DEFAULT_INVENTORY_FEE_PCT,
    GOLD_PURITY,
    SILVER_PURITY,
    MELT_CEILING_PCT,
    calc_deal,
    calc_melt,
    format_roi,
    inventory_health,
    inventory_margin,
    max_cost_for_target_roi,
)
from auth import render_login_gate, mark_paid
from storage import save_deals, load_deals, save_table, load_table
from billing import verify_checkout_session, payment_link_url
from drive_scan import scan_invoice_folder, mark_files_processed
from pos import create_pos_checkout, check_payment_status
import mail
from comps import Comp, summarize_comps, evaluate_with_comps
from comps_adapters import (
    CsvCompsAdapter,
    EbayAuthError,
    EbayBrowseAdapter,
    EbayInsightsNotApprovedError,
    EbayMarketplaceInsightsAdapter,
    is_ebay_configured,
)

# --------------------------------------------------------------------------
# PAGE CONFIG + GLOBAL STYLE
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Appraze — Cooper River Trading Co.",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded",
)

DARK_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

    .stApp {
        background:
            radial-gradient(1200px 600px at 15% -5%, rgba(77,124,255,0.08) 0%, transparent 60%),
            radial-gradient(1000px 500px at 100% 0%, rgba(34,201,140,0.06) 0%, transparent 55%),
            linear-gradient(180deg, #0a0d12 0%, #10151c 100%);
        color: #e6e9ef;
    }
    section[data-testid="stSidebar"] {
        background: #0b0e14;
        border-right: 1px solid #1f2733;
    }
    h1, h2, h3, h4 {
        font-family: 'Sora', 'Inter', sans-serif;
        color: #f5f7fb !important;
        letter-spacing: -0.02em;
    }

    /* ---- premium header wordmark ---- */
    .appraze-hero {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 4px 0 2px 0;
    }
    .appraze-hero .mark {
        font-family: 'Sora', sans-serif;
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        background: linear-gradient(120deg, #7dd3fc 0%, #4d7cff 45%, #22c98c 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .appraze-hero .tagline {
        color: #7c8798;
        font-size: 0.85rem;
        font-weight: 500;
        border-left: 1px solid #2a3441;
        padding-left: 14px;
        margin-left: 2px;
    }

    /* ---- KPI cards ---- */
    .kpi-card {
        background: linear-gradient(160deg, #151b25 0%, #0f141b 100%);
        border: 1px solid #232c38;
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: 0 4px 18px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03);
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: #3a4656;
    }
    .kpi-label {
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #8b96a5;
        margin-bottom: 6px;
        font-weight: 600;
    }
    .kpi-value { font-family: 'Sora', sans-serif; font-size: 1.65rem; font-weight: 700; color: #f7f9fc; }
    .kpi-sub { font-size: 0.8rem; color: #67e8a4; margin-top: 3px; font-weight: 600; }
    .kpi-sub.neg { color: #f2607a; }

    /* ---- badges ---- */
    .badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    .badge-strong_buy { background: linear-gradient(135deg, #0f2e22, #113a2a); color: #3fe0a5; border: 1px solid #22c98c55; }
    .badge-buy        { background: linear-gradient(135deg, #0f2e22, #113a2a); color: #22c98c; border: 1px solid #22c98c40; }
    .badge-at_ceiling { background: linear-gradient(135deg, #37260f, #3d2a10); color: #f5a524; border: 1px solid #f5a52440; }
    .badge-borderline { background: linear-gradient(135deg, #37260f, #3d2a10); color: #f5a524; border: 1px solid #f5a52440; }
    .badge-pass       { background: linear-gradient(135deg, #2b1418, #331519); color: #f2607a; border: 1px solid #f2607a40; }

    .ceiling-banner {
        background: linear-gradient(135deg, #2b1418, #2e1219);
        border: 1px solid #f2607a55;
        border-radius: 12px;
        padding: 12px 18px;
        color: #f2a5b0;
        font-weight: 600;
        margin: 10px 0 16px 0;
    }

    .autosave-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.76rem;
        color: #67e8a4;
        font-weight: 600;
        padding: 4px 0;
    }
    .autosave-dot {
        width: 7px; height: 7px; border-radius: 50%;
        background: #22c98c;
        box-shadow: 0 0 8px #22c98c99;
    }

    .stButton>button {
        border-radius: 10px;
        border: 1px solid #2a3441;
        background: linear-gradient(160deg, #1c232e, #161c25);
        color: #e6e9ef;
        font-weight: 600;
        transition: all 0.15s ease;
    }
    .stButton>button:hover {
        border-color: #4d7cff;
        color: #7dd3fc;
        box-shadow: 0 0 0 1px #4d7cff33;
    }
    button[kind="primary"] {
        background: linear-gradient(135deg, #4d7cff, #3a63e0) !important;
        border: none !important;
        color: white !important;
    }

    div[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; border: 1px solid #232c38; }
    .block-container { padding-top: 1.4rem; }
    hr { border-color: #232c38; }

    .stTabs [data-baseweb="tab-list"] {
        justify-content: flex-start !important;
        gap: 4px;
        border-bottom: 1px solid #232c38;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        color: #8b96a5;
        flex-grow: 0 !important;
    }
    .stTabs [aria-selected="true"] {
        color: #f5f7fb !important;
    }
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# DEMO MODE — a self-contained, no-login walkthrough for pitching the app to
# a stranger on the spot (a shop owner, a hotel guest, whoever). Deliberately
# isolated from everything else in this file:
#   - Never calls render_login_gate(), storage.py, or auth.py — no real
#     account, nothing persisted, nothing that could touch a real business's
#     data even by accident.
#   - The "Charge Card" button never calls Stripe — a real POS sale needs a
#     configured STRIPE_SECRET_KEY and sends the customer to a Stripe-hosted
#     page, which is the wrong thing to demo live on a stranger's/your own
#     phone in a few seconds. This simulates approval instantly instead.
#   - The AI step calls the real Anthropic API when ANTHROPIC_API_KEY is
#     configured (a real "wow" moment beats a canned one), but falls back to
#     a canned example on any failure — a demo must never visibly break
#     mid-pitch just because a hotel's wifi is bad.
# All state lives under demo_-prefixed session_state keys so it can never
# collide with the real app's "deals"/"inventory" state.
# --------------------------------------------------------------------------
DEMO_INVENTORY_SEED = [
    {"Item Name": "Vintage Coach Leather Handbag", "Cost Basis": 18.00, "List Price": 85.00, "Status": "Available", "Notes": "Estate sale find"},
    {"Item Name": "Air Jordan 1s, Size 10", "Cost Basis": 25.00, "List Price": 120.00, "Status": "Available", "Notes": "Thrift store"},
    {"Item Name": "KitchenAid Stand Mixer", "Cost Basis": 40.00, "List Price": 150.00, "Status": "Sold", "Notes": "Garage sale"},
]

DEMO_AI_FALLBACK = {
    "item_name": "Vintage Pyrex Mixing Bowl Set",
    "category": "Collectibles",
    "estimated_low": 35,
    "estimated_high": 65,
    "confidence": "medium",
    "notes": "Sample result — the live version identifies your actual photo/description instead.",
}


def _demo_ai_suggest(description: str, photo) -> dict:
    """Same call shape as tab_ai's call_claude_vision below, kept as its own
    small copy so demo mode has zero dependency on the rest of this file and
    can't be broken by later changes to the real Analyzer tab. Always
    returns a usable dict — never raises — so the demo can't crash on stage."""
    try:
        api_key = st.secrets.get("ANTHROPIC_API_KEY")
        if not api_key:
            return dict(DEMO_AI_FALLBACK)

        content = []
        if photo is not None:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": photo.type or "image/jpeg",
                    "data": base64.b64encode(photo.getvalue()).decode("utf-8"),
                },
            })
        content.append({
            "type": "text",
            "text": (
                "You are an expert resale appraiser demoing this tool live. Identify this item and "
                "estimate its realistic resale value range. Respond with ONLY a raw JSON object, no "
                "markdown fences, in exactly this shape: "
                '{"item_name": "...", "category": "...", "estimated_low": 0, "estimated_high": 0, '
                '"confidence": "low|medium|high", "notes": "one short sentence"}\n\n'
                f"Context from the seller: {description.strip() if description.strip() else '(none provided)'}"
            ),
        })
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-5", "max_tokens": 300, "messages": [{"role": "user", "content": content}]},
            timeout=20,
        )
        resp.raise_for_status()
        text = "\n".join(b["text"] for b in resp.json().get("content", []) if b.get("type") == "text")
        text = text.strip().replace("```json", "").replace("```", "").strip()
        parsed = json.loads(text)
        return {**DEMO_AI_FALLBACK, **parsed}
    except Exception:
        return dict(DEMO_AI_FALLBACK)


def _seed_demo_state():
    if "demo_inventory" not in st.session_state:
        st.session_state.demo_inventory = pd.DataFrame(DEMO_INVENTORY_SEED)
    if "demo_invoices" not in st.session_state:
        st.session_state.demo_invoices = []


def render_demo_mode():
    _seed_demo_state()

    top_l, top_r = st.columns([4, 1])
    with top_l:
        st.markdown("## 🪙 Appraze — Live Demo")
        st.caption("🎬 Sample data only · no real charges · nothing is saved anywhere")
    with top_r:
        if st.button("← Exit Demo", use_container_width=True):
            st.session_state.demo_mode = False
            st.rerun()

    st.markdown("#### 1. Add an item")
    with st.form("demo_add_item", clear_on_submit=True):
        dcol1, dcol2 = st.columns([2, 1])
        with dcol1:
            desc = st.text_input("Describe the item", placeholder="e.g. Vintage Pyrex mixing bowl set, minor wear")
        with dcol2:
            photo = st.file_uploader("Or a photo", type=["png", "jpg", "jpeg"], key="demo_photo")
        go = st.form_submit_button("✨ Suggest a price with AI", use_container_width=True)

    if go:
        if not desc.strip() and photo is None:
            st.warning("Add a photo or a short description first.")
        else:
            with st.spinner("Analyzing..."):
                result = _demo_ai_suggest(desc, photo)
            st.session_state.demo_last_ai = result

    ai_result = st.session_state.get("demo_last_ai")
    if ai_result:
        suggested_price = round((float(ai_result.get("estimated_low", 0) or 0) + float(ai_result.get("estimated_high", 0) or 0)) / 2, 2)
        st.success(f"**{ai_result.get('item_name', 'Item')}** — suggested list price **${suggested_price:,.2f}** ({ai_result.get('confidence', 'medium')} confidence)")
        if ai_result.get("notes"):
            st.caption(ai_result["notes"])
        if st.button("➕ Add to Inventory", key="demo_add_to_inv"):
            new_row = pd.DataFrame([{
                "Item Name": ai_result.get("item_name", "New Item"), "Cost Basis": 0.0,
                "List Price": suggested_price, "Status": "Available", "Notes": "Added via AI Analyzer",
            }])
            st.session_state.demo_inventory = pd.concat([st.session_state.demo_inventory, new_row], ignore_index=True)
            st.session_state.demo_last_ai = None
            st.rerun()

    st.markdown("---")
    st.markdown("#### 2. Inventory")
    st.dataframe(
        st.session_state.demo_inventory,
        use_container_width=True,
        column_config={
            "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
            "List Price": st.column_config.NumberColumn(format="$%.2f"),
        },
    )

    st.markdown("---")
    st.markdown("#### 3. Ring up a sale")
    available = st.session_state.demo_inventory[st.session_state.demo_inventory["Status"] == "Available"]
    if len(available) == 0:
        st.info("No available items — add one above.")
    else:
        pcol1, pcol2, pcol3 = st.columns([2, 1, 1])
        with pcol1:
            choice = st.selectbox("Item", available["Item Name"].tolist(), key="demo_pos_choice")
        row = available[available["Item Name"] == choice].iloc[0]
        with pcol2:
            sale_price = st.number_input("Price ($)", value=float(row["List Price"]), min_value=0.0, step=1.0, key="demo_pos_price")
        with pcol3:
            st.write("")
            st.write("")
            charge_clicked = st.button("💳 Charge Card", type="primary", use_container_width=True, key="demo_charge")

        if charge_clicked:
            idx = st.session_state.demo_inventory[st.session_state.demo_inventory["Item Name"] == choice].index[0]
            st.session_state.demo_inventory.loc[idx, "Status"] = "Sold"
            invoice_id = f"DEMO-{len(st.session_state.demo_invoices) + 1:03d}"
            st.session_state.demo_invoices.append({
                "Invoice #": invoice_id, "Item": choice, "Total": sale_price,
                "Time": datetime.now().strftime("%I:%M %p"),
            })
            st.success(f"✅ Payment approved — Invoice {invoice_id}. Inventory updated automatically.")
            st.rerun()

    if st.session_state.demo_invoices:
        st.markdown("---")
        st.markdown("#### Invoices")
        st.dataframe(
            pd.DataFrame(st.session_state.demo_invoices),
            use_container_width=True,
            column_config={"Total": st.column_config.NumberColumn(format="$%.2f")},
        )


if st.session_state.get("demo_mode"):
    render_demo_mode()
    st.stop()

if not st.session_state.get("authenticated"):
    _, demo_col = st.columns([3, 1])
    with demo_col:
        if st.button("🎬 Try Live Demo", use_container_width=True, help="No signup needed — sample data only"):
            st.session_state.demo_mode = True
            st.rerun()

if not render_login_gate():
    st.stop()


def enforce_paywall() -> bool:
    """
    Admins (you + Ashley) always pass through free. Everyone else needs a
    confirmed Stripe payment before seeing the app. Uses a Payment Link, not
    a card form — this app never touches card data, only checks payment
    status after the fact via Stripe's read-only session lookup.
    """
    if st.session_state.get("user_is_admin"):
        return True
    if st.session_state.get("user_is_paid"):
        return True

    session_id = st.query_params.get("session_id")
    if session_id:
        with st.spinner("Confirming your payment with Stripe..."):
            result = verify_checkout_session(session_id)
        if result.paid:
            mark_paid(st.session_state.get("username", ""))
            st.session_state.user_is_paid = True
            st.query_params.clear()
            st.rerun()
        else:
            st.error(f"Payment not confirmed yet ({result.error or 'still processing'}). If you just paid, wait a few seconds and refresh.")

    st.markdown(
        f"""<div class="appraze-hero">
            <span class="mark">Appraze</span>
            <span class="tagline">Cooper River Trading Co.</span>
        </div>""",
        unsafe_allow_html=True,
    )
    st.markdown("### 🔒 One step left")
    st.write(f"Hey {st.session_state.get('user_display_name', 'there')} — your account's created. Unlock full access to continue.")

    link = payment_link_url()
    st.info(
        "**Beta note:** this checkout is running in Stripe **test mode** — use card `4242 4242 4242 4242`, "
        "any future expiry date, any 3-digit CVC, any ZIP. No real charge happens.",
        icon="🧪",
    )
    if link:
        st.link_button("💳 Unlock Full Access", link, use_container_width=True, type="primary")
    else:
        st.warning("Payment link isn't configured yet — ask the admin to set STRIPE_PAYMENT_LINK_URL in secrets.")
    return False


if not enforce_paywall():
    st.stop()

PLATFORMS = ["CTBids", "eBay", "HiBid", "Facebook Marketplace", "Mercari", "Chairish", "Etsy", "Estate Sale", "Curbside"]
CATEGORIES = ["Gold/Silver Jewelry", "Sterling Flatware", "Watches", "Furniture", "Electronics", "Coins/Currency", "Collectibles", "Other"]
STATUSES = ["Watching", "Bid Placed", "Won/Purchased", "Listed", "Sold", "Passed"]


def verdict_badge_html(label: str, tier: str) -> str:
    return f'<span class="badge badge-{tier}">{label}</span>'


# --------------------------------------------------------------------------
# SESSION STATE INIT — load persisted data once per session after login
# --------------------------------------------------------------------------
if "deals_loaded" not in st.session_state:
    with st.spinner("Loading your saved data..."):
        result = load_deals()
    if result.success and result.payload:
        st.session_state.deals = pd.DataFrame(result.payload)
    elif "deals" not in st.session_state:
        st.session_state.deals = pd.DataFrame([
            {
                "Date Added": date.today().isoformat(),
                "Item": "14k Gold Chain Lot (Sample)",
                "Platform": "CTBids",
                "Category": "Gold/Silver Jewelry",
                "Cost": 85.00,
                "Est. Resale Value": 240.00,
                "Status": "Won/Purchased",
                "Notes": "Sample row \u2014 edit or delete me",
            }
        ])
    if not result.success and result.error:
        st.sidebar.warning(f"Couldn't load saved data: {result.error}. Starting fresh — your work will still try to save.")
    st.session_state.deals_loaded = True

if "editor_key" not in st.session_state:
    st.session_state.editor_key = 0

INVENTORY_STATUSES = ["Buy", "Track", "List", "Sold"]

if "inventory_loaded" not in st.session_state:
    with st.spinner("Loading your saved inventory..."):
        inv_result = load_table("inventory")
    if inv_result.success and inv_result.payload:
        st.session_state.inventory = pd.DataFrame(inv_result.payload)
    elif "inventory" not in st.session_state:
        st.session_state.inventory = pd.DataFrame([
            {
                "Item Name": "14k Gold Chain (Sample)",
                "Cost Basis": 85.00,
                "List Price": 240.00,
                "Platform Fee %": DEFAULT_INVENTORY_FEE_PCT,
                "Status": "List",
                "Sale Price": 0.0,
                "Notes": "Sample row — edit or delete me",
            }
        ])
    if not inv_result.success and inv_result.error:
        st.sidebar.warning(f"Couldn't load saved inventory: {inv_result.error}. Starting fresh.")
    st.session_state.inventory_loaded = True

if "inventory_editor_key" not in st.session_state:
    st.session_state.inventory_editor_key = 0


def persist():
    """Push current deals to shared/individual cloud storage — called automatically
    after every add/import/edit. Nothing to click, nothing to remember."""
    result = save_deals(st.session_state.deals)
    st.session_state.last_save_ok = result.success
    st.session_state.last_save_error = result.error
    st.session_state.last_save_time = datetime.now().strftime("%I:%M:%S %p")


def persist_inventory():
    """Same auto-save contract as persist(), for the Inventory table."""
    result = save_table(st.session_state.inventory, "inventory")
    st.session_state.last_inventory_save_ok = result.success
    st.session_state.last_inventory_save_error = result.error


def recalc_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived Gross Profit / Net Profit / Net Margin % / Health columns
    using finance.inventory_margin (cost basis -> list price, no buyer's
    premium — that's already sunk into cost basis by the time an item is
    priced for listing). For Sold items with a Sale Price entered, also adds
    a Realized Net Profit distinct from the Expected one everything else
    still in inventory is scored on."""
    df = df.copy()
    df["Cost Basis"] = pd.to_numeric(df["Cost Basis"], errors="coerce").fillna(0)
    df["List Price"] = pd.to_numeric(df["List Price"], errors="coerce").fillna(0)
    df["Platform Fee %"] = pd.to_numeric(df["Platform Fee %"], errors="coerce").fillna(DEFAULT_INVENTORY_FEE_PCT)
    df["Sale Price"] = pd.to_numeric(df.get("Sale Price", 0), errors="coerce").fillna(0)

    gross, net, margin, health, realized = [], [], [], [], []
    for _, row in df.iterrows():
        g, n, m = inventory_margin(row["Cost Basis"], row["List Price"], row["Platform Fee %"])
        gross.append(g)
        net.append(n)
        margin.append(m)
        health.append(inventory_health(m, n))
        if row.get("Status") == "Sold" and row["Sale Price"] > 0:
            _, realized_net, _ = inventory_margin(row["Cost Basis"], row["Sale Price"], row["Platform Fee %"])
            realized.append(realized_net)
        else:
            realized.append(None)

    df["Gross Profit"] = gross
    df["Net Profit"] = net
    df["Net Margin %"] = margin
    df["Health"] = health
    df["Realized Net Profit"] = realized
    return df


def add_deal_row(item: str, platform: str, category: str, cost: float, resale: float, status: str = "Watching", notes: str = ""):
    """Shared entry point for adding a deal — used by the sidebar form AND the
    'Send to Dashboard' handoff buttons in Melt Calculator / AI Analyzer, so
    data flows between tabs without retyping anything."""
    new_row = pd.DataFrame([{
        "Date Added": date.today().isoformat(),
        "Item": item.strip(),
        "Platform": platform,
        "Category": category,
        "Cost": cost,
        "Est. Resale Value": resale,
        "Status": status,
        "Notes": notes.strip(),
    }])
    st.session_state.deals = pd.concat([st.session_state.deals, new_row], ignore_index=True)
    st.session_state.editor_key += 1
    persist()


def recalc(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived profit/ROI/verdict columns using finance.calc_deal (CRTC five-tier scale)."""
    df = df.copy()
    df["Cost"] = pd.to_numeric(df["Cost"], errors="coerce").fillna(0)
    df["Est. Resale Value"] = pd.to_numeric(df["Est. Resale Value"], errors="coerce").fillna(0)

    profits, rois, verdicts, tiers = [], [], [], []
    for _, row in df.iterrows():
        result = calc_deal(row["Cost"], row["Est. Resale Value"])
        profits.append(result.gross_profit)
        rois.append(result.roi_pct)
        verdicts.append(result.verdict)
        tiers.append(result.verdict_tier)

    df["Gross Profit"] = profits
    df["ROI %"] = rois
    df["Verdict"] = verdicts
    df["_tier"] = tiers
    return df


# --------------------------------------------------------------------------
# SIDEBAR — ADD DEAL / IMPORT / EXPORT
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🪙 Appraze")
    admin_tag = " · Admin (shared)" if st.session_state.get("user_is_admin") else " · Paid" if st.session_state.get("user_is_paid") else ""
    st.caption(f"Logged in as {st.session_state.get('user_display_name', 'Tester')}{admin_tag}")

    last_save_time = st.session_state.get("last_save_time")
    if st.session_state.get("last_save_ok") is False:
        st.error(f"⚠️ Save failed: {st.session_state.get('last_save_error', 'unknown error')}")
    elif last_save_time:
        st.markdown(
            f'<div class="autosave-pill"><span class="autosave-dot"></span>Auto-saved · {last_save_time}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Auto-saves as you go — nothing to click.")

    if st.button("Log Out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("#### ➕ Add a Deal")
    with st.form("add_deal_form", clear_on_submit=True):
        item = st.text_input("Item description")
        c1, c2 = st.columns(2)
        with c1:
            platform = st.selectbox("Platform", PLATFORMS)
            cost = st.number_input("Cost ($)", min_value=0.0, step=1.0, format="%.2f")
        with c2:
            category = st.selectbox("Category", CATEGORIES)
            resale = st.number_input("Est. resale value ($)", min_value=0.0, step=1.0, format="%.2f")
        status = st.selectbox("Status", STATUSES, index=0)
        notes = st.text_area("Notes", height=68, placeholder="Karat, weight, condition, auction end time...")
        submitted = st.form_submit_button("Add to dashboard", use_container_width=True)

        if submitted:
            if not item.strip():
                st.warning("Give the item a name first.")
            else:
                add_deal_row(item, platform, category, cost, resale, status, notes)
                st.success(f"Added: {item.strip()}")

    st.markdown("---")
    st.markdown("#### 📥 Import / 📤 Export")

    uploaded = st.file_uploader("Import deals from CSV", type=["csv"])
    if uploaded is not None:
        try:
            imported = pd.read_csv(uploaded)
            required = {"Item", "Platform", "Category", "Cost", "Est. Resale Value", "Status"}
            if required.issubset(set(imported.columns)):
                if "Date Added" not in imported.columns:
                    imported["Date Added"] = date.today().isoformat()
                if "Notes" not in imported.columns:
                    imported["Notes"] = ""
                st.session_state.deals = pd.concat(
                    [st.session_state.deals, imported], ignore_index=True
                )
                persist()
                st.success(f"Imported {len(imported)} rows.")
            else:
                st.error(f"CSV must include columns: {', '.join(required)}")
        except Exception as e:
            st.error(f"Couldn't read that file: {e}")

    csv_buffer = io.StringIO()
    st.session_state.deals.to_csv(csv_buffer, index=False)
    st.download_button(
        "Download all deals as CSV",
        data=csv_buffer.getvalue(),
        file_name=f"cooper_river_deals_{date.today().isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.markdown("---")
    st.caption("Everything here saves automatically to the cloud — safe across restarts and devices.")


# --------------------------------------------------------------------------
# HEADER + KPI ROW
# --------------------------------------------------------------------------
st.markdown(
    f"""<div class="appraze-hero">
        <span class="mark">Appraze</span>
        <span class="tagline">Cooper River Trading Co. &middot; live sourcing dashboard</span>
    </div>""",
    unsafe_allow_html=True,
)
st.caption(f"Updated {datetime.now().strftime('%b %d, %Y %I:%M %p')}")

df = recalc(st.session_state.deals)

active_mask = ~df["Status"].isin(["Passed", "Sold"])
total_invested = df.loc[df["Status"] != "Passed", "Cost"].sum()
total_est_profit = df.loc[active_mask, "Gross Profit"].sum()
sold_profit = df.loc[df["Status"] == "Sold", "Gross Profit"].sum()
deal_count = int(active_mask.sum())

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Active Deals</div>
        <div class="kpi-value">{deal_count}</div></div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Total Invested</div>
        <div class="kpi-value">${total_invested:,.2f}</div></div>""", unsafe_allow_html=True)
with k3:
    cls = "kpi-sub" if total_est_profit >= 0 else "kpi-sub neg"
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Est. Profit (Active)</div>
        <div class="kpi-value">${total_est_profit:,.2f}</div>
        <div class="{cls}">{'↑ projected' if total_est_profit>=0 else '↓ projected'}</div></div>""", unsafe_allow_html=True)
with k4:
    st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Realized Profit (Sold)</div>
        <div class="kpi-value">${sold_profit:,.2f}</div></div>""", unsafe_allow_html=True)

st.write("")

# --------------------------------------------------------------------------
# TABS
# --------------------------------------------------------------------------
tab_dash, tab_inventory, tab_calc, tab_melt, tab_comps, tab_ai, tab_invoice, tab_mail, tab_pos = st.tabs(
    ["📊  Deal Dashboard", "📦  Inventory", "🧮  Profit Calculator", "⚖️  Melt Calculator", "📈  Market Comps", "🤖  AI Analyzer", "📨  Invoice Import", "✉️  Mail", "💳  POS Checkout"]
)

# ============================================================================
# TAB 1 — DEAL DASHBOARD
# ============================================================================
with tab_dash:
    st.markdown("#### Filters")
    f1, f2, f3, f4 = st.columns([1.2, 1.2, 1.2, 2])
    with f1:
        platform_filter = st.multiselect("Platform", PLATFORMS, default=[])
    with f2:
        category_filter = st.multiselect("Category", CATEGORIES, default=[])
    with f3:
        status_filter = st.multiselect("Status", STATUSES, default=[])
    with f4:
        search = st.text_input("Search item / notes", placeholder="e.g. Seiko, 14k, Bombay...")

    filtered = df.copy()
    if platform_filter:
        filtered = filtered[filtered["Platform"].isin(platform_filter)]
    if category_filter:
        filtered = filtered[filtered["Category"].isin(category_filter)]
    if status_filter:
        filtered = filtered[filtered["Status"].isin(status_filter)]
    if search:
        s = search.lower()
        filtered = filtered[
            filtered["Item"].str.lower().str.contains(s, na=False)
            | filtered["Notes"].str.lower().str.contains(s, na=False)
        ]

    st.markdown(f"#### Deals ({len(filtered)})")
    st.caption("Edit any cell directly. Add rows with the ➕ button in the sidebar, delete by selecting a row and pressing the trash icon.")

    edited = st.data_editor(
        filtered.drop(columns=["Gross Profit", "ROI %", "Verdict", "_tier"]),
        num_rows="dynamic",
        use_container_width=True,
        height=420,
        column_config={
            "Cost": st.column_config.NumberColumn(format="$%.2f"),
            "Est. Resale Value": st.column_config.NumberColumn(format="$%.2f"),
            "Platform": st.column_config.SelectboxColumn(options=PLATFORMS),
            "Category": st.column_config.SelectboxColumn(options=CATEGORIES),
            "Status": st.column_config.SelectboxColumn(options=STATUSES),
        },
        key=f"editor_{st.session_state.editor_key}",
    )

    if not edited.equals(filtered.drop(columns=["Gross Profit", "ROI %", "Verdict", "_tier"])):
        st.session_state.deals.update(edited)
        if len(edited) > len(filtered):
            extra_rows = edited.iloc[len(filtered):]
            st.session_state.deals = pd.concat([st.session_state.deals, extra_rows], ignore_index=True)
        persist()

    st.markdown("---")
    st.markdown("#### Verdicts (CRTC five-tier scale)")
    quick = recalc(edited) if len(edited) else df.iloc[0:0]
    if len(quick):
        display_cols = quick[["Item", "Platform", "Cost", "Est. Resale Value", "Gross Profit", "ROI %", "Verdict"]].copy()
        display_cols["ROI %"] = quick["ROI %"].apply(format_roi)
        st.dataframe(
            display_cols,
            use_container_width=True,
            column_config={
                "Cost": st.column_config.NumberColumn(format="$%.2f"),
                "Est. Resale Value": st.column_config.NumberColumn(format="$%.2f"),
                "Gross Profit": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
        st.caption("Strong Buy ≥60% · Buy 40–59% · At Ceiling 20–39% · Borderline 5–19% · Pass <5% (ROI, after 18% premium + 13% fees)")
    else:
        st.info("No deals match the current filters.")

# ============================================================================
# TAB — INVENTORY (BUY -> TRACK -> LIST -> SELL -> MEASURE PROFIT)
# ============================================================================
with tab_inventory:
    st.markdown("#### Inventory")
    st.caption(
        "Items you've already bought, priced against a fully-settled cost basis "
        "(buyer's premium already sunk in) rather than the pre-purchase Deal Dashboard math. "
        "Default platform fee is 13% — adjust per item if a platform charges differently."
    )

    inv_df = recalc_inventory(st.session_state.inventory)

    active_inv = inv_df[inv_df["Status"] != "Sold"]
    total_inventory_value = active_inv["List Price"].sum()
    total_capital_invested = inv_df["Cost Basis"].sum()
    priced = inv_df[inv_df["List Price"] > 0]
    avg_net_margin = priced["Net Margin %"].mean() if len(priced) else 0.0
    flagged_count = int((inv_df["Health"] == "LOW MARGIN").sum())

    i1, i2, i3, i4 = st.columns(4)
    with i1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Total Inventory Value</div>
            <div class="kpi-value">${total_inventory_value:,.2f}</div></div>""", unsafe_allow_html=True)
    with i2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Total Capital Invested</div>
            <div class="kpi-value">${total_capital_invested:,.2f}</div></div>""", unsafe_allow_html=True)
    with i3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Avg. Net Margin %</div>
            <div class="kpi-value">{avg_net_margin:,.1f}%</div></div>""", unsafe_allow_html=True)
    with i4:
        cls = "kpi-sub neg" if flagged_count else "kpi-sub"
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Flagged Items</div>
            <div class="kpi-value">{flagged_count}</div>
            <div class="{cls}">{'⚠ needs a look' if flagged_count else '✓ all healthy'}</div></div>""", unsafe_allow_html=True)

    st.write("")
    st.caption("Edit any cell directly — add rows with the ➕ button, delete by selecting a row and pressing the trash icon. Saves automatically.")

    edited_inv = st.data_editor(
        st.session_state.inventory,
        num_rows="dynamic",
        use_container_width=True,
        height=380,
        column_config={
            "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
            "List Price": st.column_config.NumberColumn(format="$%.2f"),
            "Sale Price": st.column_config.NumberColumn(format="$%.2f", help="Fill in once actually sold — used for Realized Net Profit."),
            "Platform Fee %": st.column_config.NumberColumn(format="%.1f%%"),
            "Status": st.column_config.SelectboxColumn(options=INVENTORY_STATUSES, help="Buy -> Track -> List -> Sold lifecycle"),
        },
        key=f"inventory_editor_{st.session_state.inventory_editor_key}",
    )

    if not edited_inv.equals(st.session_state.inventory):
        st.session_state.inventory = edited_inv
        persist_inventory()

    st.markdown("---")
    st.markdown("#### Margin & Health")
    display_inv = recalc_inventory(edited_inv) if len(edited_inv) else inv_df.iloc[0:0]
    if len(display_inv):
        cols = ["Item Name", "Cost Basis", "List Price", "Gross Profit", "Net Profit", "Net Margin %", "Health", "Status", "Realized Net Profit"]
        show = display_inv[cols].copy()
        show["Net Margin %"] = show["Net Margin %"].apply(lambda v: f"{v:,.1f}%")
        st.dataframe(
            show,
            use_container_width=True,
            column_config={
                "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
                "List Price": st.column_config.NumberColumn(format="$%.2f"),
                "Gross Profit": st.column_config.NumberColumn(format="$%.2f"),
                "Net Profit": st.column_config.NumberColumn(format="$%.2f"),
                "Realized Net Profit": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
        st.caption("LOW MARGIN flags anything under 20% net margin OR under $15 net profit (expected, based on List Price). Realized Net Profit only fills in once Status is Sold and a Sale Price is entered.")
    else:
        st.info("No inventory items yet — add one above.")

# ============================================================================
# TAB 2 — PROFIT CALCULATOR
# ============================================================================
with tab_calc:
    st.markdown("#### Standalone Profit Calculator")
    st.caption("Punch in a purchase cost and expected resale value to see the verdict instantly — handy for evaluating a lot in real time during a live auction.")

    cc1, cc2 = st.columns(2)
    with cc1:
        calc_cost = st.number_input("Purchase / bid cost ($)", min_value=0.0, step=1.0, format="%.2f", key="calc_cost")
    with cc2:
        calc_resale = st.number_input("Estimated resale value ($)", min_value=0.0, step=1.0, format="%.2f", key="calc_resale")

    with st.expander("Optional: factor in platform fees / buyer's premium"):
        fee_pct = st.slider("Fees as % of resale value (marketplace + payment processing)", 0.0, 30.0, DEFAULT_FEE_PCT, 0.5)
        premium_pct = st.slider("Buyer's premium at purchase (e.g. CTBids 18%)", 0.0, 25.0, DEFAULT_PREMIUM_PCT, 0.5)

    result = calc_deal(calc_cost, calc_resale, fee_pct=fee_pct, premium_pct=premium_pct)

    st.markdown("---")
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">True Cost (w/ premium)</div>
            <div class="kpi-value">${result.true_cost:,.2f}</div></div>""", unsafe_allow_html=True)
    with r2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Net Resale (after fees)</div>
            <div class="kpi-value">${result.net_resale:,.2f}</div></div>""", unsafe_allow_html=True)
    with r3:
        cls = "kpi-sub" if result.gross_profit >= 0 else "kpi-sub neg"
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Net Profit</div>
            <div class="kpi-value">${result.gross_profit:,.2f}</div>
            <div class="{cls}">{format_roi(result.roi_pct)} ROI</div></div>""", unsafe_allow_html=True)
    with r4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Verdict</div>
            <div style="margin-top:6px;">{verdict_badge_html(result.verdict, result.verdict_tier)}</div></div>""", unsafe_allow_html=True)

    st.markdown("### Split Scenarios")
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("##### 30 / 70 Split")
        st.write(f"**Partner A (30%):** ${result.gross_profit*0.30:,.2f}")
        st.write(f"**Partner B (70%):** ${result.gross_profit*0.70:,.2f}")
    with s2:
        st.markdown("##### 50 / 50 Split")
        st.write(f"**Partner A (50%):** ${result.gross_profit*0.50:,.2f}")
        st.write(f"**Partner B (50%):** ${result.gross_profit*0.50:,.2f}")

# ============================================================================
# TAB 3 — MELT CALCULATOR
# ============================================================================
with tab_melt:
    st.markdown("#### Precious Metals Melt Calculator")
    st.caption("Enforces the 80%-of-melt ceiling rule — never bid above this number on melt value alone. Get free live spot prices at xaus.com (no API key needed).")

    metal_type = st.radio("Metal", ["Gold", "Silver"], horizontal=True)

    m1, m2, m3 = st.columns(3)
    with m1:
        if metal_type == "Gold":
            purity_label = st.selectbox("Karat", list(GOLD_PURITY.keys()), index=4)  # default 14k
            purity = GOLD_PURITY[purity_label]
        else:
            purity_label = st.selectbox("Purity", list(SILVER_PURITY.keys()), index=1)  # default sterling
            purity = SILVER_PURITY[purity_label]
    with m2:
        weight_grams = st.number_input("Weight (grams)", min_value=0.0, step=0.1, format="%.2f")
    with m3:
        spot_price = st.number_input(
            f"Spot price ($/troy oz) — {metal_type.lower()}",
            min_value=0.0, step=1.0, format="%.2f",
            help="Check xaus.com for a free, no-API-key spot price."
        )

    melt = calc_melt(weight_grams, purity, spot_price)

    st.markdown("---")
    st.markdown(
        f'<div class="ceiling-banner">⚠️ 80% CEILING RULE — Never pay/bid above '
        f'<strong>${melt.ceiling_price:,.2f}</strong> for this item based on melt value alone.</div>',
        unsafe_allow_html=True,
    )

    n1, n2, n3 = st.columns(3)
    with n1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Pure Content</div>
            <div class="kpi-value">{melt.pure_troy_oz:.3f} oz t</div></div>""", unsafe_allow_html=True)
    with n2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Full Melt Value</div>
            <div class="kpi-value">${melt.melt_value:,.2f}</div></div>""", unsafe_allow_html=True)
    with n3:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Ceiling Price ({MELT_CEILING_PCT:.0f}%)</div>
            <div class="kpi-value">${melt.ceiling_price:,.2f}</div></div>""", unsafe_allow_html=True)

    if weight_grams > 0 and spot_price > 0:
        st.markdown("---")
        st.markdown("##### ➕ Send to Dashboard")
        st.caption("Pushes this straight into your Deal Dashboard — no retyping.")
        h1, h2 = st.columns([2, 1])
        with h1:
            melt_item_name = st.text_input(
                "Item name", value=f"{purity_label} {metal_type} — {weight_grams:g}g",
                key="melt_item_name",
            )
        with h2:
            melt_cost = st.number_input("Your actual cost ($)", min_value=0.0, value=round(melt.ceiling_price, 2), step=1.0, format="%.2f", key="melt_cost_input")
        if st.button("➕ Add to Dashboard", key="melt_send", use_container_width=True):
            add_deal_row(
                item=melt_item_name,
                platform="CTBids",
                category="Gold/Silver Jewelry",
                cost=melt_cost,
                resale=melt.melt_value,
                status="Watching",
                notes=f"{purity_label} · {weight_grams:g}g · spot ${spot_price:,.2f}/oz · 80% ceiling ${melt.ceiling_price:,.2f}",
            )
            st.success(f"Added \"{melt_item_name}\" to the Dashboard.")

# ============================================================================
# TAB — MARKET COMPS (real evidence, not a guess)
# ============================================================================
with tab_comps:
    st.markdown("#### Market Comps")
    st.caption(
        "Turns actual comparable listings — sold prices you look up yourself, an eBay search, or a "
        "pasted CSV export — into a resale-value estimate with an honest confidence rating, then runs "
        "it through the same five-tier verdict math as everywhere else. Sold comps are real evidence of "
        "what buyers paid; active/asking-price listings are weaker evidence and are scored accordingly."
    )

    if "comps_rows" not in st.session_state:
        st.session_state.comps_rows = []

    with st.expander("🔎 Pull active listings from eBay (optional)"):
        if not is_ebay_configured():
            st.info("Not configured — set `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` in Streamlit secrets to enable this. You can still add comps manually below without it.")
        else:
            eq1, eq2 = st.columns([3, 1])
            with eq1:
                ebay_query = st.text_input("Search eBay for", placeholder="e.g. 14k gold rope chain 22 inch", key="ebay_query")
            with eq2:
                st.write("")
                ebay_search_clicked = st.button("Search", key="ebay_search", use_container_width=True)
            st.caption("eBay's Browse API only returns *active* (asking-price) listings — not sold comps — so results here are weaker evidence than a sold price you look up yourself.")
            if ebay_search_clicked and ebay_query.strip():
                with st.spinner("Searching eBay..."):
                    try:
                        found = EbayBrowseAdapter().fetch_comps(ebay_query, limit=20)
                        for c in found:
                            st.session_state.comps_rows.append({
                                "Price": c.price, "Shipping": c.shipping, "Source": c.source,
                                "Listing Type": c.listing_type, "Condition": c.condition,
                                "Date": c.listing_date or "", "Title/Notes": c.title,
                            })
                        st.success(f"Added {len(found)} active listing(s) from eBay.")
                    except EbayAuthError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"eBay search failed: {e}")

    with st.expander("📄 Import comps from a CSV"):
        st.caption("Columns: price (required), source, listing_type (sold/active), condition, shipping, listing_date, title, url")
        comps_csv = st.file_uploader("Upload CSV", type=["csv"], key="comps_csv")
        if comps_csv is not None and st.button("Import rows", key="comps_csv_import"):
            try:
                imported = CsvCompsAdapter(csv_bytes=comps_csv.getvalue()).fetch_comps(limit=200)
                for c in imported:
                    st.session_state.comps_rows.append({
                        "Price": c.price, "Shipping": c.shipping, "Source": c.source,
                        "Listing Type": c.listing_type, "Condition": c.condition,
                        "Date": c.listing_date or "", "Title/Notes": c.title,
                    })
                st.success(f"Imported {len(imported)} comp(s).")
            except Exception as e:
                st.error(f"Couldn't read that CSV: {e}")

    st.markdown("##### Comps")
    st.caption("Add rows by hand for sold listings you've looked up yourself (CTBids, HiBid, eBay sold filter, Facebook Marketplace, etc.) — the most reliable evidence available without a paid data feed.")
    comps_df = pd.DataFrame(st.session_state.comps_rows) if st.session_state.comps_rows else pd.DataFrame(
        columns=["Price", "Shipping", "Source", "Listing Type", "Condition", "Date", "Title/Notes"]
    )
    edited_comps = st.data_editor(
        comps_df,
        num_rows="dynamic",
        use_container_width=True,
        height=260,
        column_config={
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "Shipping": st.column_config.NumberColumn(format="$%.2f"),
            "Listing Type": st.column_config.SelectboxColumn(options=["sold", "active"]),
        },
        key="comps_editor",
    )
    st.session_state.comps_rows = edited_comps.to_dict("records")

    comps_list = [
        Comp(
            price=float(r["Price"]) if pd.notna(r.get("Price")) else 0.0,
            shipping=float(r["Shipping"]) if pd.notna(r.get("Shipping")) else 0.0,
            source=r.get("Source") or "Manual",
            listing_type=(r.get("Listing Type") or "sold").lower(),
            condition=r.get("Condition") or "",
            listing_date=r.get("Date") or None,
            title=r.get("Title/Notes") or "",
        )
        for r in st.session_state.comps_rows
        if pd.notna(r.get("Price")) and float(r.get("Price") or 0) > 0
    ]

    st.markdown("---")
    st.markdown("##### Verdict")
    vc1, vc2 = st.columns(2)
    with vc1:
        comps_cost = st.number_input("Your cost / planned bid ($)", min_value=0.0, step=1.0, format="%.2f", key="comps_cost")
    with vc2:
        with st.expander("Fees / premium"):
            comps_fee_pct = st.slider("Platform fee %", 0.0, 30.0, DEFAULT_FEE_PCT, 0.5, key="comps_fee")
            comps_premium_pct = st.slider("Buyer's premium %", 0.0, 25.0, DEFAULT_PREMIUM_PCT, 0.5, key="comps_premium")

    if not comps_list:
        st.info("Add at least one comp above to get a verdict.")
    else:
        market_verdict = evaluate_with_comps(comps_list, comps_cost, fee_pct=comps_fee_pct, premium_pct=comps_premium_pct)
        summary = market_verdict.comps_summary
        deal = market_verdict.deal

        confidence_badge = {"high": "badge-buy", "medium": "badge-at_ceiling", "low": "badge-pass"}[summary.confidence]
        w1, w2, w3, w4 = st.columns(4)
        with w1:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Suggested Value</div>
                <div class="kpi-value">${summary.suggested_value:,.2f}</div></div>""", unsafe_allow_html=True)
        with w2:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Range (low–high)</div>
                <div class="kpi-value">${summary.low:,.0f}–${summary.high:,.0f}</div></div>""", unsafe_allow_html=True)
        with w3:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Comps Used</div>
                <div class="kpi-value">{summary.count}</div>
                <div class="kpi-sub">{summary.sold_count} sold · {summary.active_count} active</div></div>""", unsafe_allow_html=True)
        with w4:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Confidence</div>
                <div style="margin-top:6px;">{verdict_badge_html(summary.confidence.upper(), confidence_badge)}</div></div>""", unsafe_allow_html=True)
        st.caption(summary.confidence_reason)

        st.markdown("---")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Net Profit</div>
                <div class="kpi-value">${deal.gross_profit:,.2f}</div>
                <div class="{'kpi-sub' if deal.gross_profit >= 0 else 'kpi-sub neg'}">{format_roi(deal.roi_pct)} ROI</div></div>""", unsafe_allow_html=True)
        with r2:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Verdict</div>
                <div style="margin-top:6px;">{verdict_badge_html(deal.verdict, deal.verdict_tier)}</div></div>""", unsafe_allow_html=True)
        with r3:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Floor Cost (Buy tier, 40%)</div>
                <div class="kpi-value">${market_verdict.floor_cost:,.2f}</div></div>""", unsafe_allow_html=True)

        st.markdown("##### ➕ Send to Dashboard")
        comps_platform = st.selectbox("Platform for this deal", PLATFORMS, key="comps_send_platform")
        comps_item_name = st.text_input("Item name", key="comps_item_name")
        if st.button("➕ Add to Dashboard", key="comps_send", use_container_width=True):
            if not comps_item_name.strip():
                st.warning("Give the item a name first.")
            else:
                add_deal_row(
                    item=comps_item_name,
                    platform=comps_platform,
                    category="Other",
                    cost=comps_cost,
                    resale=summary.suggested_value,
                    status="Watching",
                    notes=(
                        f"Market comps: {summary.count} ({summary.sold_count} sold, {summary.active_count} active), "
                        f"confidence {summary.confidence} — {summary.confidence_reason}"
                    ),
                )
                st.success(f"Added \"{comps_item_name}\" to the Dashboard.")

# ============================================================================
# TAB 4 — AI ANALYZER
# ============================================================================
with tab_ai:
    st.markdown("#### AI Item Analyzer")
    st.caption(
        "Upload a photo and/or description. The AI identifies the item and estimates a resale value range — "
        "it does NOT decide buy/pass on its own. Your cost and CRTC's deterministic math produce the final verdict."
    )

    ai_col1, ai_col2 = st.columns([1, 1])
    with ai_col1:
        photo = st.file_uploader("Photo (optional)", type=["jpg", "jpeg", "png", "webp"], key="ai_photo")
        if photo is not None:
            st.image(photo, use_container_width=True)
    with ai_col2:
        description = st.text_area(
            "Description / context (optional but recommended)",
            placeholder="e.g. Marked 14k on clasp, ~22 inches, minor tarnish, found at estate sale",
            height=120,
        )
        purchase_cost = st.number_input("Your cost / planned bid ($)", min_value=0.0, step=1.0, format="%.2f", key="ai_cost")
        ai_fee_pct = st.slider("Platform fee %", 0.0, 30.0, DEFAULT_FEE_PCT, 0.5, key="ai_fee")
        ai_premium_pct = st.slider("Buyer's premium %", 0.0, 25.0, DEFAULT_PREMIUM_PCT, 0.5, key="ai_premium")

    analyze_clicked = st.button("🔍 Analyze Item", use_container_width=True, type="primary")

    def call_claude_vision(image_bytes: Optional[bytes], media_type: Optional[str], desc: str) -> dict:
        """
        Calls the Anthropic Messages API directly via requests (no SDK dependency).
        Returns a parsed dict: {item_name, category, estimated_low, estimated_high, confidence, notes}
        Raises on any failure — caller handles user-facing error display.
        """
        api_key = st.secrets.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in Streamlit secrets.")

        content = []
        if image_bytes is not None:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            })

        prompt_text = (
            "You are an expert resale/estate-sale appraiser AND a marketplace listing copywriter. "
            "Identify this item and estimate its REALISTIC current resale value range (not "
            "retail/replacement value) based on recent comparable sold listings you're aware of. "
            "Be conservative — CRTC would rather underestimate than overestimate. Then draft a "
            "ready-to-post listing for eBay, Poshmark, Mercari, and Facebook Marketplace — each "
            "platform's title and description should match how sellers actually write on that "
            "platform (eBay: keyword-rich, structured, under 80 characters; Poshmark/Mercari: "
            "casual, under 60 characters; Facebook Marketplace: brief and local-sale toned). Each "
            "description should be 2-4 sentences, honest about condition, and ready to paste in "
            "with no editing needed.\n\n"
            f"Additional context from the seller: {desc if desc.strip() else '(none provided)'}\n\n"
            "Respond with ONLY a raw JSON object, no markdown fences, no preamble, in exactly this shape:\n"
            '{"item_name": "...", "category": "...", "estimated_low": 0, "estimated_high": 0, '
            '"confidence": "low|medium|high", "notes": "1-2 sentences on identifying features or risk factors", '
            '"listing_drafts": {"ebay": {"title": "...", "description": "..."}, '
            '"poshmark": {"title": "...", "description": "..."}, '
            '"mercari": {"title": "...", "description": "..."}, '
            '"facebook": {"title": "...", "description": "..."}}}'
        )
        content.append({"type": "text", "text": prompt_text})

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-5",
                # Was 500 - too tight once listing drafts for four platforms were
                # added on top of the identification/value fields; that combined
                # response routinely got cut off mid-JSON at the old limit.
                "max_tokens": 1400,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()

        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        raw_text = "\n".join(text_blocks).strip()
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(raw_text)

    if analyze_clicked:
        if photo is None and not description.strip():
            st.warning("Add a photo or a description first — the AI needs something to look at.")
        else:
            with st.spinner("Analyzing item..."):
                try:
                    img_bytes, media_type = None, None
                    if photo is not None:
                        img_bytes = photo.getvalue()
                        media_type = photo.type or "image/jpeg"
                    ai_result = call_claude_vision(img_bytes, media_type, description)
                    st.session_state["ai_last_result"] = ai_result
                except requests.exceptions.HTTPError as e:
                    st.error(f"AI request failed: {e.response.status_code} — check your ANTHROPIC_API_KEY in secrets.")
                except json.JSONDecodeError:
                    st.error("The AI didn't return valid JSON. Try again, or add more description and retry.")
                except Exception as e:
                    st.error(f"Something went wrong: {e}")

    ai_result = st.session_state.get("ai_last_result")
    if ai_result:
        st.markdown("---")
        st.markdown(f"### {ai_result.get('item_name', 'Unknown Item')}")
        conf = ai_result.get("confidence", "medium")
        st.caption(f"Category: {ai_result.get('category', '—')} · AI confidence: {conf}")
        if ai_result.get("notes"):
            st.info(ai_result["notes"])

        st.markdown("##### 📊 Real eBay Comps")
        if not is_ebay_configured():
            st.caption("Not configured — set `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` in Streamlit secrets to pull real eBay data here instead of relying on the AI's estimate alone.")
        else:
            cq1, cq2 = st.columns([3, 1])
            with cq1:
                comp_query = st.text_input(
                    "Search eBay for", value=ai_result.get("item_name", ""), key="ai_comp_query",
                    label_visibility="collapsed", placeholder="Search terms for eBay comps",
                )
            with cq2:
                pull_clicked = st.button("Pull Comps", key="ai_pull_comps", use_container_width=True)

            if pull_clicked and comp_query.strip():
                with st.spinner("Checking eBay..."):
                    sold_mode = False
                    comps_found = []
                    fetch_error = None
                    try:
                        comps_found = EbayMarketplaceInsightsAdapter().fetch_comps(comp_query, limit=20)
                        sold_mode = True
                    except EbayInsightsNotApprovedError:
                        # Expected on almost every account - eBay's Marketplace
                        # Insights API is a Limited Release most individual
                        # developers never get approved for (see comps_adapters.py).
                        # Fall back to active listings rather than failing.
                        try:
                            comps_found = EbayBrowseAdapter().fetch_comps(comp_query, limit=20)
                            sold_mode = False
                        except Exception as e:
                            fetch_error = str(e)
                    except EbayAuthError as e:
                        fetch_error = str(e)
                    except Exception as e:
                        fetch_error = f"eBay search failed: {e}"
                    st.session_state["ai_comps_result"] = {"comps": comps_found, "sold_mode": sold_mode, "error": fetch_error, "query": comp_query}

            comps_result = st.session_state.get("ai_comps_result")
            if comps_result:
                if comps_result["error"]:
                    st.error(comps_result["error"])
                elif not comps_result["comps"]:
                    st.info(f"No eBay results for \"{comps_result['query']}\" — try different/fewer keywords.")
                else:
                    comps_summary = summarize_comps(comps_result["comps"])
                    if comps_result["sold_mode"]:
                        st.success(f"✅ {comps_summary.sold_count} confirmed SOLD comp(s) from eBay (last 90 days).")
                    else:
                        st.warning(f"⚠️ Showing {len(comps_result['comps'])} ACTIVE listing(s) — asking prices, not confirmed sold prices. Marketplace Insights (real sold data) isn't approved for this app yet.")
                    cc1, cc2, cc3 = st.columns(3)
                    with cc1:
                        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Median (eBay)</div>
                            <div class="kpi-value">${comps_summary.median:,.2f}</div></div>""", unsafe_allow_html=True)
                    with cc2:
                        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Range</div>
                            <div class="kpi-value">${comps_summary.low:,.0f}–${comps_summary.high:,.0f}</div></div>""", unsafe_allow_html=True)
                    with cc3:
                        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Listings Found</div>
                            <div class="kpi-value">{comps_summary.count}</div></div>""", unsafe_allow_html=True)
                    st.caption("This is separate, independent evidence from the AI's estimate above — a real median from actual eBay listings, not another AI guess. If the two disagree by a lot, trust this number over the AI's.")

        st.markdown("---")
        est_low = float(ai_result.get("estimated_low", 0) or 0)
        est_high = float(ai_result.get("estimated_high", 0) or 0)
        est_mid = (est_low + est_high) / 2
        floor_cost = max_cost_for_target_roi(est_mid, target_roi_pct=40.0, fee_pct=ai_fee_pct, premium_pct=ai_premium_pct)

        v1, v2, v3, v4 = st.columns(4)
        with v1:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Est. Value Range</div>
                <div class="kpi-value">${est_low:,.0f}–${est_high:,.0f}</div></div>""", unsafe_allow_html=True)
        with v4:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Floor Cost (Buy tier, 40%)</div>
                <div class="kpi-value">${floor_cost:,.2f}</div></div>""", unsafe_allow_html=True)

        if purchase_cost > 0:
            deal = calc_deal(purchase_cost, est_mid, fee_pct=ai_fee_pct, premium_pct=ai_premium_pct)
            with v2:
                cls = "kpi-sub" if deal.gross_profit >= 0 else "kpi-sub neg"
                st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Est. Profit (using midpoint)</div>
                    <div class="kpi-value">${deal.gross_profit:,.2f}</div>
                    <div class="{cls}">{format_roi(deal.roi_pct)} ROI</div></div>""", unsafe_allow_html=True)
            with v3:
                st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Verdict</div>
                    <div style="margin-top:6px;">{verdict_badge_html(deal.verdict, deal.verdict_tier)}</div></div>""", unsafe_allow_html=True)
            st.caption("Verdict computed deterministically from your cost + AI's midpoint estimate — using CRTC's five-tier ROI scale, not an AI opinion. Floor cost is the max you could pay and still hit the Buy tier (40% ROI).")

            st.markdown("##### ➕ Send to Dashboard")
            ai_platform = st.selectbox("Platform for this deal", PLATFORMS, key="ai_send_platform")
            if st.button("➕ Add to Dashboard", key="ai_send", use_container_width=True):
                notes_bits = [ai_result.get("notes", "")]
                notes_bits.append(f"AI confidence: {conf}")
                add_deal_row(
                    item=ai_result.get("item_name", "Unnamed item"),
                    platform=ai_platform,
                    category=ai_result.get("category", "Other") if ai_result.get("category") in CATEGORIES else "Other",
                    cost=purchase_cost,
                    resale=est_mid,
                    status="Watching",
                    notes=" · ".join(b for b in notes_bits if b),
                )
                st.success(f"Added \"{ai_result.get('item_name', 'item')}\" to the Dashboard.")
        else:
            with v2:
                st.markdown("""<div class="kpi-card"><div class="kpi-label">Est. Profit</div>
                    <div class="kpi-value" style="color:#8b96a5;">Enter cost above</div></div>""", unsafe_allow_html=True)
            st.caption(f"Enter your cost/planned bid above to get a verdict — or bid up to the ${floor_cost:,.2f} floor cost to guarantee at least a Buy-tier deal.")

        listing_drafts = ai_result.get("listing_drafts")
        if isinstance(listing_drafts, dict) and listing_drafts:
            st.markdown("---")
            st.markdown("##### 📋 Ready-to-post listings")
            st.caption("Drafted from the same analysis above — click the copy icon in a box, then paste straight into that marketplace's app.")
            platform_labels = {"ebay": "eBay", "poshmark": "Poshmark", "mercari": "Mercari", "facebook": "Facebook Marketplace"}
            draft_tabs = st.tabs([platform_labels.get(k, k.title()) for k in listing_drafts.keys()])
            for draft_tab, (plat_key, draft) in zip(draft_tabs, listing_drafts.items()):
                with draft_tab:
                    if not isinstance(draft, dict) or not (draft.get("title") or draft.get("description")):
                        st.caption("No draft returned for this platform — try analyzing again.")
                        continue
                    if draft.get("title"):
                        st.caption("Title")
                        st.code(draft["title"], language=None)
                    if draft.get("description"):
                        st.caption("Description")
                        st.code(draft["description"], language=None)

# ============================================================================
# TAB 5 — INVOICE IMPORT
# ============================================================================
with tab_invoice:
    st.markdown("#### Invoice / Receipt Import")
    st.caption(
        "Extracts line items from invoices and estimates resale value + recommended pricing for each — "
        "using your actual cost, not a guess."
    )

    def _file_content_block(file_bytes: bytes, mime_type: str) -> dict:
        """Anthropic's API wants PDFs as 'document' blocks and everything else as 'image' blocks."""
        b64 = base64.b64encode(file_bytes).decode("utf-8")
        block_type = "document" if mime_type == "application/pdf" else "image"
        return {"type": block_type, "source": {"type": "base64", "media_type": mime_type, "data": b64}}

    def call_claude_invoice_parser(image_bytes: Optional[bytes], media_type: Optional[str], text: str) -> list:
        """
        Extracts line items from invoice text/image/PDF and gets a resale estimate
        for each — same direct-API pattern as call_claude_vision, kept separate
        because the response shape (a list of items) is different. Handles both
        manually uploaded photos and files pulled from a scanned Drive folder.
        """
        api_key = st.secrets.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in Streamlit secrets.")

        content = []
        if image_bytes is not None:
            content.append(_file_content_block(image_bytes, media_type or "image/jpeg"))

        prompt_text = (
            "You are an expert resale/estate-sale appraiser reading a purchase invoice or receipt. "
            "Extract EVERY distinct line item purchased, with what was actually paid for it. If only a lot "
            "total is given with no per-item breakdown, return it as a single item. For each item, also "
            "estimate a REALISTIC current resale value range (conservative, not retail/replacement value).\n\n"
            f"Invoice/receipt text: {text if text.strip() else '(see attached image)'}\n\n"
            "Respond with ONLY a raw JSON array, no markdown fences, no preamble, in exactly this shape:\n"
            '[{"item_name": "...", "cost_paid": 0, "category": "...", "estimated_low": 0, '
            '"estimated_high": 0, "confidence": "low|medium|high"}]'
        )
        content.append({"type": "text", "text": prompt_text})

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-5",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()

        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        raw_text = "\n".join(text_blocks).strip()
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        return json.loads(raw_text)

    st.markdown("##### 🔄 Scan a Drive folder")
    st.caption(
        "Reads new image/PDF files sitting in a named Google Drive folder — no Gmail connection, "
        "no separate credentials. Each file is only ever processed once."
    )
    drive_col1, drive_col2 = st.columns([2, 1])
    with drive_col1:
        folder_name = st.text_input(
            "Exact Drive folder name",
            value=st.session_state.get("invoice_folder_name", "Invoices"),
            key="invoice_folder_name",
            help="Must match the folder name exactly, including capitalization. Point this at your Invoices or Inventory folder.",
        )
    with drive_col2:
        st.write("")  # vertical alignment spacer
        scan_folder_clicked = st.button("🔄 Scan Now", use_container_width=True)

    if scan_folder_clicked:
        with st.spinner(f'Scanning Drive folder "{folder_name}"...'):
            scan_result = scan_invoice_folder(folder_name)
        if not scan_result.success:
            st.error(scan_result.error)
        elif not scan_result.files:
            st.info("No new files found — everything in that folder has already been processed, or it's empty.")
        else:
            with st.spinner(f"Reading {len(scan_result.files)} file(s) and estimating resale values..."):
                all_items = []
                scanned_ids, scanned_names = [], []
                for f in scan_result.files:
                    try:
                        file_bytes = base64.b64decode(f["base64"])
                        items = call_claude_invoice_parser(file_bytes, f["mime_type"], "")
                        for it in items:
                            it["_source_file"] = f["file_name"]
                        all_items.extend(items)
                    except Exception as e:
                        st.warning(f"Couldn't read \"{f['file_name']}\": {e}")
                    scanned_ids.append(f["file_id"])
                    scanned_names.append(f["file_name"])

                # Mark processed regardless of per-item outcome — the file has
                # been read; re-scanning it again won't produce anything new.
                mark_files_processed(scanned_ids, scanned_names)

            if all_items:
                st.session_state["invoice_items"] = all_items
                st.success(f"Extracted {len(all_items)} item(s) from {len(scan_result.files)} file(s). Review below.")
            else:
                st.warning("Files were found and marked as read, but no line items could be extracted from them.")

    st.markdown("---")
    st.markdown("##### 📋 Or paste / upload manually")

    inv_col1, inv_col2 = st.columns([1, 1])
    with inv_col1:
        invoice_photo = st.file_uploader("Invoice photo / screenshot (optional)", type=["jpg", "jpeg", "png", "webp"], key="invoice_photo")
        if invoice_photo is not None:
            st.image(invoice_photo, use_container_width=True)
    with inv_col2:
        invoice_text = st.text_area(
            "Or paste the invoice/email text",
            placeholder="Paste the body of a CTBids/eBay purchase confirmation, or any receipt text...",
            height=160,
        )
        inv_fee_pct = st.slider("Platform fee % (for recommendations)", 0.0, 30.0, DEFAULT_FEE_PCT, 0.5, key="inv_fee")
        inv_premium_pct = st.slider("Buyer's premium % already included in invoice?", 0.0, 25.0, 0.0, 0.5, key="inv_premium",
                                     help="Leave at 0 if the invoice total already includes the premium (most CTBids invoices do). Only raise this if your invoice shows pre-premium hammer prices.")

    scan_clicked = st.button("📨 Extract Line Items", use_container_width=True, type="primary")

    if scan_clicked:
        if invoice_photo is None and not invoice_text.strip():
            st.warning("Paste some invoice text or upload a photo first.")
        else:
            with st.spinner("Reading invoice and estimating resale values..."):
                try:
                    img_bytes, media_type = None, None
                    if invoice_photo is not None:
                        img_bytes = invoice_photo.getvalue()
                        media_type = invoice_photo.type or "image/jpeg"
                    items = call_claude_invoice_parser(img_bytes, media_type, invoice_text)
                    st.session_state["invoice_items"] = items
                except requests.exceptions.HTTPError as e:
                    st.error(f"AI request failed: {e.response.status_code} — check your ANTHROPIC_API_KEY in secrets.")
                except json.JSONDecodeError:
                    st.error("The AI didn't return valid JSON. Try again with clearer invoice text.")
                except Exception as e:
                    st.error(f"Something went wrong: {e}")

    invoice_items = st.session_state.get("invoice_items")
    if invoice_items:
        st.markdown("---")
        st.markdown(f"#### {len(invoice_items)} item(s) found")

        rows = []
        for it in invoice_items:
            cost = float(it.get("cost_paid", 0) or 0)
            est_low = float(it.get("estimated_low", 0) or 0)
            est_high = float(it.get("estimated_high", 0) or 0)
            est_mid = (est_low + est_high) / 2
            deal = calc_deal(cost, est_mid, fee_pct=inv_fee_pct, premium_pct=inv_premium_pct)
            rows.append({
                "Include": True,
                "Item": it.get("item_name", "Unnamed item"),
                "Category": it.get("category", "Other") if it.get("category") in CATEGORIES else "Other",
                "Cost Paid": cost,
                "Target Price": round(est_high, 2),
                "Est. Resale (mid)": round(est_mid, 2),
                "Verdict": deal.verdict,
                "Source": it.get("_source_file", "manual entry"),
            })

        review_df = pd.DataFrame(rows)
        edited_invoice = st.data_editor(
            review_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Include": st.column_config.CheckboxColumn(),
                "Cost Paid": st.column_config.NumberColumn(format="$%.2f"),
                "Target Price": st.column_config.NumberColumn(format="$%.2f", help="Suggested listing price — top of AI's estimated range"),
                "Est. Resale (mid)": st.column_config.NumberColumn(format="$%.2f"),
                "Category": st.column_config.SelectboxColumn(options=CATEGORIES),
            },
            key="invoice_review_editor",
        )
        st.caption("Target Price = top of AI's estimated resale range. Verdict uses your actual invoice cost + the midpoint estimate, via the same five-tier scale as everywhere else. Uncheck any item (sales tax lines, shipping, etc.) before adding.")

        invoice_platform = st.selectbox("Platform to log these under", PLATFORMS, key="invoice_platform")
        if st.button("➕ Add checked items to Dashboard", use_container_width=True, type="primary"):
            added = 0
            for _, r in edited_invoice.iterrows():
                if r["Include"]:
                    add_deal_row(
                        item=r["Item"],
                        platform=invoice_platform,
                        category=r["Category"],
                        cost=r["Cost Paid"],
                        resale=r["Est. Resale (mid)"],
                        status="Won/Purchased",
                        notes=f"Imported from invoice · target list price ${r['Target Price']:,.2f}",
                    )
                    added += 1
            if added:
                st.success(f"Added {added} item(s) to the Dashboard.")
                st.session_state.pop("invoice_items", None)
            else:
                st.warning("Nothing was checked — nothing added.")

# ============================================================================
# TAB — MAIL (read-only Gmail tracking of supplier invoices/shipments)
# ============================================================================
with tab_mail:
    st.markdown("#### Mail")
    st.caption(
        "Read-only scan of the connected inbox's recent messages — flags anything that looks like a "
        "shipment tracking number or a supplier invoice. Nothing is ever sent, replied to, deleted, "
        "or modified."
    )

    if not mail.is_configured():
        st.info(
            "Not connected yet. Set `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` in Streamlit secrets to "
            "turn this on — see DEPLOY.md for the one-time Gmail App Password setup."
        )
    else:
        mc1, mc2 = st.columns([1, 3])
        with mc1:
            mail_days = st.slider("Look back (days)", 1, 30, 14, key="mail_days")
        with mc2:
            st.write("")
            if st.button("🔄 Refresh inbox", key="mail_refresh"):
                mail.fetch_recent_messages.clear()

        with st.spinner("Checking inbox..."):
            messages = mail.fetch_recent_messages(days=mail_days)

        if messages is None:
            st.error("Couldn't connect to the inbox — check GMAIL_ADDRESS/GMAIL_APP_PASSWORD and that IMAP is enabled.")
        elif not messages:
            st.info(f"No messages in the last {mail_days} day(s).")
        else:
            mail_df = pd.DataFrame(messages)
            mf1, mf2 = st.columns(2)
            with mf1:
                mail_category_filter = st.multiselect("Category", ["Tracking", "Invoice", "Other"], key="mail_cat_filter")
            with mf2:
                mail_search = st.text_input("Search subject / sender", key="mail_search")

            filtered_mail = mail_df.copy()
            if mail_category_filter:
                filtered_mail = filtered_mail[filtered_mail["Category"].isin(mail_category_filter)]
            if mail_search:
                s = mail_search.lower()
                filtered_mail = filtered_mail[
                    filtered_mail["Subject"].str.lower().str.contains(s, na=False)
                    | filtered_mail["From"].str.lower().str.contains(s, na=False)
                ]

            st.markdown(f"#### {len(filtered_mail)} message(s)")
            st.dataframe(
                filtered_mail[["Date", "From", "Subject", "Category", "Carrier", "Tracking #", "Invoice/Order Ref", "Amount"]],
                use_container_width=True,
                column_config={"Amount": st.column_config.NumberColumn(format="$%.2f")},
            )

# ============================================================================
# TAB 6 — POS CHECKOUT
# ============================================================================
with tab_pos:
    st.markdown("#### Point-of-Sale Checkout")
    st.caption(
        "Charge a real customer for a real item — they enter their own card on Stripe's hosted page, "
        "this app never sees or stores card data. Works for a shared-device tap-and-pay handoff or a "
        "link you text/send remotely."
    )

    if not st.session_state.get("user_is_admin"):
        st.info("Point-of-Sale is for Cooper River Trading Co. admins only — it charges real customers and shows the shop's full sales history, not something a beta tester account should see or touch.")
    else:
        if "sales_log_loaded" not in st.session_state:
            with st.spinner("Loading pending checkouts..."):
                sales_result = load_table("sales_log", shared=True)
            st.session_state.sales_log = sales_result.payload if (sales_result.success and sales_result.payload) else []
            st.session_state.sales_log_loaded = True

        def persist_sales_log():
            """Pending checkouts used to live only in st.session_state, so a page
            refresh silently lost them even though the Stripe session was still
            valid. Persisting through the same backend as Deals/Inventory fixes
            that, and lets the standalone webhook service (stripe_webhook_server.py)
            reconcile a sale automatically without this tab even being open.

            shared=True always targets the fixed "admin_shared" row (matching
            pos.py's SALES_LOG_OWNER_KEY and webhook_store.py's OWNER_KEY) —
            POS is one shared cash register for the business, not per-tester
            data. Without it, a non-admin login's checkouts would land under
            their own private row, where the webhook service could never find
            them to reconcile."""
            save_table(pd.DataFrame(st.session_state.sales_log), "sales_log", shared=True)

        if st.button("🔄 Refresh (picks up webhook-confirmed payments)", use_container_width=False):
            refreshed = load_table("sales_log", shared=True)
            if refreshed.success:
                st.session_state.sales_log = refreshed.payload or []
                st.rerun()
            else:
                st.warning(f"Couldn't refresh: {refreshed.error}")

        pos_mode = st.radio(
            "How do you want to set the amount?",
            ["Custom amount", "Pull from a Dashboard deal"],
            horizontal=True,
        )

        pos_description, pos_amount, pos_deal_index = "", 0.0, None

        if pos_mode == "Custom amount":
            pc1, pc2 = st.columns(2)
            with pc1:
                pos_description = st.text_input("What are they buying?", key="pos_custom_desc")
            with pc2:
                pos_amount = st.number_input("Sale amount ($)", min_value=0.0, step=1.0, format="%.2f", key="pos_custom_amount")
        else:
            sellable = df[df["Status"] != "Sold"].reset_index()  # keep original df index in a column for lookup
            if sellable.empty:
                st.info("No unsold deals in the Dashboard yet — add one first, or use Custom amount above.")
            else:
                options = {f'{r["Item"]} — ${r["Est. Resale Value"]:,.2f} ({r["Platform"]})': r["index"] for _, r in sellable.iterrows()}
                choice = st.selectbox("Which deal is this?", list(options.keys()))
                pos_deal_index = options[choice]
                chosen_row = df.loc[pos_deal_index]
                pos_description = st.text_input("Description", value=chosen_row["Item"], key="pos_deal_desc")
                pos_amount = st.number_input(
                    "Sale amount ($)", min_value=0.0, step=1.0, format="%.2f",
                    value=float(chosen_row["Est. Resale Value"]), key="pos_deal_amount",
                )

        pos_email = st.text_input("Customer email (optional — for their receipt)", key="pos_email")

        if st.button("💳 Generate Checkout Link", use_container_width=True, type="primary"):
            if not pos_description.strip() or pos_amount <= 0:
                st.warning("Add a description and an amount greater than $0.")
            else:
                result = create_pos_checkout(pos_amount, pos_description, pos_email)
                if result.success:
                    st.session_state.sales_log.append({
                        "Invoice #": result.invoice_id,
                        "session_id": result.session_id,
                        "description": pos_description,
                        "amount": pos_amount,
                        "deal_index": pos_deal_index,
                        "checkout_url": result.checkout_url,
                        "Status": "Awaiting Payment",
                    })
                    persist_sales_log()
                    st.success(f"Checkout link ready ({result.invoice_id}) — hand off the device, or copy the link below.")
                else:
                    st.error(result.error)

        pending = [tx for tx in st.session_state.sales_log if tx.get("Status") != "Paid (Card)"]
        if pending:
            st.markdown("---")
            st.markdown("##### Pending checkouts")
            st.caption(
                "Click Check Status after the customer pays, or hit Refresh above if the Stripe webhook "
                "service (see DEPLOY.md) already confirmed it automatically — works whether they paid on "
                "this device or their own."
            )

            changed = False
            for tx in pending:
                with st.container():
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.markdown(f"**{tx['description']}** — ${tx['amount']:,.2f}")
                        st.caption(f"{tx.get('Invoice #', '')} · {tx['checkout_url']}")
                    with c2:
                        st.link_button("Open", tx["checkout_url"], use_container_width=True)
                    with c3:
                        check_clicked = st.button("✅ Check Status", key=f"check_{tx['session_id']}", use_container_width=True)

                    if check_clicked:
                        if check_payment_status(tx["session_id"]):
                            st.success(f"Paid! ${tx['amount']:,.2f} confirmed.")
                            tx["Status"] = "Paid (Card)"
                            changed = True
                            if tx["deal_index"] is not None and tx["deal_index"] in st.session_state.deals.index:
                                st.session_state.deals.loc[tx["deal_index"], "Status"] = "Sold"
                                st.session_state.deals.loc[tx["deal_index"], "Est. Resale Value"] = tx["amount"]
                                persist()
                        else:
                            st.info("Not paid yet — try again once the customer confirms.")
            if changed:
                persist_sales_log()
                st.rerun()

st.markdown("---")
st.caption("Appraze · Cooper River Trading Co. · built for CTBids / eBay / HiBid / FB Marketplace / Mercari / Chairish / Etsy sourcing")
