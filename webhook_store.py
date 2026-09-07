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
    payload: list = None
    error: str = ""


def is_configured() -> bool:
    return bool(os.environ.get("APPS_SCRIPT_URL")) and bool(os.environ.get("APPS_SCRIPT_TOKEN"))


def load_sales_log() -> WebhookStoreResult:
    url = os.environ.get("APPS_SCRIPT_URL")
    token = os.environ.get("APPS_SCRIPT_TOKEN")
    if not url or not token:
        return WebhookStoreResult(False, error="APPS_SCRIPT_URL/APPS_SCRIPT_TOKEN not set in this service's environment.")
    try:
        resp = requests.get(
            url,
            params={
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
        resp = requests.get(
            url,
            params={
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
