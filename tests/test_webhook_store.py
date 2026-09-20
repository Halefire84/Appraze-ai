"""
Unit tests for webhook_store.py's update_sales_log_status() — first direct
coverage of this function (previously only exercised indirectly through
mocked stripe_webhook_server.py tests). Network calls are mocked, same
convention as storage.py/comps_adapters.py.

Covers the 2026-09-19/20 status-precedence reconciliation: the Apps Script
backend now enforces STATUS_RANK server-side and returns found/applied
separately, since a delayed webhook must be able to reach an existing row
(found=True) without being allowed to downgrade it (applied=False).
"""

import os
import unittest
from unittest import mock

import webhook_store


class TestUpdateSalesLogStatus(unittest.TestCase):
    def setUp(self):
        self.env_patch = mock.patch.dict(
            os.environ, {"APPS_SCRIPT_URL": "https://script.google.com/fake", "APPS_SCRIPT_TOKEN": "fake-token"}
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    @mock.patch("webhook_store.requests")
    def test_found_and_applied(self, mock_requests):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": True, "found": True, "applied": True}
        mock_requests.post.return_value = resp

        result = webhook_store.update_sales_log_status("POS-1", "Paid (Card)")
        self.assertTrue(result.success)
        self.assertEqual(result.payload, {"found": True, "applied": True})

    @mock.patch("webhook_store.requests")
    def test_found_but_downgrade_refused(self, mock_requests):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": True, "found": True, "applied": False}
        mock_requests.post.return_value = resp

        result = webhook_store.update_sales_log_status("POS-1", "Paid (Card)")
        self.assertTrue(result.success)  # not an error -- Stripe still gets a clean ack
        self.assertEqual(result.payload, {"found": True, "applied": False})

    @mock.patch("webhook_store.requests")
    def test_row_not_found(self, mock_requests):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": True, "found": False}
        mock_requests.post.return_value = resp

        result = webhook_store.update_sales_log_status("POS-DOES-NOT-EXIST", "Paid (Card)")
        self.assertTrue(result.success)
        self.assertEqual(result.payload, {"found": False, "applied": False})

    @mock.patch("webhook_store.requests")
    def test_force_flag_is_sent_to_apps_script(self, mock_requests):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": True, "found": True, "applied": True}
        mock_requests.post.return_value = resp

        webhook_store.update_sales_log_status("POS-1", "Paid (Card)", force=True)
        call_kwargs = mock_requests.post.call_args.kwargs
        self.assertEqual(call_kwargs["data"]["force"], "true")

    @mock.patch("webhook_store.requests")
    def test_force_defaults_to_false(self, mock_requests):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": True, "found": True, "applied": True}
        mock_requests.post.return_value = resp

        webhook_store.update_sales_log_status("POS-1", "Paid (Card)")
        call_kwargs = mock_requests.post.call_args.kwargs
        self.assertEqual(call_kwargs["data"]["force"], "false")

    def test_missing_env_vars_fails_safely_without_network_call(self):
        self.env_patch.stop()
        try:
            with mock.patch.dict(os.environ, {}, clear=True):
                result = webhook_store.update_sales_log_status("POS-1", "Paid (Card)")
                self.assertFalse(result.success)
        finally:
            self.env_patch.start()

    @mock.patch("webhook_store.requests")
    def test_apps_script_error_surfaces_without_crashing(self, mock_requests):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": False, "error": "sales_log payload is not valid JSON"}
        mock_requests.post.return_value = resp

        result = webhook_store.update_sales_log_status("POS-1", "Paid (Card)")
        self.assertFalse(result.success)
        self.assertIn("not valid JSON", result.error)

    @mock.patch("webhook_store.requests")
    def test_connection_failure_returns_failed_result_not_a_crash(self, mock_requests):
        mock_requests.post.side_effect = Exception("network down")
        result = webhook_store.update_sales_log_status("POS-1", "Paid (Card)")
        self.assertFalse(result.success)
        self.assertIn("connection error", result.error)


if __name__ == "__main__":
    unittest.main()
