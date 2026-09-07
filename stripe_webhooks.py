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

Without webhook handling, invoices stay "Awaiting Payment" forever, and you'd
need manual reconciliation with Stripe dashboard. This automates that.
"""

import hmac
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any


class StripeWebhookError(Exception):
    """Raised when webhook validation or processing fails."""
    pass


def verify_stripe_signature(
    payload: bytes,
    signature_header: str,
    webhook_secret: str,
) -> bool:
    """Verify Stripe webhook signature to ensure request authenticity.
    
    Args:
        payload: Raw request body (bytes, not decoded)
        signature_header: Stripe signature from X-Stripe-Signature header
        webhook_secret: Webhook signing secret from Stripe dashboard
    
    Returns:
        True if signature is valid, False otherwise.
    
    Raises:
        StripeWebhookError: If header format is invalid.
    """
    if not signature_header or not webhook_secret:
        raise StripeWebhookError("Missing signature header or webhook secret")
    
    try:
        # Header format: "t=timestamp,v1=signature"
        parts = {}
        for part in signature_header.split(","):
            key, value = part.split("=", 1)
            parts[key] = value
        
        timestamp = parts.get("t")
        signature = parts.get("v1")
        
        if not timestamp or not signature:
            raise StripeWebhookError("Invalid signature header format")
        
        # Reconstruct signed content: "{timestamp}.{payload}"
        signed_content = f"{timestamp}.{payload.decode('utf-8')}"
        
        # Calculate expected signature
        expected_sig = hmac.new(
            webhook_secret.encode(),
            signed_content.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        # Compare using constant-time comparison (timing-safe)
        return hmac.compare_digest(signature, expected_sig)
    except (ValueError, KeyError) as e:
        raise StripeWebhookError(f"Signature validation failed: {e}")


def handle_charge_succeeded(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle charge.succeeded event from Stripe.
    
    A successful charge means the customer paid. Update the invoice status
    from "Awaiting Payment" to "Paid (Card)".
    
    Args:
        event_data: The "data.object" field from the webhook event.
    
    Returns:
        Update instruction: {"invoice_id": "...", "new_status": "Paid (Card)"}
    
    Raises:
        StripeWebhookError: If required fields are missing.
    """
    if not event_data:
        raise StripeWebhookError("Missing event data")
    
    # Extract payment link ID or order ID from metadata
    metadata = event_data.get("metadata") or {}
    invoice_id = metadata.get("invoice_id") or event_data.get("id")
    
    if not invoice_id:
        raise StripeWebhookError("No invoice_id found in charge metadata")
    
    return {
        "invoice_id": invoice_id,
        "new_status": "Paid (Card)",
        "stripe_charge_id": event_data.get("id"),
        "amount": event_data.get("amount", 0) / 100,  # Stripe uses cents
        "timestamp": datetime.fromtimestamp(event_data.get("created", 0)).isoformat(),
    }


def handle_charge_failed(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle charge.failed event from Stripe.
    
    A failed charge means the payment didn't go through. Leave invoice as
    "Awaiting Payment" but log the failure reason.
    
    Args:
        event_data: The "data.object" field from the webhook event.
    
    Returns:
        Update instruction with failure details.
    
    Raises:
        StripeWebhookError: If required fields are missing.
    """
    if not event_data:
        raise StripeWebhookError("Missing event data")
    
    metadata = event_data.get("metadata") or {}
    invoice_id = metadata.get("invoice_id") or event_data.get("id")
    
    if not invoice_id:
        raise StripeWebhookError("No invoice_id found in charge metadata")
    
    return {
        "invoice_id": invoice_id,
        "new_status": "Payment Failed",  # Intermediate state
        "stripe_charge_id": event_data.get("id"),
        "failure_reason": event_data.get("failure_message", "Unknown"),
        "timestamp": datetime.fromtimestamp(event_data.get("created", 0)).isoformat(),
    }


def handle_charge_refunded(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle charge.refunded event from Stripe.
    
    A refunded charge means the customer got their money back. Update invoice
    to "Refunded" status.
    
    Args:
        event_data: The "data.object" field from the webhook event.
    
    Returns:
        Update instruction with refund details.
    
    Raises:
        StripeWebhookError: If required fields are missing.
    """
    if not event_data:
        raise StripeWebhookError("Missing event data")
    
    metadata = event_data.get("metadata") or {}
    invoice_id = metadata.get("invoice_id") or event_data.get("id")
    
    if not invoice_id:
        raise StripeWebhookError("No invoice_id found in charge metadata")
    
    return {
        "invoice_id": invoice_id,
        "new_status": "Refunded",
        "stripe_charge_id": event_data.get("id"),
        "refund_amount": event_data.get("refunded", 0) / 100,  # Stripe uses cents
        "timestamp": datetime.fromtimestamp(event_data.get("created", 0)).isoformat(),
    }


def process_webhook_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process a Stripe webhook event and return update instruction.
    
    Args:
        event: Parsed webhook event JSON from Stripe.
    
    Returns:
        Update instruction dict, or None if event type is not handled.
    
    Raises:
        StripeWebhookError: If event processing fails.
    """
    event_type = event.get("type")
    event_data = event.get("data", {}).get("object")
    
    if event_type == "charge.succeeded":
        return handle_charge_succeeded(event_data)
    elif event_type == "charge.failed":
        return handle_charge_failed(event_data)
    elif event_type == "charge.refunded":
        return handle_charge_refunded(event_data)
    else:
        # Event type not handled by this module
        return None


def update_invoice_status(
    sales_log: list,
    invoice_id: str,
    new_status: str,
) -> bool:
    """Update the status of an invoice in the sales log.
    
    Args:
        sales_log: List of invoice dicts from session state or database.
        invoice_id: Invoice number to update (e.g. "POS-2026-09-05-1").
        new_status: New status string.
    
    Returns:
        True if invoice was found and updated, False otherwise.
    """
    for invoice in sales_log:
        if invoice.get("Invoice #") == invoice_id or invoice.get("id") == invoice_id:
            invoice["Status"] = new_status
            return True
    return False
