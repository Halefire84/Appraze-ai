"""
stripe_webhooks.py — Stripe webhook handlers for payment status updates.

Listens for Stripe events (charge.succeeded, charge.failed, charge.refunded)
and updates invoice status in the sales log accordingly. This bridges the gap
between POS-created "Awaiting Payment" invoices and actual payment resolution.

Setup (one-time):
    1. Go to Stripe Dashboard → Developers → Webhooks
    2. Create endpoint pointing to: https://your-app-url/stripe/webhook
    3. Select events: charge.succeeded, charge.failed, charge.refunded
    4. Copy the signing secret and add it to Streamlit Secrets:
       STRIPE_WEBHOOK_SECRET = "whsec_xxxxx"
    5. Also update STRIPE_WEBHOOK_URL in Secrets to match your endpoint:
       STRIPE_WEBHOOK_URL = "https://your-streamlit-app-url/stripe/webhook"

This module is designed to be deployed as a separate FastAPI service
(not inside Streamlit), since Streamlit can't host webhooks natively.
See stripe_webhook_server.py for the FastAPI wrapper.

Production requirements enforced here (2026-09-19 P0 hardening pass):
  - Timestamp tolerance (replay protection) — a captured valid signature
    can't be replayed indefinitely.
  - Accept ANY valid v1 signature in the header, not just the first/last —
    Stripe sends multiple during a signing-secret rotation window.
  - Controlled rejection of malformed / non-ASCII headers (a
    StripeWebhookError, never an unhandled TypeError or 500).
  - Refund amount comes from amount_refunded (actual cents), never the
    boolean `refunded` field treated as a dollar amount.
  - Status precedence so a delayed/out-of-order event can never downgrade
    a more-final status (e.g. a late "Paid" can't overwrite "Refunded").
  - Idempotent application via event_id when a caller tracks seen events.

Status precedence (highest wins):
  Refunded > Partially Refunded > Paid (Card) > Payment Failed > Awaiting Payment
"""

from __future__ import annotations

import hmac
import hashlib
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

# Stripe's own recommended replay-attack tolerance (5 minutes). A signature
# alone doesn't prove freshness -- an attacker who captures one legitimate
# request+signature off the wire (a compromised proxy log, a misconfigured
# tunnel) could otherwise replay it indefinitely and it would still verify.
DEFAULT_TIMESTAMP_TOLERANCE_SEC = 300

# Every status this module or its callers can set an invoice to, ranked so
# update_invoice_status() can refuse to move an invoice backwards (a
# "charge.succeeded" that arrives after its own refund must not resurrect
# "Paid (Card)" over "Refunded").
STATUS_RANK = {
    "Awaiting Payment": 0,
    "Failed": 1,
    "Payment Failed": 1,
    "Paid": 2,
    "Paid (Card)": 2,
    "Partially Refunded": 3,
    "Refunded": 4,
}


class StripeWebhookError(Exception):
    """Raised when webhook validation or processing fails."""
    pass


def _parse_signature_header(signature_header: str):
    """Parse a Stripe-Signature header into (timestamp, [v1 signatures]).

    Stripe's header format is "t=<timestamp>,v1=<sig>[,v1=<sig>...]" — more
    than one v1 value appears during a signing-secret rotation window (the
    endpoint is briefly signed with both the old and new secret), so every
    v1 value must be collected and checked, not just the first or last.
    """
    if not signature_header or not isinstance(signature_header, str):
        raise StripeWebhookError("Missing or non-string signature header")

    try:
        signature_header.encode("ascii")
    except UnicodeEncodeError as e:
        raise StripeWebhookError(f"Non-ASCII characters in signature header: {e}") from e

    timestamp = None
    v1_sigs = []
    try:
        for part in signature_header.split(","):
            part = part.strip()
            if not part or "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "t":
                timestamp = value
            elif key == "v1":
                v1_sigs.append(value)
    except (ValueError, AttributeError) as e:
        raise StripeWebhookError(f"Invalid signature header format: {e}") from e

    if not timestamp or not v1_sigs:
        raise StripeWebhookError("Invalid signature header format: missing t= or v1=")
    return timestamp, v1_sigs


