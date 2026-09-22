"""
Unit tests for billing.py's verify_checkout_session() — the read-only
Stripe lookup pos.check_payment_status() now depends on (pos.py is wired
into app.py's "Charge Customer" tab as of 2026-09-20). Network calls are
mocked, same convention as comps_adapters.py.
"""

import unittest
from unittest import mock

from billing import verify_checkout_session


class TestVerifyCheckoutSession(unittest.TestCase):
    @mock.patch("billing.requests")
    @mock.patch("billing.st")
    def test_paid_session_returns_paid_true(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k, default=None: {"STRIPE_SECRET_KEY": "sk_test_x"}.get(k, default)
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"payment_status": "paid", "customer_details": {"email": "a@example.com"}}
        mock_requests.get.return_value = resp

        result = verify_checkout_session("cs_test_123")
        self.assertTrue(result.paid)
        self.assertEqual(result.customer_email, "a@example.com")

    @mock.patch("billing.requests")
    @mock.patch("billing.st")
    def test_unpaid_session_returns_paid_false(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k, default=None: {"STRIPE_SECRET_KEY": "sk_test_x"}.get(k, default)
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"payment_status": "unpaid"}
        mock_requests.get.return_value = resp

        result = verify_checkout_session("cs_test_123")
        self.assertFalse(result.paid)

    @mock.patch("billing.requests")
    @mock.patch("billing.st")
    def test_missing_customer_details_does_not_crash(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k, default=None: {"STRIPE_SECRET_KEY": "sk_test_x"}.get(k, default)
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"payment_status": "paid"}  # no customer_details key at all
        mock_requests.get.return_value = resp

        result = verify_checkout_session("cs_test_123")
        self.assertTrue(result.paid)
        self.assertEqual(result.customer_email, "")

    @mock.patch("billing.requests")
    @mock.patch("billing.st")
    def test_http_error_returns_unpaid_with_error_not_a_crash(self, mock_st, mock_requests):
        import requests as real_requests
        mock_st.secrets.get.side_effect = lambda k, default=None: {"STRIPE_SECRET_KEY": "sk_test_x"}.get(k, default)
        resp = mock.Mock()
        resp.status_code = 404
        error = real_requests.exceptions.HTTPError("404 Not Found")
        error.response = resp
        resp.raise_for_status.side_effect = error
        mock_requests.get.return_value = resp
        mock_requests.exceptions = real_requests.exceptions

        result = verify_checkout_session("cs_does_not_exist")
        self.assertFalse(result.paid)
        self.assertIn("Stripe error", result.error)

    @mock.patch("billing.requests")
    @mock.patch("billing.st")
    def test_connection_failure_returns_unpaid_not_a_crash(self, mock_st, mock_requests):
        import requests as real_requests
        mock_st.secrets.get.side_effect = lambda k, default=None: {"STRIPE_SECRET_KEY": "sk_test_x"}.get(k, default)
        mock_requests.exceptions = real_requests.exceptions
        mock_requests.get.side_effect = Exception("network down")

        result = verify_checkout_session("cs_test_123")
        self.assertFalse(result.paid)
        self.assertIn("connection error", result.error)


if __name__ == "__main__":
    unittest.main()
