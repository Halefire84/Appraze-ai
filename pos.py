"""
Cooper River Trading Co. — Appraze POS Checkout
----------------------------------------------------
Different from billing.py's subscriber paywall on purpose: that one uses a
fixed-price Payment Link (same price every time, for app access). A POS
sale is a DIFFERENT dollar amount every single time, so a single static
Payment Link can't cover it — this creates a one-off Stripe Checkout
Session per sale instead, with the amount set at creation time.

Still zero card handling in this app: the customer is redirected to a
Stripe-hosted page and enters their own card there, exactly like a
Payment Link. Same security model, just via the API endpoint that
supports a dynamic amount rather than one pre-made fixed price.
"""

import secrets as _secrets
from dataclasses import dataclass
from datetime import date

import requests
import streamlit as st

from billing import verify_checkout_session  # reuse the same read-only status check

# Every POS sale is tagged with this owner key when persisted to the
# "sales_log" table, regardless of which login created it — POS is a single
# shared cash register for the business, not a per-tester feature (matching
# storage.py's existing "admins share one workspace" model). The stand-alone
# Stripe webhook service (stripe_webhook_server.py) writes to this exact
# same key when it reconciles a payment, so both paths land in one place.
SALES_LOG_OWNER_KEY = "admin_shared"


def _secret_key() -> str:
    key = st.secrets.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY is not set in Streamlit secrets.")
    return key


def _new_invoice_id() -> str:
    return f"POS-{date.today().isoformat()}-{_secrets.token_hex(3)}"


@dataclass
class POSCheckoutResult:
    success: bool
    checkout_url: str = ""
    session_id: str = ""
    invoice_id: str = ""
    error: str = ""


def create_pos_checkout(amount_dollars: float, description: str, customer_email: str = "") -> POSCheckoutResult:
    """
    Creates a one-off Stripe-hosted checkout page for a specific sale amount.
    Returns the URL to show/send to the customer (or open on a shared device
    for a tap-to-pay-style in-person handoff), plus an invoice_id that's
    embedded in the Checkout Session's metadata — the Stripe webhook service
    reads that metadata back off the charge event to know which sales_log
    row to mark paid, since the webhook has no access to this app's session
    state (it runs as a separate process).
    """
    if amount_dollars <= 0:
        return POSCheckoutResult(False, error="Amount must be greater than $0.")

    invoice_id = _new_invoice_id()
    app_url = st.secrets.get("APP_URL", "").rstrip("/")
    # These redirect URLs are mostly a nice-to-have: if APP_URL is set and the
    # SAME device completes payment (e.g. handed to the customer and back),
    # the app will land back here automatically. Either way, the "Check
    # Payment Status" button in the POS tab works regardless of device.
    success_url = f"{app_url}/?pos_session_id={{CHECKOUT_SESSION_ID}}" if app_url else "https://example.com/?pos_paid=1"
    cancel_url = f"{app_url}/" if app_url else "https://example.com/?pos_cancelled=1"

    try:
        amount_cents = int(round(amount_dollars * 100))
        payload = {
            "mode": "payment",
            "line_items[0][quantity]": 1,
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": amount_cents,
            "line_items[0][price_data][product_data][name]": description or "Cooper River Trading Co. item",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "payment_intent_data[metadata][invoice_id]": invoice_id,
            "payment_intent_data[metadata][owner_key]": SALES_LOG_OWNER_KEY,
        }
        if customer_email:
            payload["customer_email"] = customer_email

        resp = requests.post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers={"Authorization": f"Bearer {_secret_key()}"},
            data=payload,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return POSCheckoutResult(True, checkout_url=data["url"], session_id=data["id"], invoice_id=invoice_id)
    except requests.exceptions.HTTPError as e:
        detail = e.response.text[:200] if e.response is not None else str(e)
        return POSCheckoutResult(False, error=f"Stripe error: {detail}")
    except Exception as e:
        return POSCheckoutResult(False, error=f"connection error: {e}")


def check_payment_status(session_id: str) -> bool:
    """Read-only poll — call whenever the admin wants to confirm a pending sale paid."""
    return verify_checkout_session(session_id).paid
