"""
Unit tests for telemetry.py. Network calls are mocked, same convention as
storage.py/webhook_store.py. The core contract under test: logging must
NEVER raise or block the caller, regardless of what the backend does.
"""

import os
import unittest
from unittest import mock

import telemetry


class TestLogEventStandalone(unittest.TestCase):
    def setUp(self):
        self.env_patch = mock.patch.dict(
            os.environ, {"APPS_SCRIPT_URL": "https://script.google.com/fake", "APPS_SCRIPT_TOKEN": "fake-token"}
        )
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    @mock.patch("telemetry.requests")
    def test_posts_expected_fields(self, mock_requests):
        telemetry.log_event_standalone("ERROR", "webhook", "stripe_webhook_server", "boom", {"invoice_id": "POS-1"})
        call_kwargs = mock_requests.post.call_args.kwargs
        self.assertEqual(call_kwargs["data"]["action"], "log_event")
        self.assertEqual(call_kwargs["data"]["level"], "ERROR")
        self.assertEqual(call_kwargs["data"]["event_type"], "webhook")
        self.assertEqual(call_kwargs["data"]["source"], "stripe_webhook_server")
        self.assertEqual(call_kwargs["data"]["message"], "boom")
        self.assertIn("POS-1", call_kwargs["data"]["context"])
        self.assertEqual(call_kwargs["data"]["token"], "fake-token")

    @mock.patch("telemetry.requests")
    def test_never_raises_on_network_failure(self, mock_requests):
        mock_requests.post.side_effect = Exception("connection refused")
        try:
            telemetry.log_event_standalone("ERROR", "webhook", "src", "msg")
        except Exception:
            self.fail("log_event_standalone() must never raise")

    def test_missing_env_vars_is_a_silent_noop(self):
        self.env_patch.stop()
        try:
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch("telemetry.requests") as mock_requests:
                telemetry.log_event_standalone("ERROR", "webhook", "src", "msg")
                mock_requests.post.assert_not_called()
        finally:
            self.env_patch.start()

    @mock.patch("telemetry.requests")
    def test_context_defaults_to_empty_object(self, mock_requests):
        telemetry.log_event_standalone("INFO", "decision", "src", "msg")
        call_kwargs = mock_requests.post.call_args.kwargs
        self.assertEqual(call_kwargs["data"]["context"], "{}")


class TestLogEvent(unittest.TestCase):
    def test_never_raises_if_auth_config_lookup_fails(self):
        # log_event() reaches into auth.py for the Apps Script URL/token
        # (st.secrets-backed) -- a failure there (e.g. secrets not
        # configured) must still never raise out to the caller.
        with mock.patch("auth._apps_script_url", side_effect=Exception("secrets not configured")):
            try:
                telemetry.log_event("ERROR", "webhook", "src", "msg")
            except Exception:
                self.fail("log_event() must never raise")

    @mock.patch("telemetry.requests")
    def test_posts_expected_fields(self, mock_requests):
        with mock.patch("auth._apps_script_url", return_value="https://script.google.com/fake"), \
             mock.patch("auth._token", return_value="fake-token"):
            telemetry.log_event("INFO", "decision", "deal_workspace", "evaluated", {"decision": "BUY"})
        call_kwargs = mock_requests.post.call_args.kwargs
        self.assertEqual(call_kwargs["data"]["event_type"], "decision")
        self.assertEqual(call_kwargs["data"]["token"], "fake-token")


class TestLoadRecentEvents(unittest.TestCase):
    def test_returns_empty_list_on_failure(self):
        with mock.patch("storage.load_table", side_effect=Exception("boom")):
            self.assertEqual(telemetry.load_recent_events(), [])

    def test_returns_newest_first_and_respects_limit(self):
        fake_result = mock.Mock(success=True, payload=[{"message": "1st"}, {"message": "2nd"}, {"message": "3rd"}])
        with mock.patch("storage.load_table", return_value=fake_result):
            events = telemetry.load_recent_events(limit=2)
        self.assertEqual(events, [{"message": "3rd"}, {"message": "2nd"}])

    def test_no_saved_data_returns_empty_list(self):
        fake_result = mock.Mock(success=True, payload=None)
        with mock.patch("storage.load_table", return_value=fake_result):
            self.assertEqual(telemetry.load_recent_events(), [])


if __name__ == "__main__":
    unittest.main()
