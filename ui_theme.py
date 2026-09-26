"""
Appraze shared visual theme -- one CSS injection every page calls.

Streamlit multipage apps only run app.py's top-level code when the user's
session starts on app.py itself; a page opened directly (a bookmark, a
shared link, a fresh tab landing on pages/8_Pricing.py) never executes
app.py at all, so styling injected only there silently doesn't apply.
This module exists so every page gets the same brand (Fraunces/IBM Plex
Sans, hidden Streamlit chrome, gold primary buttons, card/tab styling)
regardless of which page a session actually starts on -- call
inject_theme() right after st.set_page_config() on every page, same as
require_auth().
"""

import streamlit as st

APPRAZE_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

    /* ---- hide Streamlit's own chrome -- belt-and-suspenders alongside
       .streamlit/config.toml's toolbarMode="minimal"; this is what makes
       the app read as "someone's dev tool" instead of a finished program. */
    #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; height: 0; }

    html, body, .stApp, [class*="css"] { font-family: "IBM Plex Sans", -apple-system, "Segoe UI", sans-serif; }
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: #d7e0ea; border-radius: 8px; }
    ::-webkit-scrollbar-thumb:hover { background: #b7c4d6; }

    .appraze-brand img { width: 100%; max-width: 210px; display: block; margin: 0 auto 14px; }
    .appraze-brand { padding: 6px 0 4px; }
    .appraze-header { display: flex; align-items: center; gap: 12px; margin: 4px 0 0; }
    .appraze-header img { width: 40px; height: 40px; border-radius: 9px; }
    .appraze-header h2 { margin: 0 !important; font-size: 1.8rem !important; }
    /* ---- base ---- */
    .stApp {
        background: linear-gradient(180deg, #ffffff 0%, #f5f8fc 100%);
        color: #172230;
    }
    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #d9e1ea;
    }
    h1, h2, h3, h4 {
        color: #172230 !important;
        letter-spacing: -0.01em;
        font-family: "Fraunces", Georgia, serif !important;
        font-weight: 600 !important;
    }

    /* ---- tabs: a quieter, pill-style segmented control instead of
       Streamlit's default underline-tab look ---- */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #e6e9ef; }
    .stTabs [data-baseweb="tab"] {
        height: 40px; border-radius: 8px 8px 0 0; padding: 0 16px;
        color: #5d6b7a; font-weight: 600;
    }
    .stTabs [aria-selected="true"] { color: #0b2548 !important; background: #f5f8fc; }

    /* ---- KPI cards ---- */
    .kpi-card {
        background: linear-gradient(145deg, #ffffff, #f3f6fa);
        border: 1px solid #d7e0ea;
        border-radius: 14px;
        padding: 18px 20px;
        box-shadow: 0 4px 18px rgba(31,52,73,0.10);
    }
    .kpi-label {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #5d6b7a;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #172230;
    }
    .kpi-sub { font-size: 0.8rem; color: #16804b; margin-top: 2px; }
    .kpi-sub.neg { color: #c62f4a; }

    /* ---- price display (pricing tiers) -- deliberately NOT a raw
       markdown heading: Fraunces' glyph metrics wrap "$19/mo" mid-word
       inside a narrow st.columns() cell at heading size. ---- */
    .price-amount {
        font-family: "Fraunces", Georgia, serif;
        font-weight: 600;
        font-size: 1.9rem;
        white-space: nowrap;
        color: #172230;
        margin: 4px 0;
    }

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
    .badge-hot { background: #37260f; color: #f5a524; border: 1px solid #f5a52440;}
    .badge-good { background: #0f2e22; color: #22c98c; border: 1px solid #22c98c40;}
    .badge-pass { background: #2b1418; color: #f2607a; border: 1px solid #f2607a40;}

    /* buttons */
    .stButton>button, .stLinkButton>a, .stDownloadButton>button {
        border-radius: 10px;
        border: 1px solid #cbd5e1;
        background: #ffffff;
        color: #0b2548;
        font-weight: 600;
        transition: border-color 120ms ease, transform 120ms ease;
    }
    .stButton>button:hover, .stLinkButton>a:hover, .stDownloadButton>button:hover {
        border-color: #0b2548; color: #0b2548;
    }
    .stButton>button:active { transform: scale(0.98); }
    /* primary CTA buttons (type="primary") get the brand gold, not
       Streamlit's default red -- this is what a "RUN ACQUISITION
       VERDICT" or "Subscribe" button should look like on a paid product. */
    .stButton>button[kind="primary"], .stLinkButton>a[kind="primary"] {
        background: linear-gradient(180deg, #f7b64a, #f5a524);
        border: 1px solid #d68d0f;
        color: #2b1a00;
        box-shadow: 0 2px 8px rgba(245,165,36,0.35);
    }
    .stButton>button[kind="primary"]:hover, .stLinkButton>a[kind="primary"]:hover {
        border-color: #b9790a; color: #1a0f00;
        box-shadow: 0 4px 14px rgba(245,165,36,0.45);
    }

    /* dataframe */
    div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

    /* metric containers spacing */
    .block-container { padding-top: 1.6rem; }

    hr { border-color: #d7e0ea; }
</style>
"""


def inject_theme() -> None:
    """Call once, right after st.set_page_config(), on every page."""
    st.markdown(APPRAZE_CSS, unsafe_allow_html=True)