def verify_stripe_signature(
    payload,
    signature_header: str,
    webhook_secret: str,
    *,
    tolerance_sec: int = DEFAULT_TIMESTAMP_TOLERANCE_SEC,
    now: Optional[float] = None,
) -> bool:
    """Verify a Stripe webhook signature: authenticity AND freshness.

    Args:
        payload: Raw request body (bytes or str, not JSON-decoded)
        signature_header: Stripe-Signature header value
        webhook_secret: Webhook signing secret from the Stripe dashboard
        tolerance_sec: Maximum age (seconds) a signed timestamp may have
            before it's rejected as a possible replay. Pass 0 to disable
            (not recommended in production).
        now: Injectable current time (unix seconds) for deterministic tests.

    Returns:
        True if the signature matches AND the timestamp is within
        tolerance. False only for a plain signature mismatch.

    Raises:
        StripeWebhookError: missing secret/payload, malformed or
            non-ASCII header, or a stale/future timestamp outside
            tolerance (a stale timestamp is treated as a validation
            failure, not merely "invalid", since it's a possible replay).
    """
    if not webhook_secret:
        raise StripeWebhookError("Missing webhook secret")
    if payload is None:
        raise StripeWebhookError("Missing payload")

    timestamp_str, v1_sigs = _parse_signature_header(signature_header)

    try:
        ts = int(timestamp_str)
    except (TypeError, ValueError) as e:
        raise StripeWebhookError(f"Invalid timestamp in signature header: {e}") from e

    if tolerance_sec > 0:
        current = time.time() if now is None else float(now)
        if abs(current - ts) > tolerance_sec:
            raise StripeWebhookError(
                f"Timestamp outside tolerance ({tolerance_sec}s): event_ts={ts}, now={int(current)}"
            )

    payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
    signed_content = f"{timestamp_str}.".encode("utf-8") + payload_bytes
    expected_sig = hmac.new(
        webhook_secret.encode("utf-8") if isinstance(webhook_secret, str) else webhook_secret,
        signed_content,
        hashlib.sha256,
    ).hexdigest()

    for sig in v1_sigs:
        try:
            if hmac.compare_digest(sig, expected_sig):
                return True
        except (TypeError, ValueError):
            continue

    return False


