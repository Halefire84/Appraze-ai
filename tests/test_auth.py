"""
Unit tests for auth.py's shared authentication gate.

require_auth() and logout() both call real Streamlit functions, so `st` is
mocked throughout (same convention as tests/test_comps_adapters.py). Real
Streamlit's st.stop() and st.rerun() interrupt script execution by raising
internally -- a bare MagicMock does NOT do that by default, and a bare-mode
`import streamlit; streamlit.stop()` (outside `streamlit run`) is *also* a
silent no-op, which would make a naive test pass even if require_auth()
forgot to call st.stop() at all. So every test here configures
mock_st.stop.side_effect / mock_st.rerun.side_effect to raise, the same way
production Streamlit actually behaves, and asserts on which one fires.
"""

import unittest
from unittest import mock

from auth import (
    AuthResult,
    _admin_credentials_configured,
    _admin_login,
    logout,
    require_auth,
)


class _Stopped(Exception):
    """Stand-in for Streamlit's real internal StopException."""


class _Reran(Exception):
    """Stand-in for Streamlit's real internal RerunException."""


def _real_admin_secrets(password: str) -> dict:
    import hashlib
    return {
        "CRTC_ADMIN_USERNAME": "owner",
        "CRTC_ADMIN_PASSWORD_HASH": hashlib.sha256(password.encode()).hexdigest(),
    }


class TestAdminCredentialsConfigured(unittest.TestCase):
    @mock.patch("auth.st")
    def test_false_when_no_secrets_at_all(self, mock_st):
        # Real Streamlit: Secrets.get() raises when there's no secrets store,
        # not just when a key is missing -- see auth._secret's docstring.
        mock_st.secrets.get.side_effect = Exception("No secrets found")
        self.assertFalse(_admin_credentials_configured())

    @mock.patch("auth.st")
    def test_false_when_keys_missing(self, mock_st):
        mock_st.secrets.get.return_value = ""
        self.assertFalse(_admin_credentials_configured())

    @mock.patch("auth.st")
    def test_false_when_hash_is_wrong_length(self, mock_st):
        secrets = {"CRTC_ADMIN_USERNAME": "owner", "CRTC_ADMIN_PASSWORD_HASH": "not64chars"}
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        self.assertFalse(_admin_credentials_configured())

    @mock.patch("auth.st")
    def test_true_with_valid_looking_secrets(self, mock_st):
        secrets = _real_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        self.assertTrue(_admin_credentials_configured())


class TestAdminLogin(unittest.TestCase):
    @mock.patch("auth.st")
    def test_none_when_not_configured(self, mock_st):
        mock_st.secrets.get.side_effect = Exception("No secrets found")
        self.assertIsNone(_admin_login("owner", "anything"))

    @mock.patch("auth.st")
    def test_correct_credentials_succeed(self, mock_st):
        secrets = _real_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        result = _admin_login("owner", "correct horse battery staple")
        self.assertIsInstance(result, AuthResult)
        self.assertTrue(result.success)
        self.assertTrue(result.is_admin)

    @mock.patch("auth.st")
    def test_wrong_password_fails(self, mock_st):
        secrets = _real_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        result = _admin_login("owner", "wrong password")
        self.assertIsInstance(result, AuthResult)
        self.assertFalse(result.success)

    @mock.patch("auth.st")
    def test_wrong_username_returns_none_not_a_hint(self, mock_st):
        # None (not an AuthResult with an error) so the caller can't tell
        # "wrong username" apart from "not configured at all".
        secrets = _real_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        result = _admin_login("someone-else", "correct horse battery staple")
        self.assertIsNone(result)

    @mock.patch("auth.st")
    def test_username_is_case_insensitive(self, mock_st):
        secrets = _real_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        result = _admin_login("OWNER", "correct horse battery staple")
        self.assertTrue(result.success)


