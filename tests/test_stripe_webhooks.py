"""
Unit tests for stripe_webhooks.py - signature verification and event
handling for Stripe webhooks. Pure logic, no network dependency:

    python3 -m unittest tests.test_stripe_webhooks -v
"""

import hashlib
import hmac
import time
import unittest

from stripe_webhooks import (
    StripeWebhookError,
    handle_charge_failed,
    handle_charge_refunded,
    handle_charge_succeeded,
    process_webhook_event,
    update_invoice_status,
    verify_stripe_signature,
)

WEBHOOK_SECRET = "whsec_test_secret_1234567890"


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET, timestamp: int = None) -> str:
    """Builds a valid Stripe-style signature header for a payload, mirroring
    what Stripe itself computes — used to generate "known good" fixtures."""
    if timestamp is None:
        timestamp = int(time.time())
    signed_content = f"{timestamp}.{payload.decode('utf-8')}"
    signature = hmac.new(secret.encode(), signed_content.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


class TestVerifyStripeSignature(unittest.TestCase):
    def test_valid_signature_passes(self):
        payload = b'{"type": "charge.succeeded"}'
        header = _sign(payload)
        self.assertTrue(verify_stripe_signature(payload, header, WEBHOOK_SECRET))

    def test_invalid_signature_fails(self):
        payload = b'{"type": "charge.succeeded"}'
        header = _sign(payload, secret="a_completely_different_secret")
        self.assertFalse(verify_stripe_signature(payload, header, WEBHOOK_SECRET))

    def test_tampered_payload_fails(self):
        payload = b'{"type": "charge.succeeded"}'
        header = _sign(payload)
        tampered_payload = b'{"type": "charge.refunded"}'
        self.assertFalse(verify_stripe_signature(tampered_payload, header, WEBHOOK_SECRET))

    def test_missing_header_raises(self):
        with self.assertRaises(StripeWebhookError):
            verify_stripe_signature(b"{}", "", WEBHOOK_SECRET)

    def test_missing_secret_raises(self):
        with self.assertRaises(StripeWebhookError):
            verify_stripe_signature(b"{}", "t=123,v1=abc", "")

    def test_malformed_header_raises(self):
        with self.assertRaises(StripeWebhookError):
            verify_stripe_signature(b"{}", "not-a-valid-header", WEBHOOK_SECRET)

    def test_header_missing_v1_raises(self):
        with self.assertRaises(StripeWebhookError):
            verify_stripe_signature(b"{}", "t=123", WEBHOOK_SECRET)


class TestHandleChargeSucceeded(unittest.TestCase):
    def test_normal_event(self):
        event_data = {
            "id": "ch_123",
            "metadata": {"invoice_id": "POS-2026-09-05-1"},
            "amount": 24000,
            "created": 1735689600,
        }
        result = handle_charge_succeeded(event_data)
        self.assertEqual(result["invoice_id"], "POS-2026-09-05-1")
        self.assertEqual(result["new_status"], "Paid (Card)")
        self.assertEqual(result["amount"], 240.0)

    def test_falls_back_to_charge_id_when_no_metadata(self):
        result = handle_charge_succeeded({"id": "ch_456", "amount": 1000, "created": 0})
        self.assertEqual(result["invoice_id"], "ch_456")

    def test_missing_event_data_raises(self):
        with self.assertRaises(StripeWebhookError):
            handle_charge_succeeded({})


class TestHandleChargeFailed(unittest.TestCase):
    def test_normal_event(self):
        event_data = {
            "id": "ch_789",
            "metadata": {"invoice_id": "POS-1"},
            "failure_message": "card_declined",
            "created": 0,
        }
        result = handle_charge_failed(event_data)
        self.assertEqual(result["new_status"], "Payment Failed")
        self.assertEqual(result["failure_reason"], "card_declined")

    def test_missing_event_data_raises(self):
        with self.assertRaises(StripeWebhookError):
            handle_charge_failed(None)


class TestHandleChargeRefunded(unittest.TestCase):
    def test_normal_event(self):
        event_data = {
            "id": "ch_999",
            "metadata": {"invoice_id": "POS-2"},
            "refunded": 5000,
            "created": 0,
        }
        result = handle_charge_refunded(event_data)
        self.assertEqual(result["new_status"], "Refunded")
        self.assertEqual(result["refund_amount"], 50.0)


class TestProcessWebhookEvent(unittest.TestCase):
    def test_charge_succeeded_routes_correctly(self):
        event = {
            "type": "charge.succeeded",
            "data": {"object": {"id": "ch_1", "metadata": {"invoice_id": "INV-1"}, "amount": 100, "created": 0}},
        }
        result = process_webhook_event(event)
        self.assertEqual(result["new_status"], "Paid (Card)")

    def test_unhandled_event_type_returns_none(self):
        event = {"type": "customer.created", "data": {"object": {}}}
        self.assertIsNone(process_webhook_event(event))

    def test_subscription_event_type_is_unhandled_but_does_not_crash(self):
        # Only charge.* events are wired up today; anything else should be a
        # clean no-op rather than raising, so unrecognized/future event types
        # never take down the webhook endpoint.
        event = {"type": "invoice.payment_succeeded", "data": {"object": {}}}
        self.assertIsNone(process_webhook_event(event))


class TestIdempotency(unittest.TestCase):
    def test_processing_the_same_event_twice_yields_the_same_result(self):
        # Stripe guarantees at-least-once delivery, so the same event can
        # arrive more than once. process_webhook_event is pure/stateless, so
        # replaying it must be safe (same input -> same output, no side
        # effects of its own) — actual dedup happens at the caller via
        # update_invoice_status only changing state when the status differs.
        event = {
            "type": "charge.succeeded",
            "data": {"object": {"id": "ch_dup", "metadata": {"invoice_id": "INV-DUP"}, "amount": 100, "created": 0}},
        }
        first = process_webhook_event(event)
        second = process_webhook_event(event)
        self.assertEqual(first, second)

    def test_update_invoice_status_is_safe_to_apply_twice(self):
        sales_log = [{"Invoice #": "INV-DUP", "Status": "Awaiting Payment"}]
        self.assertTrue(update_invoice_status(sales_log, "INV-DUP", "Paid (Card)"))
        self.assertTrue(update_invoice_status(sales_log, "INV-DUP", "Paid (Card)"))
        self.assertEqual(sales_log[0]["Status"], "Paid (Card)")


class TestUpdateInvoiceStatus(unittest.TestCase):
    def test_updates_matching_invoice(self):
        sales_log = [{"Invoice #": "INV-1", "Status": "Awaiting Payment"}]
        self.assertTrue(update_invoice_status(sales_log, "INV-1", "Paid (Card)"))
        self.assertEqual(sales_log[0]["Status"], "Paid (Card)")

    def test_returns_false_when_invoice_not_found(self):
        sales_log = [{"Invoice #": "INV-1", "Status": "Awaiting Payment"}]
        self.assertFalse(update_invoice_status(sales_log, "INV-DOES-NOT-EXIST", "Paid (Card)"))

    def test_matches_by_id_field_too(self):
        sales_log = [{"id": "INV-2", "Status": "Awaiting Payment"}]
        self.assertTrue(update_invoice_status(sales_log, "INV-2", "Refunded"))


if __name__ == "__main__":
    unittest.main()
