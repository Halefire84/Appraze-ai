"""
telemetry.py — best-effort diagnostic logging to the shared event_log
table (see AppsScript_Code.gs::handleLogEvent_).

This is for operator visibility (errors, financial-decision/payment
events), NOT a system of record. It must never affect the caller's
control flow: log_event()/log_event_standalone() catch everything and
return silently on failure, and use a short timeout so a flaky/
misconfigured backend can't slow down a user-facing action. Durable
financial records still live in their own tables (sales_log, AIUsage)
with their own precedence/idempotency rules; this module never
substitutes for those.

Usage:
    from telemetry import log_event
    log_event("ERROR", "webhook", "stripe_webhook_server", "signature check failed", {"detail": str(e)})
    log_event("INFO", "decision", "deal_workspace", "evaluated deal", {"decision": d.decision})
"""

import json
import os
from typing import Any, Optional

import requests

_REQUEST_TIMEOUT_SECONDS = 5  # deliberately short -- logging must never block a real action


def _payload(level: str, event_type: str, source: str, message: str, context: Optional[dict]) -> dict:
    return {
        "action": "log_event",
        "level": level,
        "event_type": event_type,
        "source": source,
        "message": message,
        "context": json.dumps(context or {}, default=str),
    }


def log_event(level: str, event_type: str, source: str, message: str, context: Optional[dict] = None) -> None:
    """Best-effort append to the shared event_log table, for callers running
    inside the Streamlit app (reads APPS_SCRIPT_URL/TOKEN from st.secrets
    via auth.py). Never raises."""
    try:
        from auth import _apps_script_url, _token

        url = _apps_script_url()
        token = _token()
        if not url or not token:
            return  # backend not configured -- silently a no-op, same convention as storage.py
        data = _payload(level, event_type, source, message, context)
        data["token"] = token
        requests.post(url, data=data, timeout=_REQUEST_TIMEOUT_SECONDS)
    except Exception:
        pass  # logging failures are never allowed to surface to the caller


def log_event_standalone(level: str, event_type: str, source: str, message: str, context: Optional[dict] = None) -> None:
    """Same as log_event(), but for callers outside the Streamlit app
    (e.g. stripe_webhook_server.py) that read APPS_SCRIPT_URL/TOKEN from
    plain OS environment variables instead of st.secrets, matching
    webhook_store.py's convention. Never raises."""
    try:
        url = os.environ.get("APPS_SCRIPT_URL")
        token = os.environ.get("APPS_SCRIPT_TOKEN")
        if not url or not token:
            return
        data = _payload(level, event_type, source, message, context)
        data["token"] = token
        requests.post(url, data=data, timeout=_REQUEST_TIMEOUT_SECONDS)
    except Exception:
        pass


def load_recent_events(limit: int = 100) -> Any:
    """Read-only fetch of the most recent logged events, newest first.
    Returns a list of dicts, or [] if unavailable -- never raises."""
    try:
        from storage import load_table

        result = load_table("event_log", shared=True)
        if not result.success or not result.payload:
            return []
        rows = list(result.payload)
        rows.reverse()
        return rows[:limit]
    except Exception:
        return []
