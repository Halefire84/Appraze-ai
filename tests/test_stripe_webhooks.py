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
    can_transition,
    handle_charge_failed,
    handle_charge_refunded,
    handle_charge_succeeded,
    process_webhook_event,
    status_rank,
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

    def test_non_numeric_timestamp_raises(self):
        payload = b"{}"
        signature = hmac.new(
            WEBHOOK_SECRET.encode(), f"not-a-number.{payload.decode()}".encode(), hashlib.sha256
        ).hexdigest()
        with self.assertRaises(StripeWebhookError):
            verify_stripe_signature(payload, f"t=not-a-number,v1={signature}", WEBHOOK_SECRET)

    def test_stale_timestamp_is_rejected_as_a_possible_replay(self):
        # A stale timestamp is treated as a validation failure (raises),
        # not a plain "signature didn't match" (False) -- it's a possible
        # replay of a captured valid payload+signature, which is a more
        # serious finding than an ordinary mismatch.
        payload = b'{"type": "charge.succeeded"}'
        old_timestamp = int(time.time()) - 600  # 10 minutes old > 5 minute tolerance
        header = _sign(payload, timestamp=old_timestamp)
        with self.assertRaises(StripeWebhookError):
            verify_stripe_signature(payload, header, WEBHOOK_SECRET)

    def test_timestamp_within_tolerance_passes(self):
        payload = b'{"type": "charge.succeeded"}'
        recent_timestamp = int(time.time()) - 60  # 1 minute old, well within tolerance
        header = _sign(payload, timestamp=recent_timestamp)
        self.assertTrue(verify_stripe_signature(payload, header, WEBHOOK_SECRET))

    def test_future_timestamp_beyond_tolerance_is_rejected(self):
        # Clock skew is one thing, but a signature dated far in the future is
        # just as suspicious as a stale replay.
        payload = b'{"type": "charge.succeeded"}'
        future_timestamp = int(time.time()) + 600
        header = _sign(payload, timestamp=future_timestamp)
        with self.assertRaises(StripeWebhookError):
            verify_stripe_signature(payload, header, WEBHOOK_SECRET)

    def test_tolerance_disabled_accepts_stale_timestamp(self):
        payload = b'{"type": "charge.succeeded"}'
        old_timestamp = int(time.time()) - 600
        header = _sign(payload, timestamp=old_timestamp)
        self.assertTrue(
            verify_stripe_signature(payload, header, WEBHOOK_SECRET, tolerance_sec=0)
        )

    def test_custom_tolerance_and_injected_clock(self):
        payload = b'{"type": "charge.succeeded"}'
        header = _sign(payload, timestamp=1_000_000)
        self.assertTrue(
            verify_stripe_signature(
                payload, header, WEBHOOK_SECRET, tolerance_sec=120, now=1_000_100
            )
        )
        with self.assertRaises(StripeWebhookError):
            verify_stripe_signature(
                payload, header, WEBHOOK_SECRET, tolerance_sec=120, now=1_000_300
            )

    def test_non_ascii_signature_header_raises(self):
        with self.assertRaises(StripeWebhookError):
            verify_stripe_signature(b"{}", "t=1,v1=abc☃", WEBHOOK_SECRET)

    def test_secret_rotation_accepts_any_valid_v1_signature(self):
        # During a signing-secret rotation, Stripe sends multiple v1 values
        # in one header (old secret + new secret). Any match must pass,
        # regardless of position.
        payload = b'{"ok":true}'
        ts = str(int(time.time()))
        signed = f"{ts}.".encode() + payload
        good = hmac.new(WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
        header_good_first = f"t={ts},v1={good},v1=deadbeef"
        header_good_last = f"t={ts},v1=deadbeef,v1={good}"
        self.assertTrue(verify_stripe_signature(payload, header_good_first, WEBHOOK_SECRET))
        self.assertTrue(verify_stripe_signature(payload, header_good_last, WEBHOOK_SECRET))

    def test_string_payload_is_accepted_like_bytes(self):
        payload_bytes = b'{"type": "charge.succeeded"}'
        header = _sign(payload_bytes)
        self.assertTrue(verify_stripe_signature(payload_bytes.decode(), header, WEBHOOK_SECRET))


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
    def test_full_refund_uses_amount_refunded_not_the_boolean(self):
        # `refunded` is a BOOLEAN in Stripe's real payload (true even for a
        # partial refund) -- using it as a dollar amount was the bug.
        event_data = {
            "id": "ch_999",
            "amount": 5000,
            "amount_refunded": 5000,
            "refunded": True,
            "metadata": {"invoice_id": "POS-2"},
            "created": 0,
        }
        result = handle_charge_refunded(event_data)
        self.assertEqual(result["new_status"], "Refunded")
        self.assertEqual(result["refund_amount"], 50.0)

    def test_partial_refund_status_and_amount(self):
        event_data = {
            "id": "ch_1000",
            "amount": 5000,
            "amount_refunded": 1500,  # only $15 of a $50 charge
            "refunded": False,
            "metadata": {"invoice_id": "POS-3"},
            "created": 0,
        }
        result = handle_charge_refunded(event_data)
        self.assertEqual(result["new_status"], "Partially Refunded")
        self.assertEqual(result["refund_amount"], 15.0)
        self.assertEqual(result["charge_amount"], 50.0)

    def test_missing_amount_refunded_defaults_to_zero_not_a_crash(self):
        event_data = {"id": "ch_1001", "amount": 5000, "metadata": {"invoice_id": "POS-4"}, "created": 0}
        result = handle_charge_refunded(event_data)
        self.assertEqual(result["refund_amount"], 0.0)
        self.assertEqual(result["new_status"], "Refunded")


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


class TestStatusPrecedence(unittest.TestCase):
    """A delayed/out-of-order webhook must never downgrade a more-final
    status -- a late 'charge.succeeded' arriving after its own refund must
    not resurrect 'Paid (Card)' over 'Refunded'."""

    def test_rank_ordering(self):
        self.assertLess(status_rank("Awaiting Payment"), status_rank("Payment Failed"))
        self.assertLess(status_rank("Payment Failed"), status_rank("Paid (Card)"))
        self.assertLess(status_rank("Paid (Card)"), status_rank("Partially Refunded"))
        self.assertLess(status_rank("Partially Refunded"), status_rank("Refunded"))

    def test_unknown_status_ranks_lowest(self):
        self.assertEqual(status_rank(None), -1)
        self.assertEqual(status_rank("Some Future Status Stripe Invents"), -1)

    def test_forward_transition_allowed(self):
        self.assertTrue(can_transition("Paid (Card)", "Refunded"))
        self.assertTrue(can_transition("Awaiting Payment", "Paid (Card)"))
        self.assertTrue(can_transition("Paid (Card)", "Paid (Card)"))  # same rank, no-op is fine

    def test_downgrade_rejected(self):
        self.assertFalse(can_transition("Refunded", "Paid (Card)"))
        self.assertFalse(can_transition("Partially Refunded", "Awaiting Payment"))

    def test_out_of_order_webhook_cannot_downgrade_refunded_to_paid(self):
        sales_log = [{"Invoice #": "POS-1", "Status": "Refunded"}]
        applied = update_invoice_status(sales_log, "POS-1", "Paid (Card)")
        self.assertFalse(applied)
        self.assertEqual(sales_log[0]["Status"], "Refunded")

    def test_forward_transition_still_applies(self):
        sales_log = [{"Invoice #": "POS-1", "Status": "Paid (Card)"}]
        applied = update_invoice_status(sales_log, "POS-1", "Refunded")
        self.assertTrue(applied)
        self.assertEqual(sales_log[0]["Status"], "Refunded")

    def test_force_bypasses_precedence(self):
        sales_log = [{"Invoice #": "POS-1", "Status": "Refunded"}]
        applied = update_invoice_status(sales_log, "POS-1", "Paid (Card)", force=True)
        self.assertTrue(applied)
        self.assertEqual(sales_log[0]["Status"], "Paid (Card)")


class TestEventIdIdempotency(unittest.TestCase):
    """Stripe guarantees at-least-once delivery -- the same event_id can
    arrive more than once and must not be applied twice."""

    def test_duplicate_event_id_is_skipped(self):
        sales_log = [{"Invoice #": "POS-1", "Status": "Awaiting Payment"}]
        seen: set = set()
        first = update_invoice_status(sales_log, "POS-1", "Paid (Card)", event_id="evt_1", seen_event_ids=seen)
        second = update_invoice_status(sales_log, "POS-1", "Refunded", event_id="evt_1", seen_event_ids=seen)
        self.assertTrue(first)
        self.assertFalse(second)  # same event_id, skipped even though it targets a different status
        self.assertEqual(sales_log[0]["Status"], "Paid (Card)")

    def test_different_event_ids_both_apply(self):
        sales_log = [{"Invoice #": "POS-1", "Status": "Awaiting Payment"}]
        seen: set = set()
        self.assertTrue(update_invoice_status(sales_log, "POS-1", "Paid (Card)", event_id="evt_1", seen_event_ids=seen))
        self.assertTrue(update_invoice_status(sales_log, "POS-1", "Refunded", event_id="evt_2", seen_event_ids=seen))
        self.assertEqual(sales_log[0]["Status"], "Refunded")


class TestProcessWebhookEventCarriesEventId(unittest.TestCase):
    def test_event_id_is_attached_when_present(self):
        event = {
            "id": "evt_abc",
            "type": "charge.succeeded",
            "data": {"object": {"id": "ch_1", "metadata": {"invoice_id": "INV-1"}, "amount": 100, "created": 0}},
        }
        result = process_webhook_event(event)
        self.assertEqual(result["event_id"], "evt_abc")


if __name__ == "__main__":
    unittest.main()
