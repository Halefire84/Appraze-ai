"""
Appraze
A single-page Streamlit dashboard for tracking, filtering, and evaluating
resale/auction deals across Estate Auctions, eBay, HiBid, Facebook Marketplace,
Mercari, Chairish, and Etsy.

Run locally (optional, no terminal needed for deployment - see DEPLOY.md):
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
import secrets
import base64
import json
import urllib.request
import urllib.error
import urllib.parse
from finance import (
    compute_verdict, deal_roi, profit_calc, inventory_margin,
    melt_value, max_bid_after_premium, sales_tax, GOLD_PURITY, SILVER_PURITY,
)

# --------------------------------------------------------------------------
# PAGE CONFIG + GLOBAL STYLE
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Appraze",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded",
)

DARK_CSS = """
<style>
    /* ---- base ---- */
    .stApp {
        background: linear-gradient(180deg, #0b0f14 0%, #10151c 100%);
        color: #e6e9ef;
    }
    section[data-testid="stSidebar"] {
        background: #0d1117;
        border-right: 1px solid #1f2733;
    }
    h1, h2, h3, h4 { color: #f2f4f8 !important; letter-spacing: -0.02em; }

    /* ---- KPI cards ---- */
    .kpi-card {
        background: linear-gradient(145deg, #141a23, #0f141b);
        border: 1px solid #232c38;
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 4px 18px rgba(0,0,0,0.25);
    }
    .kpi-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #8b96a5;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #f7f9fc;
    }
    .kpi-sub { font-size: 0.8rem; color: #67e8a4; margin-top: 2px; }
    .kpi-sub.neg { color: #f2607a; }

    /* ---- pills / badges ---- */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .badge-strongbuy { background: #0f2e22; color: #22c98c; border: 1px solid #22c98c40;}
    .badge-buy { background: #10331a; color: #4ade80; border: 1px solid #4ade8040;}
    .badge-ceiling { background: #142a37; color: #38bdf8; border: 1px solid #38bdf840;}
    .badge-borderline { background: #37260f; color: #f5a524; border: 1px solid #f5a52440;}
    .badge-passverdict { background: #2b1418; color: #f2607a; border: 1px solid #f2607a40;}

    /* buttons */
    .stButton>button {
        border-radius: 10px;
        border: 1px solid #2a3441;
        background: #1a212b;
        color: #e6e9ef;
        font-weight: 600;
    }
    .stButton>button:hover { border-color: #4d7cff; color: #4d7cff; }

    /* dataframe */
    div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

    /* metric containers spacing */
    .block-container { padding-top: 1.6rem; }

    hr { border-color: #232c38; }
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# LOGIN GATE
# --------------------------------------------------------------------------
# Single-user login. This template gets customized per customer, so there's
# just one password gate here rather than multiple named accounts.
#
# The password lives in Streamlit's Secrets manager (Settings -> Secrets on
# Streamlit Community Cloud), never hardcoded here. Set this secret:
#   APP_PASSWORD = "whatever you pick"
# If it isn't set yet, the app falls back to a placeholder so it still runs
# on first deploy - set the real one in Secrets before sharing the link.

WORKSPACE = "business"

def _get_password() -> str:
    try:
        return st.secrets.get("APP_PASSWORD", "changeme")
    except Exception:
        return "changeme"

def login_screen():
    st.markdown(
        """
        <div style="max-width:380px;margin:80px auto 0 auto;text-align:center;">
            <div style="font-size:2rem;font-weight:800;color:#f7f9fc;">🪙 Appraze</div>
            <div style="color:#8b96a5;margin-top:4px;">Sign in to continue</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        st.write("")
        pwd = st.text_input("Password", type="password", key="login_pwd")
        expected = _get_password()

        if st.button("Sign in", width="stretch"):
            if secrets.compare_digest(pwd, expected):
                st.session_state.authed = True
                st.rerun()
            else:
                st.error("Wrong password. Set or find the current one under Settings \u2192 Secrets \u2192 APP_PASSWORD.")

if "authed" not in st.session_state:
    st.session_state.authed = False

if not st.session_state.authed:
    login_screen()
    st.stop()

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
    else:
        # Any future separate workspace starts clean and empty
        st.session_state.deals_by_ws[WORKSPACE] = pd.DataFrame(columns=[
            "Date Added", "Item", "Platform", "Category", "Cost",
            "Est. Resale Value", "Status", "Notes",
        ])

# Working alias for the rest of the app - always write changes back to
# deals_by_ws[WORKSPACE] so nothing leaks between workspaces.
st.session_state.deals = st.session_state.deals_by_ws[WORKSPACE]

if "editor_key" not in st.session_state:
    st.session_state.editor_key = 0


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
    st.markdown("### 🪙 Appraze")
    st.caption("Signed in \u00b7 Cooper River Trading Co.")
    if st.button("Sign out", width="stretch"):
        st.session_state.authed = False
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
        submitted = st.form_submit_button("Add to dashboard", width="stretch")

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
        width="stretch",
    )

    st.markdown("---")
    st.caption("Note: this app resets its data if the free hosting instance restarts. Download a CSV backup regularly, then re-import it next session.")


# --------------------------------------------------------------------------
# HEADER + KPI ROW
# --------------------------------------------------------------------------
st.markdown("## Appraze")
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
tab_inv_home, tab_dash, tab_calc, tab_inv, tab_sup, tab_cust, tab_charge, tab_ai = st.tabs([
    "🧾  Invoices", "📊  Deal Dashboard", "🧮  Profit Calculator", "📦  Inventory",
    "🤝  Suppliers", "👤  Customers", "💳  Point of Sale", "🔍  AI Analyzer",
])

# ==========================================================================
# INVOICES TAB (home / landing tab - opens first)
# ==========================================================================
with tab_inv_home:
    st.markdown("#### Invoices")
    st.caption("Every completed sale from the Point of Sale tab lands here automatically \u2014 this is your home view for what's been invoiced, paid, and still awaiting payment.")

    # Same idempotent init guards used on the Point of Sale tab below - safe
    # to repeat since Invoices can render before a POS sale has ever run.
    if "sales_log_by_ws" not in st.session_state:
        st.session_state.sales_log_by_ws = {}
    if WORKSPACE not in st.session_state.sales_log_by_ws:
        st.session_state.sales_log_by_ws[WORKSPACE] = []

    inv_log = st.session_state.sales_log_by_ws[WORKSPACE]

    if not inv_log:
        st.info("No invoices yet. Ring up a sale on the Point of Sale tab and it'll show up here.")
    else:
        inv_log_df = pd.DataFrame(inv_log)
        total_invoiced = float(inv_log_df["Total"].sum())
        paid_count = int((inv_log_df["Status"] == "Paid (Cash)").sum())
        awaiting_count = int((inv_log_df["Status"] == "Awaiting Payment").sum())
        today_str = date.today().isoformat()
        today_total = float(inv_log_df.loc[inv_log_df["Date"].str.startswith(today_str), "Total"].sum())

        h1, h2, h3, h4 = st.columns(4)
        with h1:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Total Invoiced</div>
                <div class="kpi-value">${total_invoiced:,.2f}</div></div>""", unsafe_allow_html=True)
        with h2:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Today's Invoiced</div>
                <div class="kpi-value">${today_total:,.2f}</div></div>""", unsafe_allow_html=True)
        with h3:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Paid (Cash)</div>
                <div class="kpi-value">{paid_count}</div></div>""", unsafe_allow_html=True)
        with h4:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Awaiting Payment</div>
                <div class="kpi-value">{awaiting_count}</div></div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### All Invoices")
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            home_method_filter = st.selectbox("Filter by payment method", ["All", "Card", "Cash"], key="home_log_method_filter")
        with fcol2:
            home_date_filter = st.text_input("Filter by date (YYYY-MM-DD, optional)", key="home_log_date_filter")

        home_filtered_log = inv_log_df.copy()
        if home_method_filter != "All":
            home_filtered_log = home_filtered_log[home_filtered_log["Payment Method"] == home_method_filter]
        if home_date_filter.strip():
            home_filtered_log = home_filtered_log[home_filtered_log["Date"].str.startswith(home_date_filter.strip())]

        st.dataframe(
            home_filtered_log,
            width="stretch",
            column_config={
                "Subtotal": st.column_config.NumberColumn(format="$%.2f"),
                "Tax": st.column_config.NumberColumn(format="$%.2f"),
                "Total": st.column_config.NumberColumn(format="$%.2f"),
                "Link": st.column_config.LinkColumn(),
            },
        )
        st.markdown(f"**Running total ({len(home_filtered_log)} invoice{'s' if len(home_filtered_log) != 1 else ''}): ${home_filtered_log['Total'].sum():,.2f}**")

        home_log_csv_buffer = io.StringIO()
        inv_log_df.to_csv(home_log_csv_buffer, index=False)
        st.download_button(
            "Download all Invoices as CSV",
            data=home_log_csv_buffer.getvalue(),
            file_name=f"appraze_invoices_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

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
        filtered.drop(columns=["Gross Profit", "ROI %"]),
        num_rows="dynamic",
        width="stretch",
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
            width="stretch",
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
            {"Item Name": "Sample: Vintage Camera", "Category": "Collectibles", "Cost Basis": 40.0, "List Price": 120.0,
             "Status": "Available", "Description": "Edit or delete me", "Notes": "Edit or delete me"},
        ] if WORKSPACE == "business" else [], columns=["Item Name", "Category", "Cost Basis", "List Price", "Status", "Description", "Notes"])

    # Backward-compat: older sessions/rows created before these columns existed
    for _col, _default in [("Status", "Available"), ("Category", "Other"), ("Description", ""), ("Barcode", "")]:
        if _col not in st.session_state.inventory_by_ws[WORKSPACE].columns:
            st.session_state.inventory_by_ws[WORKSPACE][_col] = _default
        st.session_state.inventory_by_ws[WORKSPACE][_col] = st.session_state.inventory_by_ws[WORKSPACE][_col].fillna(_default)

    st.markdown("#### Scan Barcode")
    st.caption(
        "Works with any USB or Bluetooth barcode scanner \u2014 they act like a keyboard, so just click into "
        "the box below and scan. Matches an existing item instantly, or offers to add it as new."
    )
    with st.form("barcode_scan_form", clear_on_submit=True):
        bcol1, bcol2 = st.columns([3, 1])
        with bcol1:
            scanned_code = st.text_input("Scan or type barcode", key="barcode_scan_input", label_visibility="collapsed", placeholder="Scan or type barcode\u2026")
        with bcol2:
            scan_submitted = st.form_submit_button("Look up", width="stretch")

    if scan_submitted:
        if not scanned_code.strip():
            st.warning("Scan or type a barcode first.")
        else:
            st.session_state.last_scanned_barcode = scanned_code.strip()

    if st.session_state.get("last_scanned_barcode"):
        code = st.session_state.last_scanned_barcode
        live_inv = st.session_state.inventory_by_ws[WORKSPACE]
        match = live_inv[live_inv["Barcode"].astype(str) == code]
        if len(match):
            row = match.iloc[0]
            st.success(f"Found: **{row['Item Name']}** \u2014 {row['Category']} \u00b7 Cost ${float(row['Cost Basis']):,.2f} \u00b7 List ${float(row['List Price']):,.2f} \u00b7 {row['Status']}")
            if st.button("Clear scan", key="clear_scan_found"):
                st.session_state.last_scanned_barcode = None
                st.rerun()
        else:
            st.info(f"No item found with barcode `{code}`. Add it as a new item:")
            with st.form("barcode_new_item_form"):
                nb1, nb2 = st.columns(2)
                with nb1:
                    new_barcode_name = st.text_input("Item Name", key="new_barcode_item_name")
                    new_barcode_cost = st.number_input("Cost Basis ($)", min_value=0.0, step=1.0, format="%.2f", key="new_barcode_cost")
                with nb2:
                    new_barcode_category = st.selectbox("Category", CATEGORIES, key="new_barcode_category")
                    new_barcode_price = st.number_input("List Price ($)", min_value=0.0, step=1.0, format="%.2f", key="new_barcode_price")
                new_item_submitted = st.form_submit_button("Add to Inventory")

            if new_item_submitted:
                if not new_barcode_name.strip():
                    st.warning("Give the item a name first.")
                else:
                    new_row = pd.DataFrame([{
                        "Item Name": new_barcode_name.strip(), "Category": new_barcode_category,
                        "Cost Basis": new_barcode_cost, "List Price": new_barcode_price,
                        "Status": "Available", "Description": "", "Notes": "", "Barcode": code,
                    }])
                    st.session_state.inventory_by_ws[WORKSPACE] = pd.concat(
                        [st.session_state.inventory_by_ws[WORKSPACE], new_row], ignore_index=True
                    )
                    st.success(f"Added {new_barcode_name.strip()} with barcode {code}.")
                    st.session_state.last_scanned_barcode = None
                    st.rerun()

    st.markdown("---")
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
        width="stretch",
        key=f"inv_editor_{WORKSPACE}",
        column_config={
            "Cost Basis": st.column_config.NumberColumn(format="$%.2f"),
            "List Price": st.column_config.NumberColumn(format="$%.2f"),
            "Status": st.column_config.SelectboxColumn(options=["Available", "Sold"]),
            "Category": st.column_config.SelectboxColumn(options=CATEGORIES),
        },
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
            width="stretch",
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
        width="stretch",
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
        st.dataframe(view_df, width="stretch")

    sup_csv_buffer = io.StringIO()
    st.session_state.suppliers_by_ws[WORKSPACE].to_csv(sup_csv_buffer, index=False)
    st.download_button(
        "Download Suppliers as CSV",
        data=sup_csv_buffer.getvalue(),
        file_name=f"appraze_suppliers_{date.today().isoformat()}.csv",
        mime="text/csv",
    )

# ==========================================================================
# CUSTOMERS TAB (CRM - purchase history is computed live from the Sales Log,
# never entered twice by hand)
# ==========================================================================
with tab_cust:
    if "customers_by_ws" not in st.session_state:
        st.session_state.customers_by_ws = {}
    if WORKSPACE not in st.session_state.customers_by_ws:
        st.session_state.customers_by_ws[WORKSPACE] = pd.DataFrame([
            {"Customer Name": "Sample: Ann Whitfield", "Phone": "", "Email": "", "Segment": "Regular",
             "First Visit Date": date.today().isoformat(), "Notes": "Edit or delete me"},
        ] if WORKSPACE == "business" else [], columns=[
            "Customer Name", "Phone", "Email", "Segment", "First Visit Date", "Notes",
        ])

    st.markdown("#### Customers")
    st.caption("Total Spent, Last Purchase, and # of Purchases are computed automatically from the Sales Log on the Point of Sale tab - never entered by hand, so they can't drift out of sync.")

    edited_cust = st.data_editor(
        st.session_state.customers_by_ws[WORKSPACE],
        num_rows="dynamic",
        width="stretch",
        key=f"cust_editor_{WORKSPACE}",
        column_config={
            "Segment": st.column_config.SelectboxColumn(options=["Regular", "VIP", "One-time", "Wholesale"]),
        },
    )
    st.session_state.customers_by_ws[WORKSPACE] = edited_cust

    sales_log_for_cust = st.session_state.get("sales_log_by_ws", {}).get(WORKSPACE, [])
    if len(edited_cust):
        if sales_log_for_cust:
            sales_df_for_cust = pd.DataFrame(sales_log_for_cust)
        else:
            sales_df_for_cust = pd.DataFrame(columns=["Customer", "Total", "Date"])

        def _customer_stats(name):
            matches = sales_df_for_cust[sales_df_for_cust.get("Customer", pd.Series(dtype=str)) == name] if "Customer" in sales_df_for_cust.columns else sales_df_for_cust.iloc[0:0]
            total_spent = float(matches["Total"].sum()) if len(matches) else 0.0
            purchase_count = len(matches)
            last_purchase = matches["Date"].max() if len(matches) else ""
            return total_spent, purchase_count, last_purchase

        stats = edited_cust["Customer Name"].apply(_customer_stats)
        display_cust = edited_cust.copy()
        display_cust["Total Spent"] = stats.apply(lambda t: t[0])
        display_cust["# Purchases"] = stats.apply(lambda t: t[1])
        display_cust["Last Purchase"] = stats.apply(lambda t: t[2])

        st.markdown("---")
        st.markdown("#### Purchase History (computed)")
        st.dataframe(
            display_cust[["Customer Name", "Segment", "Total Spent", "# Purchases", "Last Purchase"]],
            width="stretch",
            column_config={"Total Spent": st.column_config.NumberColumn(format="$%.2f")},
        )

    cust_csv_buffer = io.StringIO()
    st.session_state.customers_by_ws[WORKSPACE].to_csv(cust_csv_buffer, index=False)
    st.download_button(
        "Download Customers as CSV",
        data=cust_csv_buffer.getvalue(),
        file_name=f"appraze_customers_{date.today().isoformat()}.csv",
        mime="text/csv",
    )

# ==========================================================================
# POINT OF SALE TAB (Stripe Payment Links for card - no raw card entry, ever;
# cash logged directly; both feed one sales log; items sold from Inventory
# get marked Sold automatically; sales link to a Customer if one is chosen)
# ==========================================================================
with tab_charge:
    st.markdown("#### Point of Sale")
    st.caption(
        "Ring up a sale with one or more items, apply tax, and take card or cash. "
        "Card payments use a Stripe Payment Link - your customer enters their own card "
        "or taps Apple Pay / Google Pay. Your app never touches a raw card number."
    )

    stripe_key = None
    try:
        stripe_key = st.secrets.get("STRIPE_SECRET_KEY", None)
    except Exception:
        stripe_key = None

    # Rendered once, right after a completed sale forces a rerun (see the
    # Complete Sale handler below) - by then sales_log_by_ws already carries
    # the new invoice, so the Invoices tab picks it up on this same rerun too,
    # instead of staying stale until the next unrelated widget interaction.
    if st.session_state.get("pos_last_sale"):
        sale = st.session_state.pos_last_sale
        st.success(f"Sale complete — Invoice {sale['invoice_num']}")
        st.markdown(f"""<div class="kpi-card" style="margin-top:10px;">
            <div class="kpi-label">Invoice {sale['invoice_num']}</div>
            <div style="margin:8px 0;color:#e6e9ef;">{sale['item_summary']}</div>
            <div style="color:#8b96a5;">Subtotal ${sale['subtotal']:,.2f} + Tax ${sale['tax_amt']:,.2f} = <b style="color:#f7f9fc;">Total ${sale['total']:,.2f}</b></div>
            <div style="margin-top:6px;color:#8b96a5;">Payment: {sale['payment_method']} · Status: {sale['status']}</div>
            </div>""", unsafe_allow_html=True)
        if sale.get("link_url"):
            st.code(sale["link_url"], language=None)
        st.session_state.pos_last_sale = None

    if "cart_by_ws" not in st.session_state:
        st.session_state.cart_by_ws = {}
    if WORKSPACE not in st.session_state.cart_by_ws:
        st.session_state.cart_by_ws[WORKSPACE] = []

    if "sales_log_by_ws" not in st.session_state:
        st.session_state.sales_log_by_ws = {}
    if WORKSPACE not in st.session_state.sales_log_by_ws:
        st.session_state.sales_log_by_ws[WORKSPACE] = []

    if "inventory_by_ws" not in st.session_state:
        st.session_state.inventory_by_ws = {}
    inv_for_pos = st.session_state.inventory_by_ws.get(WORKSPACE, pd.DataFrame(columns=["Item Name", "Cost Basis", "List Price", "Status", "Notes"]))
    if "Status" not in inv_for_pos.columns:
        inv_for_pos["Status"] = "Available"
    available_items = inv_for_pos[inv_for_pos["Status"] == "Available"]

    st.markdown("#### Add an Item")
    add_mode = st.radio("Add from", ["Inventory", "Manual entry"], horizontal=True, key="pos_add_mode")

    if add_mode == "Inventory":
        if len(available_items) == 0:
            st.info("No available items in Inventory yet - add some on the Inventory tab, or use Manual entry.")
        else:
            pc1, pc2, pc3 = st.columns([2, 1, 1])
            with pc1:
                inv_choice = st.selectbox("Item", available_items["Item Name"].tolist(), key="pos_inv_choice")
            with pc2:
                inv_row = available_items[available_items["Item Name"] == inv_choice].iloc[0]
                pos_price = st.number_input("Price ($)", min_value=0.0, value=float(inv_row["List Price"]), step=1.0, format="%.2f", key="pos_inv_price")
            with pc3:
                pos_qty = st.number_input("Qty", min_value=1, value=1, step=1, key="pos_inv_qty")
            if st.button("Add to Cart", key="pos_add_inv"):
                st.session_state.cart_by_ws[WORKSPACE].append({
                    "Item": inv_choice, "Price": pos_price, "Qty": pos_qty, "Source": "Inventory",
                })
                st.success(f"Added: {inv_choice}")
    else:
        mc1, mc2, mc3 = st.columns([2, 1, 1])
        with mc1:
            manual_item = st.text_input("Item description", key="pos_manual_item")
        with mc2:
            manual_price = st.number_input("Price ($)", min_value=0.0, step=1.0, format="%.2f", key="pos_manual_price")
        with mc3:
            manual_qty = st.number_input("Qty", min_value=1, value=1, step=1, key="pos_manual_qty")
        if st.button("Add to Cart", key="pos_add_manual"):
            if not manual_item.strip():
                st.warning("Give the item a name first.")
            else:
                st.session_state.cart_by_ws[WORKSPACE].append({
                    "Item": manual_item.strip(), "Price": manual_price, "Qty": manual_qty, "Source": "Manual",
                })
                st.success(f"Added: {manual_item.strip()}")

    st.markdown("---")
    st.markdown("#### Cart")
    cart = st.session_state.cart_by_ws[WORKSPACE]

    if not cart:
        st.info("Cart is empty - add an item above.")
    else:
        cart_df = pd.DataFrame(cart)
        cart_df["Line Total"] = cart_df["Price"] * cart_df["Qty"]
        st.dataframe(
            cart_df[["Item", "Price", "Qty", "Line Total"]],
            width="stretch",
            column_config={
                "Price": st.column_config.NumberColumn(format="$%.2f"),
                "Line Total": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
        remove_idx = st.selectbox(
            "Remove an item", ["(none)"] + [f"{i}: {c['Item']}" for i, c in enumerate(cart)], key="pos_remove_choice"
        )
        if remove_idx != "(none)" and st.button("Remove Selected Item", key="pos_remove_btn"):
            idx_to_remove = int(remove_idx.split(":")[0])
            st.session_state.cart_by_ws[WORKSPACE].pop(idx_to_remove)
            st.rerun()

        subtotal = float(cart_df["Line Total"].sum())
        tax_rate_pct = st.slider(
            "Sales tax % (SC base rate is 6% - Charleston County/Mount Pleasant can run up to 9% combined)",
            0.0, 12.0, 6.0, 0.25, key="pos_tax_rate",
        )
        tax_amt, total = sales_tax(subtotal, tax_rate_pct)

        tcol1, tcol2, tcol3 = st.columns(3)
        with tcol1:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Subtotal</div>
                <div class="kpi-value">${subtotal:,.2f}</div></div>""", unsafe_allow_html=True)
        with tcol2:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Tax ({tax_rate_pct:.2f}%)</div>
                <div class="kpi-value">${tax_amt:,.2f}</div></div>""", unsafe_allow_html=True)
        with tcol3:
            st.markdown(f"""<div class="kpi-card"><div class="kpi-label">Total Due</div>
                <div class="kpi-value">${total:,.2f}</div></div>""", unsafe_allow_html=True)

        st.markdown("---")
        customers_for_pos = st.session_state.get("customers_by_ws", {}).get(WORKSPACE, pd.DataFrame(columns=["Customer Name"]))
        customer_choice = st.selectbox(
            "Customer (optional)", ["Walk-in / Unknown"] + customers_for_pos["Customer Name"].tolist(), key="pos_customer_choice"
        )
        payment_method = st.radio("Payment method", ["Card", "Cash"], horizontal=True, key="pos_payment_method")

        if payment_method == "Card" and not stripe_key:
            st.warning(
                "Card payment isn't configured yet. Add your Stripe **secret** key (starts with `sk_live_` "
                "or `sk_test_`) as a Secret named `STRIPE_SECRET_KEY` in Streamlit Cloud's app Settings \u2192 "
                "Secrets, then reload this page \u2014 or choose Cash for this sale."
            )

        can_complete = (payment_method == "Cash") or (payment_method == "Card" and stripe_key)
        if st.button("Complete Sale", disabled=not can_complete, key="pos_complete_sale"):
            invoice_num = f"POS-{date.today().isoformat()}-{len(st.session_state.sales_log_by_ws[WORKSPACE]) + 1}"
            item_summary = "; ".join(f"{c['Item']} x{c['Qty']}" for c in cart)
            link_url = ""
            status = "Paid (Cash)"

            if payment_method == "Card":
                try:
                    data = urllib.parse.urlencode({
                        "line_items[0][price_data][currency]": "usd",
                        "line_items[0][price_data][product_data][name]": f"Invoice {invoice_num}: {item_summary}"[:250],
                        "line_items[0][price_data][unit_amount]": int(round(total * 100)),
                        "line_items[0][quantity]": 1,
                    }).encode()
                    req = urllib.request.Request("https://api.stripe.com/v1/payment_links", data=data, method="POST")
                    auth = base64.b64encode(f"{stripe_key}:".encode()).decode()
                    req.add_header("Authorization", f"Basic {auth}")
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        result = json.loads(resp.read().decode())
                    link_url = result.get("url", "") if isinstance(result, dict) else ""
                    status = "Awaiting Payment"
                except urllib.error.HTTPError as e:
                    st.error(f"Stripe error: {e.read().decode()[:300]}")
                    st.stop()
                except Exception as e:
                    st.error(f"Couldn't create the payment link: {e}")
                    st.stop()

            # Mark inventory-sourced items as Sold so they don't get sold twice
            inv_df_live = st.session_state.inventory_by_ws.get(WORKSPACE)
            if inv_df_live is not None and len(inv_df_live):
                for c in cart:
                    if c.get("Source") == "Inventory":
                        match = inv_df_live[(inv_df_live["Item Name"] == c["Item"]) & (inv_df_live["Status"] == "Available")]
                        if len(match):
                            inv_df_live.loc[match.index[0], "Status"] = "Sold"
                st.session_state.inventory_by_ws[WORKSPACE] = inv_df_live

            st.session_state.sales_log_by_ws[WORKSPACE].append({
                "Invoice #": invoice_num,
                "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Customer": customer_choice,
                "Items": item_summary,
                "Subtotal": subtotal,
                "Tax": tax_amt,
                "Total": total,
                "Payment Method": payment_method,
                "Status": status,
                "Link": link_url,
            })
            st.session_state.cart_by_ws[WORKSPACE] = []

            st.session_state.pos_last_sale = {
                "invoice_num": invoice_num, "item_summary": item_summary,
                "subtotal": subtotal, "tax_amt": tax_amt, "total": total,
                "payment_method": payment_method, "status": status, "link_url": link_url,
            }
            st.rerun()

    st.markdown("---")
    st.caption("Full invoice history, filters, and CSV export are on the **Invoices** tab \u2014 every sale completed here appears there automatically.")

# ==========================================================================
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
        photo = st.file_uploader("Photo (optional)", type=["png", "jpg", "jpeg"])
        text_desc = st.text_area("Description (optional)", placeholder="e.g. Sterling silver flatware set, 12 pieces, monogrammed")

        if st.button("Analyze"):
            if not photo and not text_desc.strip():
                st.warning("Add a photo or a description first.")
            else:
                content = []
                if photo is not None:
                    img_bytes = photo.read()
                    img_b64 = base64.b64encode(img_bytes).decode()
                    media_type = "image/png" if photo.type == "image/png" else "image/jpeg"
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
                        columns=["Item Name", "Category", "Cost Basis", "List Price", "Status", "Description", "Notes"]
                    )
                prefill_price = suggested_price if suggested_price else ((lo + hi) / 2 if (lo or hi) else 0)
                ai_category = parsed.get("category", "Other")
                new_item = pd.DataFrame([{
                    "Item Name": parsed.get("itemName", "New Item"),
                    "Category": ai_category if ai_category in CATEGORIES else "Other",
                    "Cost Basis": 0.0,
                    "List Price": prefill_price,
                    "Status": "Available",
                    "Description": parsed.get("reasoning", ""),
                    "Notes": f"AI estimate ({parsed.get('confidence', '?')} confidence): {parsed.get('reasoning', '')}",
                }])
                st.session_state.inventory_by_ws[WORKSPACE] = pd.concat(
                    [st.session_state.inventory_by_ws[WORKSPACE], new_item], ignore_index=True
                )
                st.success("Added to Inventory \u2014 go set the real Cost Basis on the Inventory tab.")
                st.session_state.ai_last_result = None

st.markdown("---")
st.caption("Appraze · built for Estate Auctions / eBay / HiBid / FB Marketplace / Mercari / Chairish / Etsy sourcing")
