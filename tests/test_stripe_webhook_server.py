"""
Integration tests for stripe_webhook_server.py's HTTP layer — signature
enforcement and routing to webhook_store, with webhook_store's network
calls mocked out (it's live Apps Script I/O, same convention as
storage.py/sheets.py not being unit-tested for their network paths).

    python3 -m pytest tests/test_stripe_webhook_server.py -v
"""

import hashlib
import hmac
import json
import os
import time
import unittest
from unittest import mock

os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_secret_1234567890")

from fastapi.testclient import TestClient  # noqa: E402

import stripe_webhook_server  # noqa: E402
from webhook_store import WebhookStoreResult  # noqa: E402

WEBHOOK_SECRET = "whsec_test_secret_1234567890"


def _sign(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    timestamp = int(time.time())
    signed_content = f"{timestamp}.{payload.decode('utf-8')}"
    signature = hmac.new(secret.encode(), signed_content.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


class TestHealthCheck(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(stripe_webhook_server.app)

    def test_root_health_check_needs_no_signature(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_healthz(self):
        resp = self.client.get("/healthz")
        self.assertEqual(resp.status_code, 200)


class TestStripeWebhookEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(stripe_webhook_server.app)
        os.environ["STRIPE_WEBHOOK_SECRET"] = WEBHOOK_SECRET

    def _post(self, event: dict, secret: str = WEBHOOK_SECRET):
        body = json.dumps(event).encode("utf-8")
        header = _sign(body, secret=secret)
        return self.client.post(
            "/stripe/webhook",
            data=body,
            headers={"stripe-signature": header, "content-type": "application/json"},
        )

    def test_invalid_signature_returns_400(self):
        event = {"type": "charge.succeeded", "data": {"object": {}}}
        resp = self._post(event, secret="wrong_secret")
        self.assertEqual(resp.status_code, 400)

    def test_missing_signature_header_returns_400(self):
        body = json.dumps({"type": "charge.succeeded"}).encode("utf-8")
        resp = self.client.post("/stripe/webhook", data=body, headers={"content-type": "application/json"})
        self.assertEqual(resp.status_code, 400)

    def test_unhandled_event_type_acknowledged_without_persisting(self):
        event = {"type": "customer.created", "data": {"object": {}}}
        with mock.patch("stripe_webhook_server.update_sales_log_status") as mock_update:
            resp = self._post(event)
            self.assertEqual(resp.status_code, 200)
            self.assertFalse(resp.json()["handled"])
            mock_update.assert_not_called()

    def test_charge_succeeded_updates_matching_sales_log_row(self):
        event = {
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "id": "ch_123",
                    "metadata": {"invoice_id": "POS-2026-09-07-abc123", "owner_key": "admin_shared"},
                    "amount": 5000,
                    "created": 0,
                }
            },
        }
        with mock.patch("stripe_webhook_server.update_sales_log_status", return_value=WebhookStoreResult(True, payload=True)) as mock_update:
            resp = self._post(event)
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            self.assertTrue(body["handled"])
            self.assertEqual(body["new_status"], "Paid (Card)")
            mock_update.assert_called_once_with("POS-2026-09-07-abc123", "Paid (Card)")

    def test_charge_succeeded_with_no_matching_row_does_not_crash(self):
        event = {
            "type": "charge.succeeded",
            "data": {"object": {"id": "ch_456", "metadata": {"invoice_id": "POS-DOES-NOT-EXIST"}, "amount": 100, "created": 0}},
        }
        with mock.patch("stripe_webhook_server.update_sales_log_status", return_value=WebhookStoreResult(True, payload=False)):
            resp = self._post(event)
            self.assertEqual(resp.status_code, 200)

    def test_replaying_the_same_event_twice_is_safe(self):
        event = {
            "type": "charge.succeeded",
            "data": {"object": {"id": "ch_dup", "metadata": {"invoice_id": "POS-DUP"}, "amount": 100, "created": 0}},
        }
        with mock.patch("stripe_webhook_server.update_sales_log_status", return_value=WebhookStoreResult(True, payload=True)):
            first = self._post(event)
            second = self._post(event)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)

    def test_persistence_failure_still_acknowledges_stripe(self):
        # If the Apps Script backend is unreachable, we still return 200 so
        # Stripe doesn't retry-storm us — the event is logged, not lost
        # silently, but there's no user-facing retry queue in this design.
        event = {
            "type": "charge.succeeded",
            "data": {"object": {"id": "ch_789", "metadata": {"invoice_id": "POS-1"}, "amount": 100, "created": 0}},
        }
        with mock.patch("stripe_webhook_server.update_sales_log_status", return_value=WebhookStoreResult(False, error="unreachable")):
            resp = self._post(event)
            self.assertEqual(resp.status_code, 200)

    def test_malformed_json_body_returns_400(self):
        body = b"not json at all"
        header = _sign(body)
        resp = self.client.post(
            "/stripe/webhook",
            data=body,
            headers={"stripe-signature": header, "content-type": "application/json"},
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
