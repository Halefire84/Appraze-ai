"""
Unit tests for storage.py. Network calls are mocked — same convention as
comps_adapters.py's eBay tests.

    python3 -m pytest tests/test_storage.py -v
"""

import unittest
from unittest import mock

import pandas as pd

import storage


class TestSaveTable(unittest.TestCase):
    def setUp(self):
        self.url_patch = mock.patch("storage._apps_script_url", return_value="https://script.google.com/fake")
        self.token_patch = mock.patch("storage._token", return_value="fake-token")
        self.url_patch.start()
        self.token_patch.start()
        self.addCleanup(self.url_patch.stop)
        self.addCleanup(self.token_patch.stop)

    @mock.patch("storage.requests")
    @mock.patch("storage.st")
    def test_uses_post_not_get(self, mock_st, mock_requests):
        """The actual bug this fix closes: a GET here put the whole table
        in the URL query string, which has a length ceiling - a table with
        enough rows would silently fail to save once it crossed that line."""
        mock_st.session_state.get.side_effect = lambda k, default=None: {"username": "alex", "user_is_admin": False}.get(k, default)
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"success": True}
        mock_requests.post.return_value = response

        df = pd.DataFrame([{"Item": "Chair", "Cost": 10.0}])
        result = storage.save_table(df, table="inventory")

        self.assertTrue(result.success)
        mock_requests.get.assert_not_called()
        mock_requests.post.assert_called_once()
        # The payload must be in the POST body (data=), never in params=.
        call_kwargs = mock_requests.post.call_args.kwargs
        self.assertIn("data", call_kwargs)
        self.assertNotIn("params", call_kwargs)
        self.assertIn("Chair", call_kwargs["data"]["payload"])

    @mock.patch("storage.requests")
    @mock.patch("storage.st")
    def test_a_payload_too_large_for_a_url_query_string_still_sends_fine(self, mock_st, mock_requests):
        """Directly proves the fix: build a table whose JSON payload alone
        would exceed a typical ~8KB URL length ceiling, and confirm it's
        still sent as one POST body rather than split, truncated, or
        raising - because it's in the body, not the URL, there's no ceiling
        to hit at all."""
        mock_st.session_state.get.side_effect = lambda k, default=None: {"username": "alex", "user_is_admin": False}.get(k, default)
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"success": True}
        mock_requests.post.return_value = response

        big_notes = "x" * 20_000  # comfortably past any URL length limit
        df = pd.DataFrame([{"Item Name": f"Item {i}", "Notes": big_notes} for i in range(5)])
        result = storage.save_table(df, table="inventory")

        self.assertTrue(result.success)
        sent_payload = mock_requests.post.call_args.kwargs["data"]["payload"]
        self.assertGreater(len(sent_payload), 20_000)

    @mock.patch("storage.requests")
    @mock.patch("storage.st")
    def test_shared_true_uses_admin_shared_identity_regardless_of_session(self, mock_st, mock_requests):
        mock_st.session_state.get.side_effect = lambda k, default=None: {"username": "someone_else", "user_is_admin": False}.get(k, default)
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"success": True}
        mock_requests.post.return_value = response

        storage.save_table(pd.DataFrame([{"a": 1}]), table="sales_log", shared=True)

        sent_data = mock_requests.post.call_args.kwargs["data"]
        self.assertEqual(sent_data["username"], "")
        self.assertEqual(sent_data["is_admin"], "true")

    @mock.patch("storage.requests")
    @mock.patch("storage.st")
    def test_backend_failure_is_reported_not_raised(self, mock_st, mock_requests):
        mock_st.session_state.get.side_effect = lambda k, default=None: default
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"success": False, "error": "sheet locked"}
        mock_requests.post.return_value = response

        result = storage.save_table(pd.DataFrame([{"a": 1}]))
        self.assertFalse(result.success)
        self.assertEqual(result.error, "sheet locked")

    @mock.patch("storage.requests")
    @mock.patch("storage.st")
    def test_connection_error_does_not_raise(self, mock_st, mock_requests):
        mock_st.session_state.get.side_effect = lambda k, default=None: default
        mock_requests.post.side_effect = ConnectionError("network down")

        result = storage.save_table(pd.DataFrame([{"a": 1}]))
        self.assertFalse(result.success)
        self.assertIn("network down", result.error)


class TestLoadTable(unittest.TestCase):
    def setUp(self):
        self.url_patch = mock.patch("storage._apps_script_url", return_value="https://script.google.com/fake")
        self.token_patch = mock.patch("storage._token", return_value="fake-token")
        self.url_patch.start()
        self.token_patch.start()
        self.addCleanup(self.url_patch.stop)
        self.addCleanup(self.token_patch.stop)

    @mock.patch("storage.requests")
    @mock.patch("storage.st")
    def test_uses_post_not_get(self, mock_st, mock_requests):
        mock_st.session_state.get.side_effect = lambda k, default=None: default
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"success": True, "payload": '[{"Item": "Chair"}]'}
        mock_requests.post.return_value = response

        result = storage.load_table("inventory")

        self.assertTrue(result.success)
        self.assertEqual(result.payload, [{"Item": "Chair"}])
        mock_requests.get.assert_not_called()
        call_kwargs = mock_requests.post.call_args.kwargs
        self.assertIn("data", call_kwargs)
        self.assertNotIn("params", call_kwargs)

    @mock.patch("storage.requests")
    @mock.patch("storage.st")
    def test_no_saved_data_yet_returns_success_with_none_payload(self, mock_st, mock_requests):
        mock_st.session_state.get.side_effect = lambda k, default=None: default
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"success": True, "payload": ""}
        mock_requests.post.return_value = response

        result = storage.load_table("inventory")
        self.assertTrue(result.success)
        self.assertIsNone(result.payload)

    @mock.patch("storage.requests")
    @mock.patch("storage.st")
    def test_backend_failure_is_reported_not_raised(self, mock_st, mock_requests):
        mock_st.session_state.get.side_effect = lambda k, default=None: default
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"success": False, "error": "not found"}
        mock_requests.post.return_value = response

        result = storage.load_table("inventory")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "not found")


if __name__ == "__main__":
    unittest.main()
