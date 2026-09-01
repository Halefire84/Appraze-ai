"""
sheets.py — optional Google Sheets persistence layer for Appraze.

Streamlit Community Cloud's free tier has no built-in database and wipes
st.session_state on every browser refresh and every app restart/redeploy.
For real (even beta) use, losing the deals/inventory/suppliers/customers/
sales log between sessions is a dealbreaker. This backs those five tables
with a Google Sheet instead, authenticating via a Google Cloud service
account rather than asking end users to sign in to Google themselves.

To enable it, set two Streamlit secrets (Settings -> Secrets):
    GOOGLE_SHEET_ID = "the spreadsheet ID from its URL"
    GOOGLE_SERVICE_ACCOUNT_JSON = '''{ ...full service-account JSON key... }'''

Setup, one time, in Google Cloud Console:
    1. Create (or reuse) a Google Cloud project.
    2. Enable the "Google Sheets API" and "Google Drive API" for it.
    3. Create a Service Account, then a JSON key for it - download the key
       file and paste its full contents as the GOOGLE_SERVICE_ACCOUNT_JSON
       secret above.
    4. Create a blank Google Sheet (any name), share it with the service
       account's email (looks like ...@...iam.gserviceaccount.com) as an
       Editor, and put the sheet's ID (the long string in its URL between
       /d/ and /edit) in the GOOGLE_SHEET_ID secret above.
    5. Reload the app. Worksheets (tabs) for each table are created
       automatically inside that spreadsheet on first use.

Every function here takes a `workspace` name (defaulting to "business",
the single-shared-workspace default) and reads/writes a separate worksheet
per workspace+table - see app.py's APP_PASSWORDS multi-tester login mode,
where each isolated tester gets their own workspace and therefore their
own tabs in the one shared spreadsheet, never colliding with each other.

Without those two secrets set, every function below returns None/False and
the app falls back to in-memory session state only - this mirrors the
existing optional-secret pattern already used for STRIPE_SECRET_KEY and
ANTHROPIC_API_KEY, so the app still runs out of the box with no setup.

This module deliberately isn't unit-tested the way finance.py is - it's
all live network/credential I/O, not pure logic. Treat the load/save
functions as untested until exercised against a real spreadsheet.
"""

import json

import pandas as pd
import streamlit as st

try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GSPREAD_AVAILABLE = True
except BaseException:
    # Deliberately broad: a broken/incompatible native dependency in gspread's
    # own import chain (seen in the wild as a Rust-level pyo3_runtime.PanicException
    # from the cryptography package, which is NOT an ImportError) must never be
    # allowed to take down the whole app - persistence just stays disabled.
    _GSPREAD_AVAILABLE = False

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Column order for each persisted table - kept here (not just in app.py) so
# load/save always agree on shape regardless of what changed in the sheet.
TABLE_COLUMNS = {
    "deals": ["Date Added", "Item", "Platform", "Category", "Cost", "Est. Resale Value", "Status", "Notes"],
    "inventory": ["Item Name", "Category", "Cost Basis", "List Price", "Status", "Description", "Notes", "Barcode"],
    "suppliers": [
        "Supplier Name", "Contact Person", "Phone", "Email", "Tier", "Category",
        "First Contact Date", "Last Contact Date", "Relationship Status",
        "Compliance Doc Status", "Value Potential", "Notes",
    ],
    "customers": ["Customer Name", "Phone", "Email", "Segment", "First Visit Date", "Notes"],
    "sales_log": [
        "Invoice #", "Date", "Customer", "Items", "Subtotal", "Tax", "Total",
        "Payment Method", "Status", "Link",
    ],
}

# Sheets stores every cell as text, so numeric columns need coercing back to
# floats after a load - otherwise things like inv_log_df["Total"].sum() end
# up doing string concatenation instead of arithmetic.
NUMERIC_COLUMNS = {
    "deals": ["Cost", "Est. Resale Value"],
    "inventory": ["Cost Basis", "List Price"],
    "suppliers": ["Tier"],
    "customers": [],
    "sales_log": ["Subtotal", "Tax", "Total"],
}


