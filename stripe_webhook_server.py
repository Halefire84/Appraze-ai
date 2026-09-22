"""
stripe_webhook_server.py — small standalone FastAPI service that receives
Stripe webhook events and reconciles POS sales automatically, so a sale
made on the customer's own device (or one nobody remembered to click
"Check Status" on) still lands as "Paid (Card)" in the sales_log without
manual polling.

This is deliberately NOT part of the Streamlit app — Streamlit apps can't
receive inbound webhooks. Run this as its own tiny service (any host that
can run a Python web app works: Replit, Render, Fly.io, a VPS, etc.).

Environment variables it needs:
    STRIPE_WEBHOOK_SECRET   the signing secret Stripe gives you for this
                            endpoint (Stripe Dashboard -> Developers ->
                            Webhooks -> your endpoint -> "Signing secret")
    APPS_SCRIPT_URL         same value as the Streamlit secret of the same
                            name (see webhook_store.py) — optional; without
                            it, events are verified and acknowledged but
                            not persisted anywhere.
    APPS_SCRIPT_TOKEN       same value as the Streamlit secret of the same
                            name — optional, same caveat as above.

Run locally:
    pip install -r requirements-webhook.txt
    STRIPE_WEBHOOK_SECRET=whsec_... uvicorn stripe_webhook_server:app --port 8000

Stripe Dashboard setup (Developers -> Webhooks -> Add endpoint):
    Endpoint URL: https://<wherever-this-is-hosted>/stripe/webhook
    Events to send: charge.succeeded, charge.failed, charge.refunded
"""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from stripe_webhooks import StripeWebhookError, process_webhook_event, verify_stripe_signature
from webhook_store import update_sales_log_status
from telemetry import log_event_standalone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stripe_webhook_server")

app = FastAPI(title="Appraze Stripe Webhook Receiver")


@app.get("/")
@app.get("/healthz")
def health():
    """Lets a hosting platform's health check confirm the service is up
    without needing a Stripe signature."""
    return {"ok": True, "service": "appraze-stripe-webhook"}


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    payload = await request.body()
    signature_header = request.headers.get("stripe-signature", "")

    try:
        valid = verify_stripe_signature(payload, signature_header, webhook_secret)
    except StripeWebhookError as e:
        logger.warning("Webhook signature check failed: %s", e)
        log_event_standalone("WARNING", "webhook", "stripe_webhook_server", "signature check failed", {"error": str(e)})
        return JSONResponse(status_code=400, content={"error": str(e)})

    if not valid:
        logger.warning("Webhook signature did not match — rejecting.")
        log_event_standalone("WARNING", "webhook", "stripe_webhook_server", "signature did not match")
        return JSONResponse(status_code=400, content={"error": "invalid signature"})

    try:
        event = await request.json()
    except Exception:
        log_event_standalone("ERROR", "webhook", "stripe_webhook_server", "malformed JSON body")
        return JSONResponse(status_code=400, content={"error": "malformed JSON body"})

    try:
        update = process_webhook_event(event)
    except StripeWebhookError as e:
        logger.warning("Event processing failed: %s", e)
        log_event_standalone("ERROR", "webhook", "stripe_webhook_server", "event processing failed", {"error": str(e), "event_type": event.get("type")})
        return JSONResponse(status_code=400, content={"error": str(e)})

    if update is None:
        # Event type we don't act on (e.g. customer.created) — Stripe only
        # needs a 2xx to stop retrying, there's nothing to persist.
        return {"ok": True, "handled": False}

    _apply_update(update)
    return {"ok": True, "handled": True, "invoice_id": update["invoice_id"], "new_status": update["new_status"]}


def _apply_update(update: dict) -> None:
    """Reconciles one invoice's status into the sales_log table via a
    single atomic Apps Script call (read + mutate + write in one locked
    server-side execution — see AppsScript_Code.gs's
    handleUpdateSalesLogStatus_) rather than a separate load-then-save
    round trip, which would let two webhook deliveries arriving close
    together race and silently clobber each other's update. Safe to call
    more than once for the same event (Stripe retries/duplicates
    deliveries): the event id is persisted on the row server-side
    (_last_event_id), so a redelivery of an already-applied event is a
    durable no-op even across process restarts, not just because setting
    the same status value twice happens to be harmless."""
    result = update_sales_log_status(update["invoice_id"], update["new_status"], event_id=update.get("event_id", ""))
    if not result.success:
        logger.warning("Could not update sales_log for invoice_id=%s: %s", update["invoice_id"], result.error)
        log_event_standalone(
            "ERROR", "payment", "stripe_webhook_server",
            "sales_log reconciliation failed",
            {"invoice_id": update["invoice_id"], "new_status": update["new_status"], "error": result.error},
        )
        return
    found = bool((result.payload or {}).get("found"))
    applied = bool((result.payload or {}).get("applied"))
    duplicate = bool((result.payload or {}).get("duplicate"))
    if not found:
        logger.info("No sales_log row found for invoice_id=%s yet (event may have arrived before the row was saved).", update["invoice_id"])
    elif duplicate:
        logger.info("Duplicate delivery of event_id=%s for invoice_id=%s -- already applied, skipped.", update.get("event_id"), update["invoice_id"])
    elif not applied:
        # Found the row but the status-precedence check in AppsScript_Code.gs
        # refused it as a downgrade (e.g. a delayed charge.succeeded arriving
        # after its own refund) -- not an error, Stripe still gets a 2xx.
        logger.info(
            "sales_log row for invoice_id=%s not downgraded to %s (a more-final status already applied).",
            update["invoice_id"], update["new_status"],
        )
