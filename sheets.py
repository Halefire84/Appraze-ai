"""
sheets.py — optional Google Sheets persistence layer for Appraze.

Streamlit Community Cloud's free tier has no built-in database and wipes
st.session_state on every browser refresh and every app restart/redeploy.
For real (even beta) use, losing the deals/inventory/suppliers/customers/
sales log between sessions is a dealbreaker. This backs those five tables
with a Google Sheet instead.

Talks to a small Google Apps Script Web App (see appscript/Code.gs)
deployed from inside the target spreadsheet itself, rather than a Google
Cloud service account. That's a deliberate choice: since May 2024, new
Google Cloud accounts get an "organization" auto-provisioned with a
security baseline that disables service-account key creation by default,
which makes the previously-standard service-account setup a dead end for
a lot of people without a Cloud IAM admin to unblock it (see
appscript/Code.gs's own docstring, and DEPLOY.md, for the full story).
Apps Script needs none of that - it runs with the permissions of whoever
deploys it, using only the Google account that already owns the Sheet.

To enable it, set two Streamlit secrets (Settings -> Secrets):
    APPS_SCRIPT_URL = "the Web app URL Apps Script gives you on deploy"
    APPS_SCRIPT_TOKEN = "the same random string you set as TOKEN in Code.gs"

Setup, one time, no Google Cloud Console involved at all:
    1. Create a blank Google Sheet (any name).
    2. Extensions -> Apps Script. Delete the default code, paste in the
       contents of appscript/Code.gs from this repo.
    3. Change the TOKEN constant near the top to a long random string of
       your own (this is the shared secret between Appraze and this
       script - anyone with both the URL and this token can read/write
       this one spreadsheet, so keep it as private as a password).
    4. Deploy -> New deployment -> gear icon -> Web app. Execute as "Me",
       who has access "Anyone". Deploy, and authorize it when prompted
       (it's your own script acting on your own spreadsheet).
    5. Copy the Web app URL it gives you into the APPS_SCRIPT_URL secret;
       copy the TOKEN you set in step 3 into APPS_SCRIPT_TOKEN.
    6. Reload the app. Worksheets (tabs) for each table are created
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
import urllib.error
import urllib.request

import pandas as pd
import streamlit as st

_REQUEST_TIMEOUT_SECONDS = 20

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


class _PreservePostRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Apps Script Web Apps commonly answer the first hit to a `/exec` URL
    with a 301/302/303 redirect to a script.googleusercontent.com URL that
    actually serves the response. Python's default redirect handling (like
    most HTTP clients, including `requests`) turns a POST into a GET and
    drops the body on those specific codes - which would silently turn
    every load/save into a no-op instead of an error, since the request
    would still "succeed" against the wrong endpoint with no payload. This
    preserves the original method and body across the redirect instead."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if code in (301, 302, 303) and req.get_method() == "POST":
            new_req = urllib.request.Request(newurl, data=req.data, method="POST")
            for key, val in req.header_items():
                new_req.add_header(key, val)
            return new_req
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_PreservePostRedirectHandler)


def _get_config():
    try:
        url = st.secrets.get("APPS_SCRIPT_URL")
        token = st.secrets.get("APPS_SCRIPT_TOKEN")
    except Exception:
        return None, None
    return url, token


def is_configured() -> bool:
    """True only once both secrets are present."""
    url, token = _get_config()
    return bool(url) and bool(token)


def _call(action: str, table: str, workspace: str, rows=None, columns=None):
    """POSTs one request to the Apps Script Web App. Returns the parsed
    {"ok": true, ...} dict on success, or None on any failure (not
    configured, unreachable, timed out, rejected token, malformed
    response) - callers treat None uniformly as "couldn't sync right now,
    fall back to local state" rather than raising."""
    url, token = _get_config()
    if not url or not token:
        return None
    payload = {"token": token, "action": action, "table": table, "workspace": workspace}
    if rows is not None:
        payload["rows"] = rows
    if columns is not None:
        payload["columns"] = columns
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("content-type", "application/json")
        with _opener.open(req, timeout=_REQUEST_TIMEOUT_SECONDS) as resp:
            result = json.loads(resp.read().decode())
        if not isinstance(result, dict) or not result.get("ok"):
            return None
        return result
    except Exception:
        return None


def load_df(sheet_name: str, workspace: str = "business"):
    """Returns a DataFrame for the given table + workspace, or None if
    Sheets isn't configured/reachable (caller should fall back to local
    defaults)."""
    columns = TABLE_COLUMNS[sheet_name]
    result = _call("load", sheet_name, workspace)
    if result is None:
        return None
    try:
        records = result.get("rows") or []
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
        out = df.reindex(columns=columns).fillna("")
        rows = out.astype(str).to_dict("records")
    except Exception:
        return False
    result = _call("save", sheet_name, workspace, rows=rows, columns=columns)
    return result is not None


def sync_table(sheet_name: str, df: pd.DataFrame, workspace: str = "business") -> None:
    """Persists df to Sheets only if it actually changed since the last sync
    this session - avoids hammering the Apps Script endpoint on every
    Streamlit rerun (the whole script re-executes on every widget
    interaction, not just edits to this particular table).

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