class TestRequireAuth(unittest.TestCase):
    def _configured_mock(self, mock_st, password="correct horse battery staple"):
        secrets = _real_admin_secrets(password)
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        mock_st.stop.side_effect = _Stopped
        mock_st.rerun.side_effect = _Reran
        return secrets

    @mock.patch("auth.st")
    def test_already_authenticated_returns_without_stopping(self, mock_st):
        mock_st.session_state.get.return_value = True
        mock_st.stop.side_effect = _Stopped
        # Must NOT raise -- an authenticated session renders the page normally.
        require_auth()
        mock_st.stop.assert_not_called()

    @mock.patch("auth.st")
    def test_unauthenticated_with_no_credentials_configured_fails_safely(self, mock_st):
        mock_st.session_state.get.return_value = False
        mock_st.secrets.get.side_effect = Exception("No secrets found")
        mock_st.stop.side_effect = _Stopped

        with self.assertRaises(_Stopped):
            require_auth()

        # No fallback password is ever accepted, and no login form should
        # even be offered when there's nothing valid to check it against.
        mock_st.error.assert_called()
        mock_st.form.assert_not_called()

    @mock.patch("auth.st")
    def test_unauthenticated_form_not_submitted_stops(self, mock_st):
        mock_st.session_state.get.return_value = False
        self._configured_mock(mock_st)
        mock_st.form_submit_button.return_value = False

        with self.assertRaises(_Stopped):
            require_auth()
        mock_st.rerun.assert_not_called()

    @mock.patch("auth.st")
    def test_correct_credentials_authenticate_and_rerun(self, mock_st):
        mock_st.session_state.get.return_value = False
        self._configured_mock(mock_st)
        mock_st.form_submit_button.return_value = True
        mock_st.text_input.side_effect = ["owner", "correct horse battery staple"]

        with self.assertRaises(_Reran):
            require_auth()
        # st.stop() must never be reached on the success path -- st.rerun()
        # interrupts first, exactly like real Streamlit.
        mock_st.stop.assert_not_called()

    @mock.patch("auth.st")
    def test_invalid_credentials_show_error_and_stop_without_rerun(self, mock_st):
        mock_st.session_state.get.return_value = False
        self._configured_mock(mock_st)
        mock_st.form_submit_button.return_value = True
        mock_st.text_input.side_effect = ["owner", "totally wrong password"]

        with self.assertRaises(_Stopped):
            require_auth()
        mock_st.rerun.assert_not_called()
        mock_st.error.assert_called()

    @mock.patch("auth.st")
    def test_blank_fields_warn_and_still_stop(self, mock_st):
        mock_st.session_state.get.return_value = False
        self._configured_mock(mock_st)
        mock_st.form_submit_button.return_value = True
        mock_st.text_input.side_effect = ["", ""]

        with self.assertRaises(_Stopped):
            require_auth()
        mock_st.warning.assert_called()
        mock_st.rerun.assert_not_called()


class TestLogout(unittest.TestCase):
    def test_logout_clears_every_session_key(self):
        # Use a real dict here (not a MagicMock) so .pop() is genuine dict
        # behavior, proving the keys are actually removed, not just called.
        state = {
            "authenticated": True,
            "user_display_name": "CRTC Admin",
            "user_is_admin": True,
            "user_is_paid": True,
            "username": "owner",
            "unrelated_app_state": "should survive logout",
        }
        with mock.patch("auth.st") as mock_st:
            mock_st.session_state = state
            logout()
        self.assertNotIn("authenticated", state)
        self.assertNotIn("user_display_name", state)
        self.assertNotIn("user_is_admin", state)
        self.assertNotIn("user_is_paid", state)
        self.assertNotIn("username", state)
        self.assertIn("unrelated_app_state", state)

    def test_logout_is_safe_to_call_when_never_logged_in(self):
        state = {}
        with mock.patch("auth.st") as mock_st:
            mock_st.session_state = state
            logout()  # must not raise KeyError/AttributeError
        self.assertEqual(state, {})


class TestSessionSurvivesRerun(unittest.TestCase):
    """Streamlit reruns the whole script top-to-bottom on every interaction,
    but st.session_state persists across those reruns within one session --
    that persistence is the platform's guarantee, not something require_auth()
    implements itself. What require_auth() must do correctly is respect an
    already-True flag on every subsequent call, exactly as a second, third,
    fourth... rerun would present it."""

    @mock.patch("auth.st")
    def test_authenticated_flag_holds_across_repeated_calls(self, mock_st):
        mock_st.session_state.get.return_value = True
        mock_st.stop.side_effect = _Stopped
        for _ in range(5):
            require_auth()  # must return cleanly every time, never stop
        mock_st.stop.assert_not_called()


class TestDemoModeIsolation(unittest.TestCase):
    """There is currently no functional demo-mode split in app.py to test --
    WORKSPACE is a single hardcoded "business" constant and every tab reads
    and writes that one workspace's session state directly. This is
    documented rather than faked: building a real isolated demo mode is a
    product decision (a second workspace, a way to enter it, and UI to
    distinguish it) out of scope for an auth-gate fix, per this lane's own
    "do not redesign the application" instruction."""

    def test_no_demo_workspace_exists_yet(self):
        # Source-level check rather than importing app.py: app.py is a plain
        # top-level Streamlit script (no __main__ guard), so importing it
        # here would execute the entire live UI in bare mode -- unnecessary
        # risk for confirming a documented, static fact about the source.
        with open("app.py", encoding="utf-8") as f:
            source = f.read()
        self.assertIn('WORKSPACE = "business"', source)


if __name__ == "__main__":
    unittest.main()
