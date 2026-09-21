"""
Appraze
A single-page Streamlit dashboard for tracking, filtering, and evaluating
resale/auction deals across Estate Auctions, eBay, HiBid, Facebook Marketplace,
Mercari, Chairish, and Etsy.

Run locally (optional, no terminal needed for deployment - see DEPLOY.md):
    streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import date, datetime, timedelta
import io
import base64
import json
import urllib.request
import urllib.error
from finance import (
    compute_verdict, deal_roi, profit_calc, inventory_margin,
    melt_value, max_bid_after_premium, GOLD_PURITY, SILVER_PURITY,
)
from auth import require_auth, logout
from pos import create_pos_checkout, check_payment_status
from sales_documents import calculate_totals, apply_payment, new_account_number, new_document_number
from storage import load_table, save_table

# --------------------------------------------------------------------------
# PAGE CONFIG + GLOBAL STYLE
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Appraze",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

LIGHT_CSS = """
<style>
    .appraze-brand img { width: 100%; max-width: 210px; display: block; margin: 0 auto 14px; }
    .appraze-brand { padding: 6px 0 4px; }
    .stApp { background: #f7f9fc; color: #172033; }
    section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #d9a321; }
    h1, h2, h3, h4 { color: #102a43 !important; letter-spacing: -0.02em; }
    .kpi-card {
        background: #ffffff;
        border: 1px solid #d8e0ea;
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 4px 18px rgba(31,52,73,0.08);
    }
    .kpi-label { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; color: #5b6b7f; margin-bottom: 6px; }
    .kpi-value { font-size: 1.6rem; font-weight: 700; color: #102a43; }
    .kpi-sub { font-size: 0.8rem; color: #16834b; margin-top: 2px; }
    .kpi-sub.neg { color: #c62845; }
    .badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.03em; }
    .badge-strongbuy { background: #e8f7ef; color: #137a45; border: 1px solid #9bd8b5; }
    .badge-buy { background: #eaf8ee; color: #21843d; border: 1px solid #a9ddb7; }
    .badge-ceiling { background: #eaf6fb; color: #176b8f; border: 1px solid #a6d9ec; }
    .badge-borderline { background: #fff6df; color: #996b00; border: 1px solid #e7c66a; }
    .badge-passverdict { background: #fdebed; color: #b4233c; border: 1px solid #efabb7; }
    .badge-hot { background: #fff6df; color: #996b00; border: 1px solid #e7c66a; }
    .badge-good { background: #e8f7ef; color: #137a45; border: 1px solid #9bd8b5; }
    .badge-pass { background: #fdebed; color: #b4233c; border: 1px solid #efabb7; }
    .stButton>button {
        border-radius: 10px;
        border: 1px solid #b8c5d4;
        background: #ffffff;
        color: #102a43;
        font-weight: 600;
    }
    .stButton>button:hover { border-color: #d9a321; color: #102a43; }
    div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid #d8e0ea; }
    .block-container { padding-top: 1.6rem; }
    hr { border-color: #d9a321; }
</style>
"""
st.markdown(LIGHT_CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# PWA HEAD INJECTION
# --------------------------------------------------------------------------
# static/manifest.json + the PWA icons only make the app installable if a
# <link rel="manifest"> actually reaches the real page <head> -- browsers
# never discover a manifest that isn't referenced. st.markdown(...,
# unsafe_allow_html=True) can't do this: a <script> tag set via
# dangerouslySetInnerHTML never executes, and a bare <link> lands in
# Streamlit's app body, not <head>. components.html() instead renders in a
# same-origin iframe, so its script can reach window.parent.document.head
# directly -- the standard workaround for injecting real <head> tags into a
# Streamlit page. Runs once per browser tab (guarded by a data attribute)
# so Streamlit's frequent reruns don't keep re-appending duplicate tags.
_PWA_HEAD_INJECTION = """
<script>
(function () {
    try {
        var head = window.parent.document.head;
        if (head.querySelector('[data-appraze-pwa]')) return;
        var tags = [
            ['link', {rel: 'manifest', href: './app/static/manifest.json'}],
            ['link', {rel: 'icon', href: './app/static/appraze-logo.svg', sizes: '192x192', type: 'image/png'}],
            ['link', {rel: 'apple-touch-icon', href: './app/static/appraze-logo.svg'}],
            ['meta', {name: 'theme-color', content: '#f7f9fc'}],
            ['meta', {name: 'mobile-web-app-capable', content: 'yes'}],
            ['meta', {name: 'apple-mobile-web-app-capable', content: 'yes'}],
            ['meta', {name: 'apple-mobile-web-app-status-bar-style', content: 'default'}],
        ];
        tags.forEach(function (t) {
            var el = window.parent.document.createElement(t[0]);
            el.setAttribute('data-appraze-pwa', '1');
            for (var k in t[1]) el.setAttribute(k, t[1][k]);
            head.appendChild(el);
        });
    } catch (e) {
        // Same-origin access can fail in unusual embeds (e.g. a cross-origin
        // preview iframe) -- fail silently rather than breaking the app;
        // the app is fully usable without the install prompt.
    }
})();
</script>
"""
components.html(_PWA_HEAD_INJECTION, height=0, width=0)

# --------------------------------------------------------------------------
# LOGIN GATE
# --------------------------------------------------------------------------
# One shared Admin login, backed by auth.py's existing hashed-credential
# model (CRTC_ADMIN_USERNAME / CRTC_ADMIN_PASSWORD_HASH secrets -- see
# AUTH_SETUP.md). require_auth() is the same gate every page under pages/
# calls independently, since Streamlit does not run this script before a
# direct page navigation. There is no fallback/default password: if the
# Admin secrets aren't configured, require_auth() refuses to render a
# login form at all rather than accepting a guessable placeholder.
require_auth()

WORKSPACE = "business"

DISPLAY_NAME = "Owner"

PLATFORMS = ["Estate Auctions", "eBay", "HiBid", "Facebook Marketplace", "Mercari", "Chairish", "Etsy", "Estate Sale", "Curbside"]
CATEGORIES = ["Gold/Silver Jewelry", "Sterling Flatware", "Watches", "Furniture", "Electronics", "Coins/Currency", "Collectibles", "Other"]
STATUSES = ["Watching", "Bid Placed", "Won/Purchased", "Listed", "Sold", "Passed"]

# --------------------------------------------------------------------------
# SESSION STATE INIT
# --------------------------------------------------------------------------
if "deals_by_ws" not in st.session_state:
    st.session_state.deals_by_ws = {}

if WORKSPACE not in st.session_state.deals_by_ws:
    if WORKSPACE == "business":
        st.session_state.deals_by_ws[WORKSPACE] = pd.DataFrame([
            {
                "Date Added": date.today().isoformat(),
                "Item": "14k Gold Chain Lot (Sample)",
                "Platform": "Estate Auctions",
                "Category": "Gold/Silver Jewelry",
                "Cost": 85.00,
                "Est. Resale Value": 240.00,
                "Status": "Won/Purchased",
                "Notes": "Sample row \u2014 edit or delete me",
            }
        ])
    else:        # Any future separate workspace starts clean and empty        st.session_state.deals_by_ws[WORKSPACE] = pd.DataFrame(columns=[            "Date Added", "Item", "Platform", "Category", "Cost",
            "Est. Resale Value", "Status", "Notes",
        ])

# Working alias for the rest of the app - always write changes back to
# deals_by_ws[WORKSPACE] so nothing leaks between workspaces.
st.session_state.deals = st.session_state.deals_by_ws[WORKSPACE]

if "editor_key" not in st.session_state:
    st.session_state.editor_key = 0


# --------------------------------------------------------------------------
# BUSINESS PROFILE — document identity belongs to the logged-in CRTC customer
# --------------------------------------------------------------------------
BUSINESS_PROFILE_DEFAULTS = {
    "Business Name": "",
    "Legal Name": "",
    "Tax ID / EIN": "",
    "Business Address": "",
    "Phone": "",
    "Email": "",
    "Website": "",
    "Invoice Footer": "",
    "Tax Registration / State": "",
}


def load_business_profile():
    result = load_table("business_profile")
    if result.success and result.payload:
        row = result.payload[0]
        return {**BUSINESS_PROFILE_DEFAULTS, **row}
    return dict(BUSINESS_PROFILE_DEFAULTS)


def save_business_profile(profile):
    return save_table(pd.DataFrame([profile]), "business_profile")


def recalc(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived profit columns to the deals dataframe."""
    df = df.copy()
    df["Cost"] = pd.to_numeric(df["Cost"], errors="coerce").fillna(0)
    df["Est. Resale Value"] = pd.to_numeric(df["Est. Resale Value"], errors="coerce").fillna(0)
    results = df.apply(lambda r: deal_roi(r["Cost"], r["Est. Resale Value"]), axis=1)
    df["Gross Profit"] = results.apply(lambda t: t[0])
    df["ROI %"] = results.apply(lambda t: t[1])
    return df


# --------------------------------------------------------------------------
# SIDEBAR — ADD DEAL / IMPORT / EXPORT
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="appraze-brand"><img src="./app/static/appraze-logo.svg" alt="Appraze"></div>', unsafe_allow_html=True)
    st.markdown("### 🔑 Appraze")
    st.caption("Buy. Track. Value. List. Sell. Get Paid. Grow.")
    st.caption("Signed in \u00b7 Cooper River Trading Co.")
    if st.button("Sign out", use_container_width=True):
        logout()
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
                st.session_state.deals = pd.concat(
                    [st.session_state.deals, new_row], ignore_index=True
                )
                st.session_state.deals_by_ws[WORKSPACE] = st.session_state.deals
                st.session_state.editor_key += 1
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
                st.session_state.deals_by_ws[WORKSPACE] = st.session_state.deals
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
    st.caption("Note: this app resets its data if the free hosting instance restarts. Download a CSV backup regularly, then re-import it next session.")


# --------------------------------------------------------------------------
# HEADER + KPI ROW
# --------------------------------------------------------------------------
st.markdown("## 🔑 Appraze")
st.caption("Buy. Track. Value. List. Sell. Get Paid. Grow.")
st.caption(f"Live dashboard — updated {datetime.now().strftime('%b %d, %Y %I:%M %p')}")

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
# TABS — DASHBOARD / PROFIT CALCULATOR
# --------------------------------------------------------------------------
tab_dash, tab_calc, tab_inv, tab_sup, tab_charge, tab_accounts, tab_ai = st.tabs([
    "📊  Deal Dashboard", "🧮  Profit Calculator", "📦  Inventory",
    "🤝  Suppliers", "💳  Charge Customer", "🧾  Accounts & Invoices", "🔍  AI Analyzer",
])

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
        s = search.lower()        filtered = filtered[
            filtered["Item"].str.lower().str.contains(s, na=False)            | filtered["Notes"].str.lower().str.contains(s, na=False)
        ]
    st.markdown(f"#### Deals ({len(filtered)})")
    st.caption("Edit any cell directly. Add rows with the ➕ button in the sidebar, delete by selecting a row and pressing the trash icon.")

    edited = st.data_editor(
        filtered.drop(columns=["Gross Profit", "ROI %"]),
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

    # push edits made in the filtered view back into the master dataframe
    if not edited.equals(filtered.drop(columns=["Gross Profit", "ROI %"])):
        st.session_state.deals.update(edited)
        # handle any newly added rows from the data editor
        if len(edited) > len(filtered):
            extra_rows = edited.iloc[len(filtered):]
            st.session_state.deals = pd.concat([st.session_state.deals, extra_rows], ignore_index=True)
        st.session_state.deals_by_ws[WORKSPACE] = st.session_state.deals

    st.markdown("---")
    st.markdown("#### Quick profit view per deal (30/70 · 50/50)")
    quick = recalc(edited) if len(edited) else df.iloc[0:0]
    if len(quick):
        quick["30/70 (Cooper River share @70%)"] = quick["Gross Profit"] * 0.70
        quick["50/50 (each share)"] = quick["Gross Profit"] * 0.50
        quick["Verdict"] = quick["ROI %"].apply(lambda r: compute_verdict(r)[0])
        st.dataframe(
            quick[["Item", "Platform", "Cost", "Est. Resale Value", "Gross Profit",
                   "ROI %", "Verdict", "30/70 (Cooper River share @70%)", "50/50 (each share)"]],
            use_container_width=True,
            column_config={
                "Cost": st.column_config.NumberColumn(format="$%.2f"),
                "Est. Resale Value": st.column_config.NumberColumn(format="$%.2f"),
                "Gross Profit": st.column_config.NumberColumn(format="$%.2f"),
                "ROI %": st.column_config.NumberColumn(format="%.1f%%"),
                "30/70 (Cooper River share @70%)": st.column_config.NumberColumn(format="$%.2f"),
                "50/50 (each share)": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
    else:
        st.info("No deals match the current filters.")

with tab_calc:
    st.markdown("#### Standalone Profit Calculator")
    st.caption("Punch in a purchase cost and expected resale value to see both split scenarios instantly — handy for evaluating a lot in real time during a live auction.")

    cc1, cc2 = st.columns(2)
    with cc1:
        calc_cost = st.number_input("Purchase / bid cost ($)", min_value=0.0, step=1.0, format="%.2f", key="calc_cost")
    with cc2:
        calc_resale = st.number_input("Estimated resale value ($)", min_value=0.0, step=1.0, format="%.2f", key="calc_resale")

    with st.expander("Optional: factor in platform fees / buyer's premium"):
        fee_pct = st.slider("Fees as % of resale value (marketplace + payment processing)", 0.0, 30.0, 13.0, 0.5)
        premium_pct = st.slider("Buyer's premium at purchase (e.g. Estate Auctions 18%)", 0.0, 25.0, 18.0, 0.5)

    true_cost, net_resale, gross_profit, roi = profit_calc(calc_cost, calc_resale, fee_pct, premium_pct)

    st.markdown("---")
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">True Cost (w/ premium)</div>
            <div class="kpi-value">${true_cost:,.2f}</div></div>""", unsafe_allow_html=True)
    with r2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Net Resale (after fees)</div>
            <div class="kpi-value">${net_resale:,.2f}</div></div>""", unsafe_allow_html=True)
    with r3:
        cls = "kpi-sub" if gross_profit >= 0 else "kpi-sub neg"
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Net Profit</div>
            <div class="kpi-value">${gross_profit:,.2f}</div>
            <div class="{cls}">{roi:,.1f}% ROI</div></div>""", unsafe_allow_html=True)
    with r4:
        v_label, v_badge = compute_verdict(roi)
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Verdict</div>
            <div style="margin-top:6px;"><span class="badge {v_badge}">{v_label}</span></div></div>""", unsafe_allow_html=True)

    st.markdown("### Split Scenarios")
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("##### 30 / 70 Split")
        st.write(f"**Partner A (30%):** ${gross_profit*0.30:,.2f}")
        st.write(f"**Partner B (70%):** ${gross_profit*0.70:,.2f}")
    with s2:
        st.markdown("##### 50 / 50 Split")
        st.write(f"**Partner A (50%):** ${gross_profit*0.50:,.2f}")
        st.write(f"**Partner B (50%):** ${gross_profit*0.50:,.2f}")

    st.markdown("---")
    st.markdown("#### Melt Value Calculator (Gold & Silver)")
    st.caption("Estimate the raw melt value of a gold or silver item by weight and purity, and compare it against the 80%-of-melt buying ceiling.")

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        metal = st.selectbox("Metal", ["Gold", "Silver"], key="melt_metal")
    with mc2:
        spot_price = st.number_input(
            f"Current spot price ($/troy oz {metal.lower()})", min_value=0.0, step=1.0, format="%.2f", key="melt_spot"
        )
    with mc3:
        weight_unit = st.radio("Weight unit", ["Grams", "Troy oz"], horizontal=True, key="melt_unit")

    purity_options = GOLD_PURITY if metal == "Gold" else SILVER_PURITY
    mc4, mc5 = st.columns(2)
    with mc4:
        purity_label = st.selectbox("Purity / Karat", list(purity_options.keys()), key="melt_purity")
    with mc5:
        weight_input = st.number_input(f"Weight ({weight_unit.lower()})", min_value=0.0, step=0.1, format="%.3f", key="melt_weight")

    purity = purity_options[purity_label]
    melt_dollar_value, ceiling_80 = melt_value(spot_price, weight_input, weight_unit, purity)

    mv1, mv2, mv3 = st.columns(3)
    with mv1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Melt Value (100%)</div>
            <div class="kpi-value">${melt_dollar_value:,.2f}</div></div>""", unsafe_allow_html=True)
    with mv2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">80% of Melt (Buy Ceiling)</div>
            <div class="kpi-value">${ceiling_80:,.2f}</div></div>""", unsafe_allow_html=True)
    with mv3:
        melt_premium_pct = st.slider("Buyer's premium at purchase %", 0.0, 25.0, 18.0, 0.5, key="melt_premium")
        true_melt_cost_note = max_bid_after_premium(ceiling_80, melt_premium_pct)
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Max Bid (ceiling \u00f7 premium)</div>
            <div class="kpi-value">${true_melt_cost_note:,.2f}</div></div>""", unsafe_allow_html=True)

    if melt_dollar_value > 0:
        st.markdown(
            f"""<div style="margin-top:14px;padding:14px 18px;background:#2b1418;border:1px solid #f2607a55;border-radius:10px;">
            <span style="color:#f2607a;font-weight:700;">\u26a0\ufe0f 80% Ceiling Rule:</span>
            <span style="color:#e6e9ef;"> Never pay more than <b>${ceiling_80:,.2f}</b> for this item's raw metal value
            (before any buyer's premium). Factoring in an {melt_premium_pct:.1f}% premium, your actual max bid
            should be <b>${true_melt_cost_note:,.2f}</b> to stay within the 80% ceiling after fees.</span>
            </div>""",
            unsafe_allow_html=True,
        )


# ==========================================================================
# INVENTORY TAB
# ==========================================================================
with tab_inv:
    if "inventory_by_ws" not in st.session_state:
        st.session_state.inventory_by_ws = {}
    if WORKSPACE not in st.session_state.inventory_by_ws:
        st.session_state.inventory_by_ws[WORKSPACE] = pd.DataFrame([
            {"Item Name": "Sample: Vintage Camera", "Cost Basis": 40.0, "List Price": 120.0, "Notes": "Edit or delete me"},
        ] if WORKSPACE == "business" else [], columns=["Item Name", "Cost Basis", "List Price", "Notes"])

    st.markdown("#### Settings")
    ic1, ic2 = st.columns(2)
    with ic1:
        inv_fee_pct = st.slider("Estimated Platform Fees %", 0.0, 30.0, 13.0, 0.5, key="inv_fee")
    with ic2:
        margin_threshold = st.slider("Minimum healthy Net Margin %", 0.0, 50.0, 20.0, 1.0, key="inv_margin_thresh")

    inv_df = st.session_state.inventory_by_ws[WORKSPACE].copy()
    inv_df["Cost Basis"] = pd.to_numeric(inv_df["Cost Basis"], errors="coerce").fillna(0)
    inv_df["List Price"] = pd.to_numeric(inv_df["List Price"], errors="coerce").fillna(0)
    inv_results = inv_df.apply(lambda r: inventory_margin(r["Cost Basis"], r["List Price"], inv_fee_pct), axis=1)
    inv_df["Gross Profit"] = inv_results.apply(lambda t: t[0])
    inv_df["Net Profit"] = inv_results.apply(lambda t: t[1])
    inv_df["Net Margin %"] = inv_results.apply(lambda t: t[2])
    flagged_count = int(((inv_df["Net Margin %"] < margin_threshold) | (inv_df["Gross Profit"] < 15)).sum()) if len(inv_df) else 0

    st.markdown("#### Summary")
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Total Inventory Value</div>
            <div class="kpi-value">${inv_df['List Price'].sum():,.2f}</div></div>""", unsafe_allow_html=True)
    with b2:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Total Capital Invested</div>
            <div class="kpi-value">${inv_df['Cost Basis'].sum():,.2f}</div></div>""", unsafe_allow_html=True)
    with b3:
        avg_margin = inv_df["Net Margin %"].mean() if len(inv_df) else 0
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Average Net Margin</div>
            <div class="kpi-value">{avg_margin:,.1f}%</div></div>""", unsafe_allow_html=True)
    with b4:
        st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Flagged Low-Margin</div>
            <div class="kpi-value">{flagged_count}</div></div>""", unsafe_allow_html=True)

    st.markdown("#### Items")
    st.caption("Edit inline. New rows are picked up automatically. Amber = below your margin threshold, green = healthy.")

    edited_inv = st.data_editor(
        st.session_state.inventory_by_ws[WORKSPACE],
        num_rows="dynamic",
        use_container_width=True,
        key=f"inv_editor_{WORKSPACE}",        column_config={
            "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
            "List Price": st.column_config.NumberColumn(format="$%.2f"),        },
    )
    st.session_state.inventory_by_ws[WORKSPACE] = edited_inv
    if len(edited_inv):
        disp = edited_inv.copy()
        disp["Cost Basis"] = pd.to_numeric(disp["Cost Basis"], errors="coerce").fillna(0)
        disp["List Price"] = pd.to_numeric(disp["List Price"], errors="coerce").fillna(0)
        disp_results = disp.apply(lambda r: inventory_margin(r["Cost Basis"], r["List Price"], inv_fee_pct), axis=1)
        disp["Gross Profit"] = disp_results.apply(lambda t: t[0])
        disp["Net Profit"] = disp_results.apply(lambda t: t[1])
        disp["Net Margin %"] = disp_results.apply(lambda t: t[2])
        disp["Status"] = disp["Net Margin %"].apply(
            lambda m: "⚠️ Low Margin" if m < margin_threshold else "✓ Healthy"
        )
        st.dataframe(
            disp[["Item Name", "Cost Basis", "List Price", "Gross Profit", "Net Profit", "Net Margin %", "Status"]],
            use_container_width=True,
            column_config={
                "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
                "List Price": st.column_config.NumberColumn(format="$%.2f"),
                "Gross Profit": st.column_config.NumberColumn(format="$%.2f"),
                "Net Profit": st.column_config.NumberColumn(format="$%.2f"),
                "Net Margin %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

    inv_csv_buffer = io.StringIO()
    st.session_state.inventory_by_ws[WORKSPACE].to_csv(inv_csv_buffer, index=False)
    st.download_button(
        "Download Inventory as CSV",
        data=inv_csv_buffer.getvalue(),
        file_name=f"appraze_inventory_{date.today().isoformat()}.csv",
        mime="text/csv",
    )

# ==========================================================================
# SUPPLIERS TAB
# ==========================================================================
with tab_sup:
    if "suppliers_by_ws" not in st.session_state:
        st.session_state.suppliers_by_ws = {}
    if WORKSPACE not in st.session_state.suppliers_by_ws:
        st.session_state.suppliers_by_ws[WORKSPACE] = pd.DataFrame([
            {
                "Supplier Name": "Sample: Caring Transitions Charleston", "Contact Person": "Ann",
                "Phone": "", "Email": "", "Tier": 2, "Category": "Estate sale",
                "First Contact Date": date.today().isoformat(), "Last Contact Date": date.today().isoformat(),
                "Relationship Status": "Warm", "Compliance Doc Status": "N/A", "Value Potential": "Medium",
                "Notes": "Edit or delete me",
            }
        ] if WORKSPACE == "business" else [], columns=[
            "Supplier Name", "Contact Person", "Phone", "Email", "Tier", "Category",
            "First Contact Date", "Last Contact Date", "Relationship Status",
            "Compliance Doc Status", "Value Potential", "Notes",
        ])

    sup_df = st.session_state.suppliers_by_ws[WORKSPACE].copy()

    def _next_follow_up(last_contact):
        try:
            d = pd.to_datetime(last_contact) + pd.Timedelta(days=30)
            return d.date().isoformat()
        except Exception:
            return ""

    if len(sup_df):
        sup_df["Next Follow-Up Due"] = sup_df["Last Contact Date"].apply(_next_follow_up)

    st.markdown("#### Saved Views")
    view = st.radio(
        "Quick filter", ["All", "This Week's Follow-Ups", "Probation Watch", "Tier 1 Compliance Gaps", "High Value, Cold"],
        horizontal=True, label_visibility="collapsed",
    )

    view_df = sup_df.copy()
    today = pd.Timestamp(date.today())
    if len(view_df):
        if view == "This Week's Follow-Ups":
            due = pd.to_datetime(view_df["Next Follow-Up Due"], errors="coerce")
            view_df = view_df[(due <= today + pd.Timedelta(days=7)) & (view_df["Relationship Status"] != "Inactive")]
        elif view == "Probation Watch":
            view_df = view_df[view_df["Relationship Status"] == "Probation"]
        elif view == "Tier 1 Compliance Gaps":
            view_df = view_df[(view_df["Tier"].astype(str) == "1") & (view_df["Compliance Doc Status"] != "Verified")]
        elif view == "High Value, Cold":
            view_df = view_df[(view_df["Value Potential"] == "High") & (view_df["Relationship Status"] == "Cold")]

    st.markdown(f"#### Suppliers ({len(view_df)})")
    edited_sup = st.data_editor(
        st.session_state.suppliers_by_ws[WORKSPACE],
        num_rows="dynamic",
        use_container_width=True,
        key=f"sup_editor_{WORKSPACE}",
        column_config={
            "Tier": st.column_config.SelectboxColumn(options=[1, 2, 3]),
            "Relationship Status": st.column_config.SelectboxColumn(options=["Cold", "Warm", "Active", "Probation", "Inactive"]),
            "Compliance Doc Status": st.column_config.SelectboxColumn(options=["N/A", "Pending", "Verified"]),
            "Value Potential": st.column_config.SelectboxColumn(options=["Low", "Medium", "High"]),
        },
    )
    st.session_state.suppliers_by_ws[WORKSPACE] = edited_sup

    if view != "All" and len(view_df):
        st.markdown("---")
        st.caption(f"Filtered view: {view}")
        st.dataframe(view_df, use_container_width=True)

    sup_csv_buffer = io.StringIO()
    st.session_state.suppliers_by_ws[WORKSPACE].to_csv(sup_csv_buffer, index=False)
    st.download_button(
        "Download Suppliers as CSV",
        data=sup_csv_buffer.getvalue(),
        file_name=f"appraze_suppliers_{date.today().isoformat()}.csv",
        mime="text/csv",
    )

# ==========================================================================
# CHARGE CUSTOMER TAB (Stripe Payment Links - no raw card entry, ever)
# ==========================================================================
with tab_charge:
    st.markdown("#### Charge a Customer")
    st.caption(
        "Creates a one-off Stripe Checkout link for this exact amount. Send or show the link/QR "
        "to your customer - they enter their own card or tap Apple Pay / Google Pay. Your card "
        "number never touches this app."
    )

    stripe_key = None
    try:
        stripe_key = st.secrets.get("STRIPE_SECRET_KEY", None)
    except Exception:
        stripe_key = None

    if not stripe_key:
        st.warning(
            "Charge Customer isn't configured yet. Add your Stripe **secret** key (starts with `sk_live_` "
            "or `sk_test_`) as a Secret named `STRIPE_SECRET_KEY` in Streamlit Cloud's app Settings \u2192 "
            "Secrets, then reload this page."
        )
    else:
        # sales_log is the one durable, shared record every charge lands in -
        # the standalone webhook service (stripe_webhook_server.py) and the
        # "Check Status" button below both read/write this exact table, so a
        # charge created here is reconcilable from any device or session,
        # unlike the old session-state-only "Recent Charges" list this
        # replaced (which vanished on refresh and gave the webhook service
        # nothing to match against, since it never carried an invoice_id).
        sales_log_result = load_table("sales_log", shared=True)
        sales_log = list(sales_log_result.payload) if sales_log_result.success and sales_log_result.payload else []

        with st.form("charge_form"):
            amt = st.number_input("Amount ($)", min_value=0.50, step=1.0, format="%.2f")
            desc = st.text_input("Description", placeholder="e.g. Estate cleanout \u2014 123 Main St")
            submitted = st.form_submit_button("Create Checkout Link")

        if submitted and amt > 0 and desc.strip():
            result = create_pos_checkout(amt, desc.strip())
            if result.success:
                st.success("Checkout link created!")
                st.code(result.checkout_url, language=None)
                sales_log.append({
                    "Invoice #": result.invoice_id,
                    "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "Description": desc.strip(),
                    "Amount": amt,
                    "Status": "Awaiting Payment",
                    "Link": result.checkout_url,
                    "session_id": result.session_id,
                })
                save_result = save_table(pd.DataFrame(sales_log), "sales_log", shared=True)
                if not save_result.success:
                    st.warning(
                        f"Checkout link created, but couldn't save it to the shared sales log "
                        f"({save_result.error}). The link above still works \u2014 write down the "
                        f"invoice number ({result.invoice_id}) to reconcile it manually."
                    )
            else:
                st.error(result.error)

        st.markdown("---")
        st.markdown("#### Recent Charges")
        if sales_log:
            log_df = pd.DataFrame(sales_log).drop(columns=["session_id"], errors="ignore")
            st.dataframe(log_df, use_container_width=True, column_config={
                "Amount": st.column_config.NumberColumn(format="$%.2f"),
                "Link": st.column_config.LinkColumn(),
            })

            awaiting = [row for row in sales_log if row.get("Status") == "Awaiting Payment" and row.get("session_id")]
            if awaiting:
                st.markdown("##### Check payment status")
                st.caption(
                    "The webhook service reconciles these automatically if it's deployed (see "
                    "DEPLOY.md). This button does the same check manually, right now."
                )
                for row in awaiting[-5:]:  # most recent few - avoid an unbounded button list                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{row.get('Invoice #')}** \u2014 {row.get('Description', '')} (${float(row.get('Amount', 0)):,.2f})")
                    if c2.button("Check Status", key=f"check_{row['Invoice #']}", use_container_width=True):
                        if check_payment_status(row["session_id"]):                            for r in sales_log:
                                if r.get("Invoice #") == row["Invoice #"]:
                                    r["Status"] = "Paid (Card)"
                            save_table(pd.DataFrame(sales_log), "sales_log", shared=True)                            st.success(f"{row['Invoice #']} is paid!")
                            st.rerun()
                        else:
                            st.info("Not paid yet.")
        else:
            st.info("No charges created yet.")

# ==========================================================================# ===========================================================================
# ACCOUNTS / QUOTES / INVOICES
# ===========================================================================
with tab_accounts:
    st.markdown("#### Business Profile & Sales Documents")
    st.caption("Your business identity is used on quotes, invoices and printable sales documents.")

    if "business_profile" not in st.session_state:
        st.session_state.business_profile = load_business_profile()

    profile = st.session_state.business_profile
    with st.expander("⚙️ Your business information", expanded=not bool(profile.get("Business Name"))):
        with st.form("business_profile_form"):
            bp1, bp2 = st.columns(2)
            with bp1:
                business_name = st.text_input("Business / DBA name", value=profile.get("Business Name", ""))
                legal_name = st.text_input("Legal business name", value=profile.get("Legal Name", ""))
                tax_id = st.text_input("Tax ID / EIN", value=profile.get("Tax ID / EIN", ""), type="password", help="Stored as part of your business profile. Only include what you need printed on your documents.")
                tax_registration = st.text_input("Tax registration / state", value=profile.get("Tax Registration / State", ""))
                phone = st.text_input("Business phone", value=profile.get("Phone", ""))
            with bp2:
                email = st.text_input("Business email", value=profile.get("Email", ""))
                website = st.text_input("Website", value=profile.get("Website", ""))
                address = st.text_area("Business address", value=profile.get("Business Address", ""))
                footer = st.text_area("Invoice / quote footer", value=profile.get("Invoice Footer", ""), placeholder="Payment terms, thank-you message, return policy, etc.")
            save_profile = st.form_submit_button("Save business information", use_container_width=True)
        if save_profile:
            st.session_state.business_profile = {
                "Business Name": business_name.strip(), "Legal Name": legal_name.strip(),
                "Tax ID / EIN": tax_id.strip(), "Tax Registration / State": tax_registration.strip(),
                "Business Address": address.strip(), "Phone": phone.strip(), "Email": email.strip(),
                "Website": website.strip(), "Invoice Footer": footer.strip(),
            }
            result = save_business_profile(st.session_state.business_profile)
            if result.success:
                st.success("Business information saved. New documents will use it.")
            else:
                st.error(f"Could not save business information: {result.error}")

    st.markdown("---")
    st.markdown("#### Customers, Quotes & Invoices")
    st.caption("Repeat customers, quotes, invoices, discounts and payment tracking — focused on reseller operations.")

    account_cols = ["Account #", "Business / Customer", "Contact", "Email", "Phone", "Billing Address", "Shipping Address", "Payment Terms", "Default Discount %", "Notes", "Created"]
    doc_cols = ["Document #", "Type", "Account #", "Customer", "Issue Date", "Due Date", "Expiration Date", "Status", "Subtotal", "Discount", "Tax", "Shipping", "Total", "Amount Paid", "Amount Due", "Line Items", "Notes", "Created"]
    if "customer_accounts" not in st.session_state:
        loaded = load_table("customer_accounts")
        st.session_state.customer_accounts = pd.DataFrame(loaded.payload, columns=account_cols) if loaded.success and loaded.payload else pd.DataFrame(columns=account_cols)
    if "sales_documents" not in st.session_state:
        loaded = load_table("sales_documents")
        st.session_state.sales_documents = pd.DataFrame(loaded.payload, columns=doc_cols) if loaded.success and loaded.payload else pd.DataFrame(columns=doc_cols)

    ac1, ac2 = st.columns([1, 2])
    with ac1:
        st.markdown("##### Add Customer / Business")
        with st.form("new_customer_form", clear_on_submit=True):
            customer_name = st.text_input("Business / customer name")
            contact = st.text_input("Contact person")
            email = st.text_input("Email")
            phone = st.text_input("Phone")
            billing_address = st.text_area("Billing address")
            shipping_address = st.text_area("Shipping address")
            terms = st.selectbox("Payment terms", ["Due on receipt", "Net 7", "Net 15", "Net 30", "Custom"])
            default_discount = st.number_input("Default discount %", min_value=0.0, max_value=100.0, step=1.0)
            notes = st.text_area("Notes")
            add_customer = st.form_submit_button("Save Customer", use_container_width=True)
        if add_customer:
            if not customer_name.strip():
                st.error("Customer/business name is required.")
            else:
                row = {"Account #": new_account_number(), "Business / Customer": customer_name.strip(), "Contact": contact.strip(), "Email": email.strip(), "Phone": phone.strip(), "Billing Address": billing_address.strip(), "Shipping Address": shipping_address.strip(), "Payment Terms": terms, "Default Discount %": default_discount, "Notes": notes.strip(), "Created": datetime.now().strftime("%Y-%m-%d %H:%M")}
                st.session_state.customer_accounts = pd.concat([st.session_state.customer_accounts, pd.DataFrame([row])], ignore_index=True)
                save_table(st.session_state.customer_accounts, "customer_accounts")
                st.success(f"Saved {row['Business / Customer']} ({row['Account #']}).")
                st.rerun()

    with ac2:
        st.markdown("##### Customer Accounts")
        edited_accounts = st.data_editor(st.session_state.customer_accounts, num_rows="dynamic", use_container_width=True, key="customer_accounts_editor", column_config={"Default Discount %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f%%")})
        if not edited_accounts.equals(st.session_state.customer_accounts):
            st.session_state.customer_accounts = edited_accounts
            save_table(edited_accounts, "customer_accounts")

    st.markdown("---")
    st.markdown("##### Create Quote or Invoice")
    accounts = st.session_state.customer_accounts
    if not len(accounts):
        st.info("Add a customer above before creating a quote or invoice.")
    else:
        labels = {f"{r['Account #']} — {r['Business / Customer']}": i for i, r in accounts.iterrows()}
        selected_label = st.selectbox("Customer / account", list(labels.keys()), key="sales_customer")
        selected_account = accounts.loc[labels[selected_label]].to_dict()
        default_disc = float(selected_account.get("Default Discount %", 0) or 0)
        line_items = st.data_editor(pd.DataFrame([{"Description": "", "Quantity": 1.0, "Unit Price": 0.0}]), num_rows="dynamic", use_container_width=True, key="sales_line_items", column_config={"Description": st.column_config.TextColumn(required=True), "Quantity": st.column_config.NumberColumn(min_value=0.0, step=1.0), "Unit Price": st.column_config.NumberColumn(min_value=0.0, format="$%.2f")})
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1: discount_type = st.selectbox("Discount type", ["fixed", "percent"], key="sales_discount_type")
        with fc2: discount_value = st.number_input("Discount", min_value=0.0, value=default_disc if discount_type == "percent" else 0.0, step=1.0, key="sales_discount")
        with fc3: tax_pct = st.number_input("Tax %", min_value=0.0, max_value=100.0, step=0.25, key="sales_tax")
        with fc4: shipping = st.number_input("Shipping / delivery", min_value=0.0, step=1.0, key="sales_shipping")
        totals = calculate_totals(line_items.to_dict("records"), discount_value, discount_type, tax_pct, shipping)
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Subtotal", f"${totals['subtotal']:,.2f}")
        t2.metric("Discount", f"-${totals['discount']:,.2f}")
        t3.metric("Tax + Shipping", f"${totals['tax'] + totals['shipping']:,.2f}")
        t4.metric("Total", f"${totals['total']:,.2f}")
        q1, q2, q3 = st.columns(3)
        with q1: create_quote = st.button("Create Quote", use_container_width=True)
        with q2: create_invoice = st.button("Create Invoice", use_container_width=True)
        with q3: create_payment_link = st.button("Create Payment Link", use_container_width=True)
        if create_quote or create_invoice or create_payment_link:
            if totals["total"] <= 0:
                st.error("Add at least one priced line item.")
            else:
                kind = "QUO" if create_quote else "INV"
                doc_no = new_document_number(kind)
                is_quote = create_quote
                row = {"Document #": doc_no, "Type": "Quote" if is_quote else "Invoice", "Account #": selected_account["Account #"], "Customer": selected_account["Business / Customer"], "Issue Date": date.today().isoformat(), "Due Date": "" if is_quote else (date.today() + pd.Timedelta(days=30)).isoformat(), "Expiration Date": (date.today() + pd.Timedelta(days=14)).isoformat() if is_quote else "", "Status": "Draft" if is_quote else ("Awaiting Payment" if create_payment_link else "Unpaid"), "Subtotal": totals["subtotal"], "Discount": totals["discount"], "Tax": totals["tax"], "Shipping": totals["shipping"], "Total": totals["total"], "Amount Paid": 0.0, "Amount Due": totals["total"], "Line Items": json.dumps(line_items.to_dict("records")), "Notes": "", "Created": datetime.now().strftime("%Y-%m-%d %H:%M")}
                st.session_state.sales_documents = pd.concat([st.session_state.sales_documents, pd.DataFrame([row])], ignore_index=True)
                save_table(st.session_state.sales_documents, "sales_documents")
                if create_payment_link:
                    result = create_pos_checkout(totals["total"], f"{doc_no} — {selected_account['Business / Customer']}", str(selected_account.get("Email", "") or ""), invoice_id=doc_no)
                    if result.success:
                        log = load_table("sales_log", shared=True)
                        sales_log = list(log.payload) if log.success and log.payload else []
                        sales_log.append({"Invoice #": doc_no, "Date": datetime.now().strftime("%Y-%m-%d %H:%M"), "Description": f"{selected_account['Business / Customer']} — invoice", "Amount": totals["total"], "Status": "Awaiting Payment", "Link": result.checkout_url, "session_id": result.session_id})
                        save_table(pd.DataFrame(sales_log), "sales_log", shared=True)
                        st.success(f"Payment link created for {doc_no}.")
                        st.code(result.checkout_url)
                    else: st.error(result.error)
                else: st.success(f"{row['Type']} {doc_no} created.")
                st.rerun()

        st.markdown("---")
        st.markdown("##### Documents / Accounts Receivable")
        docs = st.session_state.sales_documents
        if len(docs):
            st.dataframe(docs, use_container_width=True, column_config={k: st.column_config.NumberColumn(format="$%.2f") for k in ["Subtotal","Discount","Tax","Shipping","Total","Amount Paid","Amount Due"]})
            options = [f"{i} — {r['Document #']} — {r['Customer']} — ${float(r['Total']):,.2f}" for i, r in docs.iterrows()]
            chosen = st.selectbox("Manage document", options, key="manage_sales_doc")
            doc_idx = int(chosen.split(" — ", 1)[0])
            doc = docs.loc[doc_idx]
            if doc["Type"] == "Quote":
                if st.button("Convert Quote to Invoice", key=f"convert_{doc['Document #']}"):
                    invoice_no = new_document_number("INV")
                    converted = doc.to_dict()
                    converted.update({"Document #": invoice_no, "Type": "Invoice", "Issue Date": date.today().isoformat(), "Due Date": (date.today() + pd.Timedelta(days=30)).isoformat(), "Expiration Date": "", "Status": "Unpaid", "Amount Paid": 0.0, "Amount Due": float(doc["Total"]), "Created": datetime.now().strftime("%Y-%m-%d %H:%M")})
                    st.session_state.sales_documents = pd.concat([st.session_state.sales_documents, pd.DataFrame([converted])], ignore_index=True)
                    st.session_state.sales_documents.loc[doc_idx, "Status"] = "Accepted / Converted"
                    save_table(st.session_state.sales_documents, "sales_documents")
                    st.success(f"Created invoice {invoice_no} from {doc['Document #']}.")
                    st.rerun()
            if doc["Type"] == "Invoice":
                pay = st.number_input("Record payment", min_value=0.0, max_value=float(doc["Amount Due"] or 0), step=1.0, key=f"pay_{doc['Document #']}")
                if st.button("Apply Payment", key=f"apply_{doc['Document #']}"):
                    payment = apply_payment(float(doc["Total"]), float(doc["Amount Paid"]) + pay)
                    for col, val in [("Amount Paid", payment["amount_paid"]), ("Amount Due", payment["amount_due"]), ("Status", payment["status"])]: st.session_state.sales_documents.loc[doc_idx, col] = val
                    save_table(st.session_state.sales_documents, "sales_documents")
                    st.rerun()
            html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{doc["Document #"]}</title><style>body{{font-family:Arial;max-width:800px;margin:40px auto;padding:20px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #ddd}}</style></head><body><h1>{profile.get("Business Name") or profile.get("Legal Name") or "Your Business"}</h1><p>{profile.get("Business Address","")}<br>{profile.get("Phone","")} · {profile.get("Email","")} · {profile.get("Website","")}</p><h2>{doc["Type"]} {doc["Document #"]}</h2><p><b>Customer:</b> {doc["Customer"]} ({doc["Account #"]})</p><p><b>Issued:</b> {doc["Issue Date"]} &nbsp; <b>Due:</b> {doc["Due Date"] or "—"}</p><p><b>Status:</b> {doc["Status"]}</p><hr><table><tr><th>Description</th><th>Qty</th><th>Unit Price</th><th>Line Total</th></tr>{"" .join(f"<tr><td>{item.get('Description', '')}</td><td>{float(item.get('Quantity', 0)):g}</td><td>${float(item.get('Unit Price', 0)):,.2f}</td><td>${float(item.get('Quantity', 0))*float(item.get('Unit Price', 0)):,.2f}</td></tr>" for item in json.loads(doc.get("Line Items", "[]") or "[]"))}</table><p>Subtotal: ${float(doc["Subtotal"]):,.2f}<br>Discount: -${float(doc["Discount"]):,.2f}<br>Tax: ${float(doc["Tax"]):,.2f}<br>Shipping: ${float(doc["Shipping"]):,.2f}</p><h2>Total: ${float(doc["Total"]):,.2f}</h2><p>Amount due: ${float(doc["Amount Due"]):,.2f}</p><p><b>Tax ID / EIN:</b> {profile.get("Tax ID / EIN","")} &nbsp; <b>Tax registration:</b> {profile.get("Tax Registration / State","")}</p><p>{profile.get("Invoice Footer","")}</p><p>Print this page or save as PDF from your browser.</p></body></html>"""
            st.download_button("Download printable document", html, file_name=f"{doc['Document #']}.html", mime="text/html", use_container_width=True)
        else: st.info("No quotes or invoices yet.")


# AI ANALYZER TAB (Claude identifies/estimates - your own math still verdicts)
# ==========================================================================
with tab_ai:
    st.markdown("#### AI Item Analyzer")
    st.caption(
        "Upload a photo and/or describe an item. Claude identifies it and estimates a value range. "
        "Your own profit math (not the AI) still decides buy/pass \u2014 review everything before saving."
    )

    anthropic_key = None
    try:
        anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", None)
    except Exception:
        anthropic_key = None

    if not anthropic_key:
        st.warning(
            "AI Analyzer not configured yet. Add your Anthropic API key (starts with `sk-ant-`) as a "
            "Secret named `ANTHROPIC_API_KEY` in Streamlit Cloud's app Settings \u2192 Secrets, then reload."
        )
    else:
        photo = st.file_uploader("Photo (optional)", type=["png", "jpg", "jpeg"])        text_desc = st.text_area("Description (optional)", placeholder="e.g. Sterling silver flatware set, 12 pieces, monogrammed")

        if st.button("Analyze"):
            if not photo and not text_desc.strip():
                st.warning("Add a photo or a description first.")            else:
                content = []
                if photo is not None:
                    img_bytes = photo.read()
                    img_b64 = base64.b64encode(img_bytes).decode()                    media_type = "image/png" if photo.type == "image/png" else "image/jpeg"
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": img_b64},
                    })
                prompt_text = text_desc.strip() if text_desc.strip() else "Identify and value this item."
                content.append({"type": "text", "text": prompt_text})

                system_prompt = (
                    "You identify resale items for an estate-cleanout and flip business, and draft "
                    "marketplace listing copy for the seller to review and post themselves (you do not "
                    "post anything yourself). Respond with ONLY valid JSON, no other text, no markdown "
                    "fences, using exactly these fields: itemName (string), category (one of: Gold/Silver "
                    "Jewelry, Sterling Flatware, Watches, Furniture, Electronics, Coins/Currency, "
                    "Collectibles, LEGO, Other), conditionEstimate (one of: New, Like New, Good, Fair, "
                    "Parts Only), estimatedValueLow (number, USD), estimatedValueHigh (number, USD), "
                    "confidence (Low, Medium, or High), reasoning (1-2 sentence explanation), "
                    "suggestedListPrice (number, USD \u2014 a specific competitive asking price, not just "
                    "the midpoint of the value range), listingDrafts (object with three keys: ebay, "
                    "facebook, mercari \u2014 each an object with 'title' and 'description'). eBay titles "
                    "must be SEO-keyword-rich and under 80 characters. Facebook and Mercari titles should "
                    "be shorter and more conversational, under 60 characters. Each description should be "
                    "2-4 sentences, honest about condition, and written in the tone typical of that "
                    "platform (eBay: detailed and structured; Facebook/Mercari: casual and direct)."
                )
                try:
                    body = json.dumps({
                        "model": "claude-sonnet-5",
                        "max_tokens": 900,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": content}],
                    }).encode()
                    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST")
                    req.add_header("x-api-key", anthropic_key)
                    req.add_header("anthropic-version", "2023-06-01")
                    req.add_header("content-type", "application/json")
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        result = json.loads(resp.read().decode())
                    raw_text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
                    parsed = json.loads(raw_text)
                    if not isinstance(parsed, dict):
                        raise ValueError("Response wasn't a JSON object")
                    # Store in session state so the result (and its "Add to Inventory"
                    # button below) survives the rerun triggered by that button click -
                    # keeping it nested inside this "if st.button(Analyze)" block would
                    # make the button click silently do nothing.
                    st.session_state.ai_last_result = parsed
                except urllib.error.HTTPError as e:
                    st.error(f"Claude API error: {e.read().decode()[:300]}")
                except json.JSONDecodeError:
                    st.error("The AI's response wasn't valid JSON \u2014 try again, or simplify the description.")
                except Exception as e:
                    st.error(f"Something went wrong: {e}")

        if st.session_state.get("ai_last_result"):
            parsed = st.session_state.ai_last_result
            st.success(f"**{parsed.get('itemName', '?')}** \u2014 {parsed.get('category', '?')}")
            ac1, ac2, ac3 = st.columns(3)

            def _safe_float(val, default=0.0):
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return default

            with ac1:
                st.metric("Condition", parsed.get("conditionEstimate", "?"))
            with ac2:
                lo = _safe_float(parsed.get("estimatedValueLow", 0))
                hi = _safe_float(parsed.get("estimatedValueHigh", 0))
                st.metric("Est. Value Range", f"${lo:,.0f} \u2013 ${hi:,.0f}")
            with ac3:
                st.metric("Confidence", parsed.get("confidence", "?"))
            st.caption(parsed.get("reasoning", ""))

            suggested_price = _safe_float(parsed.get("suggestedListPrice", 0))
            st.markdown(f"""<div class="kpi-card" style="margin-top:10px;"><div class="kpi-label">Suggested List Price</div>
                <div class="kpi-value">${suggested_price:,.2f}</div></div>""", unsafe_allow_html=True)

            drafts = parsed.get("listingDrafts", {})
            if isinstance(drafts, dict) and drafts:
                st.markdown("---")
                st.markdown("#### Listing Drafts \u2014 copy and paste yourself, nothing auto-posts")
                platform_labels = {"ebay": "eBay", "facebook": "Facebook Marketplace", "mercari": "Mercari"}
                dtabs = st.tabs([platform_labels.get(k, k) for k in drafts.keys()])
                for dtab, (plat_key, plat_draft) in zip(dtabs, drafts.items()):
                    with dtab:
                        if not isinstance(plat_draft, dict):
                            st.caption("No draft returned for this platform \u2014 try analyzing again.")
                            continue
                        st.text_input(f"{platform_labels.get(plat_key, plat_key)} Title", value=plat_draft.get("title", ""), key=f"draft_title_{plat_key}")
                        st.text_area(f"{platform_labels.get(plat_key, plat_key)} Description", value=plat_draft.get("description", ""), height=100, key=f"draft_desc_{plat_key}")

            if st.button("Add to Inventory as a new item"):
                if "inventory_by_ws" not in st.session_state:
                    st.session_state.inventory_by_ws = {}
                if WORKSPACE not in st.session_state.inventory_by_ws:
                    st.session_state.inventory_by_ws[WORKSPACE] = pd.DataFrame(
                        columns=["Item Name", "Cost Basis", "List Price", "Notes"]
                    )
                prefill_price = suggested_price if suggested_price else ((lo + hi) / 2 if (lo or hi) else 0)
                new_item = pd.DataFrame([{
                    "Item Name": parsed.get("itemName", "New Item"),
                    "Cost Basis": 0.0,
                    "List Price": prefill_price,
                    "Notes": f"AI estimate ({parsed.get('confidence', '?')} confidence): {parsed.get('reasoning', '')}",
                }])
                st.session_state.inventory_by_ws[WORKSPACE] = pd.concat(
                    [st.session_state.inventory_by_ws[WORKSPACE], new_item], ignore_index=True
                )
                st.success("Added to Inventory \u2014 go set the real Cost Basis on the Inventory tab.")
                st.session_state.ai_last_result = None

st.markdown("---")
st.caption("Appraze · Buy. Track. Value. List. Sell. Get Paid. Grow. · Built for buying, valuing, managing, and selling physical goods")