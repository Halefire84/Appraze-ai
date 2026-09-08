"""
webhook_store.py — persistence client for stripe_webhook_server.py.

stripe_webhook_server.py runs as a separate process from the Streamlit app
(Streamlit can't host webhooks), so it has no `st.secrets` or
`st.session_state` to read from — storage.py/auth.py can't be reused as-is
here. This talks to the exact same Apps Script backend
(AppsScript_Code.gs) that storage.py uses, but reads its two config values
from plain OS environment variables instead:

    APPS_SCRIPT_URL   = same value as the Streamlit secret of the same name
    APPS_SCRIPT_TOKEN = same value as the Streamlit secret of the same name

Every row lands in the "sales_log" table under the fixed "admin_shared"
owner key — POS is a single shared cash register for the business, not a
per-tester feature (see pos.py's SALES_LOG_OWNER_KEY), so there's no
per-user identity to resolve here the way storage.py does.

Without those two environment variables set, every function below returns
False/None and the webhook server logs a warning instead of crashing —
the webhook signature is still verified and acknowledged either way, since
that part needs no persistence at all.
"""

import json
import os
from dataclasses import dataclass

import requests

_REQUEST_TIMEOUT_SECONDS = 15
SALES_LOG_TABLE = "sales_log"
OWNER_KEY = "admin_shared"


@dataclass
class WebhookStoreResult:
    success: bool
    payload: object = None  # list of rows for load_sales_log; bool "found" for update_sales_log_status
    error: str = ""


def is_configured() -> bool:
    return bool(os.environ.get("APPS_SCRIPT_URL")) and bool(os.environ.get("APPS_SCRIPT_TOKEN"))


def load_sales_log() -> WebhookStoreResult:
    url = os.environ.get("APPS_SCRIPT_URL")
    token = os.environ.get("APPS_SCRIPT_TOKEN")
    if not url or not token:
        return WebhookStoreResult(False, error="APPS_SCRIPT_URL/APPS_SCRIPT_TOKEN not set in this service's environment.")
    try:
        # POST, not GET - keeps the auth token out of the URL/access logs,
        # same reasoning as storage.py's save_table/load_table.
        resp = requests.post(
            url,
            data={
                "token": token,
                "action": "load_data",
                "table": SALES_LOG_TABLE,
                "is_admin": "true",
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return WebhookStoreResult(False, error=data.get("error", "load failed"))
        raw = data.get("payload")
        return WebhookStoreResult(True, payload=json.loads(raw) if raw else [])
    except Exception as e:
        return WebhookStoreResult(False, error=f"connection error: {e}")


def save_sales_log(rows: list) -> WebhookStoreResult:
    url = os.environ.get("APPS_SCRIPT_URL")
    token = os.environ.get("APPS_SCRIPT_TOKEN")
    if not url or not token:
        return WebhookStoreResult(False, error="APPS_SCRIPT_URL/APPS_SCRIPT_TOKEN not set in this service's environment.")
    try:
        # POST, not GET - the sales log only ever grows (every sale, never
        # truncated), so a GET here was the most likely of all the Apps
        # Script calls in this codebase to eventually exceed a URL length
        # limit and silently stop saving.
        resp = requests.post(
            url,
            data={
                "token": token,
                "action": "save_data",
                "table": SALES_LOG_TABLE,
                "is_admin": "true",
                "payload": json.dumps(rows),
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        return WebhookStoreResult(bool(data.get("success")), error=data.get("error", ""))
    except Exception as e:
        return WebhookStoreResult(False, error=f"connection error: {e}")


def update_sales_log_status(invoice_id: str, new_status: str) -> WebhookStoreResult:
    """
    Atomic single-row update, preferred over load_sales_log() +
    save_sales_log() for reconciling one invoice: those two are separate
    HTTP round trips, so two webhook deliveries arriving close together can
    each load the same stale snapshot and then overwrite each other's
    change when they save the whole table back. This instead asks
    AppsScript_Code.gs's update_sales_log_status action to read, mutate,
    and write the one matching row in a single locked execution server-side
    — there's no window for a second request to race it.

    payload.found tells the caller whether a matching invoice_id existed
    yet (it may not, if the webhook arrives before the POS tab has
    persisted its "Awaiting Payment" row).
    """
    url = os.environ.get("APPS_SCRIPT_URL")
    token = os.environ.get("APPS_SCRIPT_TOKEN")
    if not url or not token:
        return WebhookStoreResult(False, error="APPS_SCRIPT_URL/APPS_SCRIPT_TOKEN not set in this service's environment.")
    try:
        resp = requests.post(
            url,
            data={
                "token": token,
                "action": "update_sales_log_status",
                "invoice_id": invoice_id,
                "new_status": new_status,
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            return WebhookStoreResult(False, error=data.get("error", "update failed"))
        return WebhookStoreResult(True, payload=data.get("found"))
    except Exception as e:
        return WebhookStoreResult(False, error=f"connection error: {e}")
