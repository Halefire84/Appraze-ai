"""
Unit tests for pos.py — Stripe one-off Checkout Session creation for
point-of-sale charges. Wired into app.py's "Charge Customer" tab as of
2026-09-20 (previously unused); this is its first test coverage. Network
calls are mocked, same convention as comps_adapters.py/webhook_store.py.
"""

import unittest
from unittest import mock

from billing import BillingResult
from pos import check_payment_status, create_pos_checkout


class TestCreatePosCheckout(unittest.TestCase):
    def test_rejects_non_positive_amount(self):
        result = create_pos_checkout(0, "Item")
        self.assertFalse(result.success)
        self.assertIn("greater than $0", result.error)

    def test_rejects_negative_amount(self):
        result = create_pos_checkout(-5, "Item")
        self.assertFalse(result.success)

    @mock.patch("pos.st")
    def test_missing_secret_key_returns_failed_result_not_a_crash(self, mock_st):
        mock_st.secrets.get.side_effect = lambda k, default=None: default
        result = create_pos_checkout(10, "Item")
        self.assertFalse(result.success)

    @mock.patch("pos.requests")
    @mock.patch("pos.st")
    def test_successful_checkout_session_creation(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k, default=None: {
            "STRIPE_SECRET_KEY": "sk_test_x", "APP_URL": "",
        }.get(k, default)
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"url": "https://checkout.stripe.com/pay/abc", "id": "cs_test_123"}
        mock_requests.post.return_value = resp

        result = create_pos_checkout(49.99, "Vintage Camera")

        self.assertTrue(result.success)
        self.assertEqual(result.checkout_url, "https://checkout.stripe.com/pay/abc")
        self.assertEqual(result.session_id, "cs_test_123")
        self.assertTrue(result.invoice_id.startswith("POS-"))

        call_kwargs = mock_requests.post.call_args.kwargs
        # amount is sent to Stripe as integer cents, not a float dollar amount
        self.assertEqual(call_kwargs["data"]["line_items[0][price_data][unit_amount]"], 4999)
        # the invoice_id that reconciles this sale in sales_log must be the
        # same one embedded in the PaymentIntent metadata the webhook reads
        self.assertEqual(call_kwargs["data"]["payment_intent_data[metadata][invoice_id]"], result.invoice_id)

    @mock.patch("pos.requests")
    @mock.patch("pos.st")
    def test_each_call_gets_a_unique_invoice_id(self, mock_st, mock_requests):
        """Regression guard: two POS sales must never collide onto the same
        invoice_id, the same identity-collision class of bug flagged for
        listing_bridge.build_master_listing()'s old "CRTC-ITEM" fallback."""
        mock_st.secrets.get.side_effect = lambda k, default=None: {"STRIPE_SECRET_KEY": "sk_test_x"}.get(k, default)
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"url": "https://x", "id": "cs_1"}
        mock_requests.post.return_value = resp

        first = create_pos_checkout(10, "Item A")
        second = create_pos_checkout(10, "Item A")
        self.assertNotEqual(first.invoice_id, second.invoice_id)

    @mock.patch("pos.requests")
    @mock.patch("pos.st")
    def test_http_error_returns_failed_result_with_stripe_detail(self, mock_st, mock_requests):
        import requests as real_requests
        mock_st.secrets.get.side_effect = lambda k, default=None: {"STRIPE_SECRET_KEY": "sk_test_x"}.get(k, default)
        resp = mock.Mock()
        resp.text = '{"error": {"message": "Invalid API key"}}'
        error = real_requests.exceptions.HTTPError("401 Unauthorized")
        error.response = resp
        resp.raise_for_status.side_effect = error
        mock_requests.post.return_value = resp
        mock_requests.exceptions = real_requests.exceptions

        result = create_pos_checkout(10, "Item")
        self.assertFalse(result.success)
        self.assertIn("Stripe error", result.error)

    @mock.patch("pos.requests")
    @mock.patch("pos.st")
    def test_connection_failure_returns_failed_result_not_a_crash(self, mock_st, mock_requests):
        import requests as real_requests
        mock_st.secrets.get.side_effect = lambda k, default=None: {"STRIPE_SECRET_KEY": "sk_test_x"}.get(k, default)
        mock_requests.exceptions = real_requests.exceptions
        mock_requests.post.side_effect = Exception("network down")
        result = create_pos_checkout(10, "Item")
        self.assertFalse(result.success)
        self.assertIn("connection error", result.error)


class TestCheckPaymentStatus(unittest.TestCase):
    @mock.patch("pos.verify_checkout_session")
    def test_returns_true_when_paid(self, mock_verify):
        mock_verify.return_value = BillingResult(paid=True)
        self.assertTrue(check_payment_status("cs_test_123"))

    @mock.patch("pos.verify_checkout_session")
    def test_returns_false_when_not_paid(self, mock_verify):
        mock_verify.return_value = BillingResult(paid=False)
        self.assertFalse(check_payment_status("cs_test_123"))

    @mock.patch("pos.verify_checkout_session")
    def test_returns_false_on_lookup_error_not_a_crash(self, mock_verify):
        mock_verify.return_value = BillingResult(paid=False, error="connection error: timeout")
        self.assertFalse(check_payment_status("cs_test_123"))


if __name__ == "__main__":
    unittest.main()