@st.cache_resource(show_spinner=False)
def _get_client():
    if not _GSPREAD_AVAILABLE:
        return None
    creds_raw = None
    try:
        creds_raw = st.secrets.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    except Exception:
        return None
    if not creds_raw:
        return None
    try:
        creds_dict = json.loads(creds_raw) if isinstance(creds_raw, str) else dict(creds_raw)
        creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None


def is_configured() -> bool:
    """True only once both secrets are present and a client was built successfully."""
    try:
        sheet_id = st.secrets.get("GOOGLE_SHEET_ID")
    except Exception:
        sheet_id = None
    return bool(sheet_id) and _get_client() is not None


def _worksheet_title(sheet_name: str, workspace: str) -> str:
    # "business" is the original single-workspace default - kept unprefixed
    # so anyone who already set up a Sheet before multi-workspace support
    # existed doesn't have their tabs silently renamed out from under them.
    # Any other workspace (one of a handful of isolated testers) gets its
    # own suffixed tab so their data never collides with anyone else's.
    if workspace == "business":
        return sheet_name
    return f"{sheet_name}__{workspace}"


def _get_or_create_worksheet(sheet_name: str, workspace: str):
    client = _get_client()
    try:
        sheet_id = st.secrets.get("GOOGLE_SHEET_ID")
    except Exception:
        sheet_id = None
    if client is None or not sheet_id:
        return None
    columns = TABLE_COLUMNS[sheet_name]
    title = _worksheet_title(sheet_name, workspace)
    spreadsheet = client.open_by_key(sheet_id)
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=200, cols=max(len(columns), 10))
        ws.append_row(columns)
        return ws


def load_df(sheet_name: str, workspace: str = "business"):
    """Returns a DataFrame for the given table + workspace, or None if
    Sheets isn't configured/reachable (caller should fall back to local
    defaults)."""
    columns = TABLE_COLUMNS[sheet_name]
    try:
        ws = _get_or_create_worksheet(sheet_name, workspace)
        if ws is None:
            return None
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame(columns=columns)
        df = pd.DataFrame(records)
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        df = df[columns]
        for col in NUMERIC_COLUMNS.get(sheet_name, []):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df
    except Exception:
        return None


def save_df(sheet_name: str, df: pd.DataFrame, workspace: str = "business") -> bool:
    """Overwrites the given table + workspace's worksheet with df's contents.
    Returns True on success."""
    columns = TABLE_COLUMNS[sheet_name]
    try:
        ws = _get_or_create_worksheet(sheet_name, workspace)
        if ws is None:
            return False
        out = df.reindex(columns=columns).fillna("")
        ws.clear()
        ws.update([columns] + out.astype(str).values.tolist())
        return True
    except Exception:
        return False


def sync_table(sheet_name: str, df: pd.DataFrame, workspace: str = "business") -> None:
    """Persists df to Sheets only if it actually changed since the last sync
    this session - avoids hammering the Sheets API on every Streamlit rerun
    (the whole script re-executes on every widget interaction, not just
    edits to this particular table).

    Records success/failure in session_state (see last_sync_failed()) so the
    UI can warn the user instead of silently claiming "synced" while a save
    is actually failing - the whole point of this module is to not lose
    data, so a failed write has to be visible somewhere."""
    if not is_configured():
        return
    cache_key = f"_sheets_synced_{workspace}_{sheet_name}"
    prev = st.session_state.get(cache_key)
    try:
        changed = prev is None or not df.reset_index(drop=True).equals(prev.reset_index(drop=True))
    except Exception:
        changed = True
    if not changed:
        return
    if save_df(sheet_name, df, workspace):
        st.session_state[cache_key] = df.copy()
        st.session_state["_sheets_last_sync_failed"] = False
    else:
        st.session_state["_sheets_last_sync_failed"] = True


def last_sync_failed() -> bool:
    """True if the most recent sync_table() save attempt this session
    actually failed (as opposed to Sheets simply not being configured)."""
    return bool(st.session_state.get("_sheets_last_sync_failed", False))


def mark_synced(sheet_name: str, df: pd.DataFrame, workspace: str = "business") -> None:
    """Records df as already in sync (used right after a fresh load, so we
    don't immediately re-save the data we just read)."""
    st.session_state[f"_sheets_synced_{workspace}_{sheet_name}"] = df.copy()
