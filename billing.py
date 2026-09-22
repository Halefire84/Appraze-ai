"""
Cooper River Trading Co. — Appraze Billing

verify_checkout_session() is wired in indirectly via pos.py's
check_payment_status() as of 2026-09-20 (pos.py is now used by app.py's
"Charge Customer" tab) — it's a generic read-only Checkout Session status
check that works for any session regardless of how it was created, not
only ones a Payment Link produced. The subscriber-paywall flow described
below (payment_link_url() + a Payment-Link-driven redirect back into the
app) is still not wired into app.py — app.py has no paywall/subscription
gating anywhere (grepped for "paywall", "subscription", "is_paid" — zero
hits in app.py). That part of this module remains unused.
---------------------------------------------
Deliberately uses Stripe PAYMENT LINKS, not the Checkout Sessions API or any
card element — consistent with CRTC's "Stripe Payment Links only, no raw
card handling" rule. This module does NOT create checkout sessions; it only
verifies one after the fact.

Flow:
  1. The Payment Link itself is created once, by hand, in the Stripe Dashboard
     (test mode for beta, live mode when selling for real). Its URL goes in
     Streamlit secrets as STRIPE_PAYMENT_LINK_URL.
  2. In that Payment Link's settings, "After payment" is set to redirect to
     this app's URL with ?session_id={CHECKOUT_SESSION_ID} appended — Stripe
     fills in the real session id automatically.
  3. When the browser lands back on the app with that session_id in the URL,
     this module makes a read-only GET to Stripe to confirm payment_status,
     using the secret key. No card data ever touches this app.
"""

from dataclasses import dataclass

import requests
import streamlit as st


@dataclass
class BillingResult:
    paid: bool
    customer_email: str = ""
    error: str = ""


def _secret_key() -> str:
    key = st.secrets.get("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY is not set in Streamlit secrets.")
    return key


def payment_link_url() -> str:
    return st.secrets.get("STRIPE_PAYMENT_LINK_URL", "")


def plan_payment_link(plan_key: str) -> str:
    """Per-plan Stripe Payment Link for the Pricing page's subscribe buttons,
    e.g. STRIPE_PAYMENT_LINK_APPRAISER for the "appraiser" plan. Each
    Payment Link is created by hand in the Stripe Dashboard (test mode for
    beta, live mode when selling for real) with its own price and its own
    "after payment" redirect set to
    f"{APP_URL}/?sub_plan={plan_key}&sub_session_id={{CHECKOUT_SESSION_ID}}"
    -- see DEPLOY.md. Returns "" (falsy) when that plan's link isn't
    configured yet, so the Pricing page can fail safe to a
    "not yet available" state instead of a broken button."""
    return st.secrets.get(f"STRIPE_PAYMENT_LINK_{plan_key.upper()}", "")


def verify_checkout_session(session_id: str) -> BillingResult:
    """
    Read-only lookup — confirms whether a given Checkout Session (created by
    a Payment Link) actually completed payment. Safe to call repeatedly.
    """
    try:
        resp = requests.get(
            f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
            headers={"Authorization": f"Bearer {_secret_key()}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        paid = data.get("payment_status") == "paid"
        email = (data.get("customer_details") or {}).get("email", "")
        return BillingResult(paid=paid, customer_email=email)
    except requests.exceptions.HTTPError as e:
        return BillingResult(paid=False, error=f"Stripe error: {e.response.status_code}")
    except Exception as e:
        return BillingResult(paid=False, error=f"connection error: {e}")