def handle_charge_succeeded(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle charge.succeeded: move an invoice from "Awaiting Payment" to "Paid (Card)"."""
    if not event_data:
        raise StripeWebhookError("Missing event data")

    metadata = event_data.get("metadata") or {}
    invoice_id = metadata.get("invoice_id") or event_data.get("id")
    if not invoice_id:
        raise StripeWebhookError("No invoice_id found in charge metadata")

    return {
        "invoice_id": invoice_id,
        "new_status": "Paid (Card)",
        "stripe_charge_id": event_data.get("id"),
        "amount": (event_data.get("amount") or 0) / 100,  # Stripe uses cents
        "timestamp": datetime.fromtimestamp(event_data.get("created", 0)).isoformat(),
        "event_kind": "charge.succeeded",
    }


def handle_charge_failed(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle charge.failed: leave the invoice "Awaiting Payment" but log why it failed."""
    if not event_data:
        raise StripeWebhookError("Missing event data")

    metadata = event_data.get("metadata") or {}
    invoice_id = metadata.get("invoice_id") or event_data.get("id")
    if not invoice_id:
        raise StripeWebhookError("No invoice_id found in charge metadata")

    return {
        "invoice_id": invoice_id,
        "new_status": "Payment Failed",
        "stripe_charge_id": event_data.get("id"),
        "failure_reason": event_data.get("failure_message") or event_data.get("failure_code") or "Unknown",
        "timestamp": datetime.fromtimestamp(event_data.get("created", 0)).isoformat(),
        "event_kind": "charge.failed",
    }


def handle_charge_refunded(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle charge.refunded, distinguishing a full refund from a partial one.

    Uses amount_refunded (the actual refunded amount, in cents) rather than
    the `refunded` field, which is a BOOLEAN ("was this charge ever
    refunded at all", true even for a $0.01 partial refund) -- treating
    that boolean as a dollar amount would report every refund, partial or
    full, as the charge's full original amount.
    """
    if not event_data:
        raise StripeWebhookError("Missing event data")

    metadata = event_data.get("metadata") or {}
    invoice_id = metadata.get("invoice_id") or event_data.get("id")
    if not invoice_id:
        raise StripeWebhookError("No invoice_id found in charge metadata")

    amount_refunded_cents = event_data.get("amount_refunded")
    if amount_refunded_cents is None:
        amount_refunded_cents = 0
    try:
        refund_amount = float(amount_refunded_cents) / 100.0
    except (TypeError, ValueError):
        refund_amount = 0.0

    charge_amount_cents = event_data.get("amount") or 0
    try:
        charge_amount = float(charge_amount_cents) / 100.0
    except (TypeError, ValueError):
        charge_amount = 0.0

    if charge_amount > 0 and 0 < refund_amount < charge_amount - 0.001:
        new_status = "Partially Refunded"
    else:
        new_status = "Refunded"

    return {
        "invoice_id": invoice_id,
        "new_status": new_status,
        "stripe_charge_id": event_data.get("id"),
        "refund_amount": round(refund_amount, 2),
        "charge_amount": round(charge_amount, 2),
        "timestamp": datetime.fromtimestamp(event_data.get("created", 0)).isoformat(),
        "event_kind": "charge.refunded",
    }


def process_webhook_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process a Stripe webhook event and return an update instruction.

    Returns None for event types this module doesn't act on (Stripe only
    needs a 2xx to stop retrying those; there's nothing to persist).
    """
    event_type = event.get("type")
    event_data = event.get("data", {}).get("object")
    event_id = event.get("id")

    if event_type == "charge.succeeded":
        result = handle_charge_succeeded(event_data)
    elif event_type == "charge.failed":
        result = handle_charge_failed(event_data)
    elif event_type == "charge.refunded":
        result = handle_charge_refunded(event_data)
    else:
        return None

    if event_id:
        result["event_id"] = event_id
    return result


def status_rank(status: Optional[str]) -> int:
    """Unrecognized/missing statuses rank below everything (-1), so a known
    status always outranks "no status yet" without needing a special case."""
    if not status:
        return -1
    return STATUS_RANK.get(status, -1)


def can_transition(current_status: Optional[str], new_status: str) -> bool:
    """True if moving from current_status to new_status is not a downgrade."""
    return status_rank(new_status) >= status_rank(current_status)


def update_invoice_status(
    sales_log: list,
    invoice_id: str,
    new_status: str,
    *,
    event_id: Optional[str] = None,
    seen_event_ids: Optional[Set[str]] = None,
    force: bool = False,
) -> bool:
    """Update one invoice's status in the sales log.

    Args:
        sales_log: List of invoice dicts from session state or a database.
        invoice_id: Invoice number to update (e.g. "POS-2026-09-05-1").
        new_status: New status string.
        event_id: Stripe event id, for idempotent replay handling — if
            seen_event_ids is also given and already contains this id,
            the update is skipped (Stripe guarantees at-least-once
            delivery, so the same event can arrive more than once).
        seen_event_ids: Caller-owned set of already-applied event ids.
        force: Bypass the status-precedence check (an explicit manual
            override, never used by the automatic webhook path).

    Returns:
        True if the invoice was found AND the status was actually applied
        (found but a downgrade, or a duplicate event_id, both return False
        without raising -- a rejected transition is not an error).
    """
    if event_id and seen_event_ids is not None:
        if event_id in seen_event_ids:
            return False
        seen_event_ids.add(event_id)

    for invoice in sales_log:
        if invoice.get("Invoice #") == invoice_id or invoice.get("id") == invoice_id:
            current = invoice.get("Status")
            if force or can_transition(current, new_status):
                invoice["Status"] = new_status
                return True
            return False
    return False
