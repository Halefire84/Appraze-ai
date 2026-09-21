"""Server-side usage gate and accounting for Appraze's platform-managed AI.

The Anthropic credential is never passed to this module or returned to the
browser. Apps Script owns the per-account quota state so Streamlit reruns and
separate browser sessions cannot reset a user's allowance.

Current beta policy:
- Paid customer: 100 successful AI calls/month, 10 successful calls/day.
- Admin/owner: 500 successful AI calls/month, 25 successful calls/day.
- 15-minute stale reservations are automatically released by the backend.
- Usage is tracked with actual Anthropic input/output tokens and estimated USD.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import requests
import streamlit as st

AI_MODEL = "claude-sonnet-5"
INPUT_USD_PER_MTOK = 2.0
OUTPUT_USD_PER_MTOK = 10.0
MAX_IMAGE_BYTES = 3_000_000
MAX_DESCRIPTION_CHARS = 2_000
REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class UsageDecision:
    allowed: bool
    reason: str = ""
    monthly_used: int = 0
    monthly_limit: int = 0
    daily_used: int = 0
    daily_limit: int = 0
    monthly_cost_usd: float = 0.0


def _secret(key: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(key, default))
    except Exception:
        return default


def _post(action: str, **fields) -> dict:
    url = _secret("APPS_SCRIPT_URL").strip()
    token = _secret("APPS_SCRIPT_TOKEN").strip()
    if not url or not token:
        return {"success": False, "error": "usage service not configured"}
    payload = {"token": token, "action": action, **fields}
    response = requests.post(url, data=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {"success": False, "error": "invalid usage response"}


def reserve_ai_call(username: str) -> UsageDecision:
    """Atomically reserve one AI call before contacting Anthropic.

    A failed reservation means no provider request should be made.
    """
    if not username.strip():
        return UsageDecision(False, "account identity is unavailable")
    try:
        data = _post("reserve_ai_usage", username=username.strip().lower())
    except Exception:
        return UsageDecision(False, "AI usage service is temporarily unavailable")
    if not data.get("success"):
        return UsageDecision(
            False,
            str(data.get("error", "AI usage limit reached")),
            int(data.get("monthly_used", 0) or 0),
            int(data.get("monthly_limit", 0) or 0),
            int(data.get("daily_used", 0) or 0),
            int(data.get("daily_limit", 0) or 0),
            float(data.get("monthly_cost_usd", 0) or 0),
        )
    return UsageDecision(
        True,
        monthly_used=int(data.get("monthly_used", 0) or 0),
        monthly_limit=int(data.get("monthly_limit", 0) or 0),
        daily_used=int(data.get("daily_used", 0) or 0),
        daily_limit=int(data.get("daily_limit", 0) or 0),
        monthly_cost_usd=float(data.get("monthly_cost_usd", 0) or 0),
    )


def finalize_ai_call(username: str, input_tokens: int, output_tokens: int) -> dict:
    """Commit actual provider usage after a successful Anthropic response."""
    input_tokens = max(0, int(input_tokens or 0))
    output_tokens = max(0, int(output_tokens or 0))
    cost = (
        (input_tokens / 1_000_000) * INPUT_USD_PER_MTOK
        + (output_tokens / 1_000_000) * OUTPUT_USD_PER_MTOK
    )
    try:
        return _post(
            "finalize_ai_usage",
            username=username.strip().lower(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=f"{cost:.8f}",
        )
    except Exception:
        # The provider call already happened. Never turn an accounting outage
        # into a second provider call or expose credentials to recover it.
        return {"success": False, "error": "usage accounting temporarily unavailable"}


def release_ai_call(username: str) -> dict:
    """Release a reservation when no provider request was successfully billed."""
    try:
        return _post("release_ai_usage", username=username.strip().lower())
    except Exception:
        return {"success": False, "error": "usage accounting temporarily unavailable"}


def usage_summary(username: str) -> dict:
    """Return the current server-side usage summary for an authenticated user."""
    try:
        return _post("get_ai_usage", username=username.strip().lower())
    except Exception:
        return {"success": False, "error": "usage service temporarily unavailable"}
