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

import json
import unittest
from unittest import mock

from auth import (
    AuthResult,
    _admin_credentials_configured,
    _admin_login,
    _beta_enabled,
    _beta_login,
    _beta_signup,
    get_visit_count,
    logout,
    mark_paid,
    require_auth,
)


class _Stopped(Exception):
    """Stand-in for Streamlit's real internal StopException."""


class _Reran(Exception):
    """Stand-in for Streamlit's real internal RerunException."""


def _real_admin_secrets(password: str) -> dict:
    """Legacy-format secrets (SHA-256) -- exercises the backward-compat
    path every already-deployed CRTC_ADMIN_PASSWORD_HASH secret uses."""
    import hashlib
    return {
        "CRTC_ADMIN_USERNAME": "owner",
        "CRTC_ADMIN_PASSWORD_HASH": hashlib.sha256(password.encode()).hexdigest(),
    }


def _bcrypt_admin_secrets(password: str) -> dict:
    """New-format secrets (bcrypt) -- what AUTH_SETUP.md now tells a
    deployer to generate."""
    import bcrypt
    return {
        "CRTC_ADMIN_USERNAME": "owner",
        "CRTC_ADMIN_PASSWORD_HASH": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
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

    @mock.patch("auth.st")
    def test_admin_login_carries_admin_plan(self, mock_st):
        secrets = _real_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        result = _admin_login("owner", "correct horse battery staple")
        self.assertEqual(result.plan, "admin")
        self.assertTrue(result.is_paid)


class TestMarkPaid(unittest.TestCase):
    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_sends_plan_when_given(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k, d="": {
            "APPS_SCRIPT_URL": "https://script.example/exec",
            "APPS_SCRIPT_TOKEN": "tok",
        }.get(k, d)
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": True}
        mock_requests.post.return_value = resp

        result = mark_paid("alice", plan="hunter")

        self.assertTrue(result)
        sent = mock_requests.post.call_args.kwargs["data"]
        self.assertEqual(sent["plan"], "hunter")
        self.assertEqual(sent["username"], "alice")
        self.assertEqual(sent["action"], "set_paid")

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_omits_plan_key_entirely_when_not_given(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k, d="": {
            "APPS_SCRIPT_URL": "https://script.example/exec",
            "APPS_SCRIPT_TOKEN": "tok",
        }.get(k, d)
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": True}
        mock_requests.post.return_value = resp

        mark_paid("alice")

        sent = mock_requests.post.call_args.kwargs["data"]
        self.assertNotIn("plan", sent)

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_connection_failure_returns_false_not_a_crash(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k, d="": {
            "APPS_SCRIPT_URL": "https://script.example/exec",
            "APPS_SCRIPT_TOKEN": "tok",
        }.get(k, d)
        mock_requests.post.side_effect = Exception("network down")

        self.assertFalse(mark_paid("alice", plan="hunter"))


class TestBcryptAdminAuth(unittest.TestCase):
    """2026-09-21 auth hardening: bcrypt is the new format,
    SHA-256 stays supported for already-deployed secrets."""

    @mock.patch("auth.st")
    def test_bcrypt_secret_is_recognized_as_configured(self, mock_st):
        secrets = _bcrypt_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        self.assertTrue(_admin_credentials_configured())

    @mock.patch("auth.st")
    def test_bcrypt_correct_password_succeeds(self, mock_st):
        secrets = _bcrypt_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        result = _admin_login("owner", "correct horse battery staple")
        self.assertTrue(result.success)
        self.assertEqual(result.plan, "admin")

    @mock.patch("auth.st")
    def test_bcrypt_wrong_password_fails(self, mock_st):
        secrets = _bcrypt_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        result = _admin_login("owner", "wrong password")
        self.assertFalse(result.success)

    @mock.patch("auth.st")
    def test_legacy_sha256_secret_still_works_unchanged(self, mock_st):
        # Backward compatibility: an already-deployed secret in the old
        # format must keep authenticating exactly as before -- migrating
        # to bcrypt must never lock an existing deployment's owner out.
        secrets = _real_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        self.assertTrue(_admin_credentials_configured())
        result = _admin_login("owner", "correct horse battery staple")
        self.assertTrue(result.success)


class TestBetaInviteSignup(unittest.TestCase):
    """2026-09-21 beta access: CRTC_BETA_INVITE_CODES gates a separate,
    single-use-code signup path that reuses the Apps Script
    save_data/load_data backend for account storage (see
    auth._load_beta_accounts/_save_beta_accounts) instead of a new local
    store, and always grants free full access (never touches Stripe)."""

    def _beta_secrets(self, codes="ABC123,DEF456", admin_password="correct horse battery staple"):
        secrets = _real_admin_secrets(admin_password)
        secrets["CRTC_BETA_INVITE_CODES"] = codes
        secrets["APPS_SCRIPT_URL"] = "https://script.example/exec"
        secrets["APPS_SCRIPT_TOKEN"] = "tok"
        return secrets

    @mock.patch("auth.st")
    def test_beta_disabled_when_no_codes_configured(self, mock_st):
        mock_st.secrets.get.side_effect = lambda k, d="": {}.get(k, d)
        self.assertFalse(_beta_enabled())

    @mock.patch("auth.st")
    def test_beta_enabled_when_codes_configured(self, mock_st):
        secrets = self._beta_secrets()
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        self.assertTrue(_beta_enabled())

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_valid_code_creates_account_with_free_access(self, mock_st, mock_requests):
        secrets = self._beta_secrets()
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)

        load_resp = mock.Mock()
        load_resp.raise_for_status.return_value = None
        load_resp.json.return_value = {"success": True, "payload": None}
        save_resp = mock.Mock()
        save_resp.raise_for_status.return_value = None
        save_resp.json.return_value = {"success": True}
        mock_requests.post.side_effect = [load_resp, save_resp]

        result = _beta_signup("newuser", "somepassword", "New User", "abc123")

        self.assertTrue(result.success)
        self.assertTrue(result.is_paid)
        self.assertEqual(result.plan, "beta")
        self.assertFalse(result.is_admin)

        saved_payload = json.loads(mock_requests.post.call_args_list[1].kwargs["data"]["payload"])
        self.assertEqual(saved_payload[0]["invite_code"], "ABC123")
        self.assertEqual(saved_payload[0]["username"], "newuser")
        # password must never be stored in the clear
        self.assertNotEqual(saved_payload[0]["password_hash"], "somepassword")

    @mock.patch("auth.st")
    def test_invalid_code_rejected(self, mock_st):
        secrets = self._beta_secrets()
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        result = _beta_signup("newuser", "somepassword", "New User", "not-a-real-code")
        self.assertFalse(result.success)
        self.assertIn("Invalid invite code", result.error)

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_already_used_code_rejected(self, mock_st, mock_requests):
        secrets = self._beta_secrets()
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)

        load_resp = mock.Mock()
        load_resp.raise_for_status.return_value = None
        load_resp.json.return_value = {
            "success": True,
            "payload": json.dumps([{"username": "firstuser", "invite_code": "ABC123", "password_hash": "x"}]),
        }
        mock_requests.post.return_value = load_resp

        result = _beta_signup("seconduser", "somepassword", "Second User", "abc123")

        self.assertFalse(result.success)
        self.assertIn("already been used", result.error)

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_duplicate_username_rejected(self, mock_st, mock_requests):
        secrets = self._beta_secrets()
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)

        load_resp = mock.Mock()
        load_resp.raise_for_status.return_value = None
        load_resp.json.return_value = {
            "success": True,
            "payload": json.dumps([{"username": "newuser", "invite_code": "DEF456", "password_hash": "x"}]),
        }
        mock_requests.post.return_value = load_resp

        result = _beta_signup("newuser", "somepassword", "New User", "abc123")

        self.assertFalse(result.success)
        self.assertIn("already taken", result.error)

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_login_with_correct_password_succeeds(self, mock_st, mock_requests):
        secrets = self._beta_secrets()
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        import bcrypt as real_bcrypt
        stored_hash = real_bcrypt.hashpw(b"somepassword", real_bcrypt.gensalt()).decode()

        load_resp = mock.Mock()
        load_resp.raise_for_status.return_value = None
        load_resp.json.return_value = {
            "success": True,
            "payload": json.dumps([{
                "username": "newuser", "display_name": "New User",
                "invite_code": "ABC123", "password_hash": stored_hash,
            }]),
        }
        mock_requests.post.return_value = load_resp

        result = _beta_login("newuser", "somepassword")

        self.assertIsNotNone(result)
        self.assertTrue(result.success)
        self.assertTrue(result.is_paid)
        self.assertEqual(result.plan, "beta")

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_login_with_wrong_password_fails(self, mock_st, mock_requests):
        secrets = self._beta_secrets()
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        import bcrypt as real_bcrypt
        stored_hash = real_bcrypt.hashpw(b"somepassword", real_bcrypt.gensalt()).decode()

        load_resp = mock.Mock()
        load_resp.raise_for_status.return_value = None
        load_resp.json.return_value = {
            "success": True,
            "payload": json.dumps([{"username": "newuser", "invite_code": "ABC123", "password_hash": stored_hash}]),
        }
        mock_requests.post.return_value = load_resp

        result = _beta_login("newuser", "wrongpassword")

        self.assertIsNotNone(result)
        self.assertFalse(result.success)

    @mock.patch("auth.st")
    def test_login_returns_none_when_beta_not_configured(self, mock_st):
        mock_st.secrets.get.side_effect = lambda k, d="": {}.get(k, d)
        self.assertIsNone(_beta_login("anyone", "anything"))

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_login_returns_none_when_username_unknown(self, mock_st, mock_requests):
        secrets = self._beta_secrets()
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        load_resp = mock.Mock()
        load_resp.raise_for_status.return_value = None
        load_resp.json.return_value = {"success": True, "payload": None}
        mock_requests.post.return_value = load_resp

        self.assertIsNone(_beta_login("nosuchuser", "anything"))


class TestVisitCounter(unittest.TestCase):
    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_get_visit_count_reads_stored_total(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k, d="": {
            "APPS_SCRIPT_URL": "https://script.example/exec",
            "APPS_SCRIPT_TOKEN": "tok",
        }.get(k, d)
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": True, "payload": json.dumps([{"count": 42}])}
        mock_requests.post.return_value = resp

        self.assertEqual(get_visit_count(), 42)

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_get_visit_count_defaults_to_zero_when_nothing_saved_yet(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k, d="": {
            "APPS_SCRIPT_URL": "https://script.example/exec",
            "APPS_SCRIPT_TOKEN": "tok",
        }.get(k, d)
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"success": True, "payload": None}
        mock_requests.post.return_value = resp

        self.assertEqual(get_visit_count(), 0)

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_get_visit_count_fails_quiet_on_error(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = Exception("No secrets found")
        self.assertEqual(get_visit_count(), 0)


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


class TestRequireAuthBetaSignupTab(unittest.TestCase):
    """require_auth()'s "Beta Sign Up" tab only appears when
    CRTC_BETA_INVITE_CODES is configured, and only a matching, unused code
    can ever create an account through it."""

    def _configured_mock(self, mock_st, admin_password="correct horse battery staple", beta_codes="ABC123"):
        secrets = _real_admin_secrets(admin_password)
        secrets["CRTC_BETA_INVITE_CODES"] = beta_codes
        secrets["APPS_SCRIPT_URL"] = "https://script.example/exec"
        secrets["APPS_SCRIPT_TOKEN"] = "tok"
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        mock_st.stop.side_effect = _Stopped
        mock_st.rerun.side_effect = _Reran
        mock_st.tabs.return_value = [mock.MagicMock(), mock.MagicMock()]
        return secrets

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_beta_tab_rendered_when_codes_configured(self, mock_st, mock_requests):
        mock_st.session_state.get.return_value = False
        self._configured_mock(mock_st)
        mock_st.form_submit_button.return_value = False

        with self.assertRaises(_Stopped):
            require_auth()

        mock_st.tabs.assert_called_once_with(["Log In", "Beta Sign Up"])

    @mock.patch("auth.st")
    def test_no_beta_tab_when_codes_not_configured(self, mock_st):
        # Same as plain TestRequireAuth: no CRTC_BETA_INVITE_CODES secret.
        mock_st.session_state.get.return_value = False
        secrets = _real_admin_secrets("correct horse battery staple")
        mock_st.secrets.get.side_effect = lambda k, d="": secrets.get(k, d)
        mock_st.stop.side_effect = _Stopped
        mock_st.form_submit_button.return_value = False

        with self.assertRaises(_Stopped):
            require_auth()

        mock_st.tabs.assert_not_called()

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_valid_invite_code_signs_up_and_reruns(self, mock_st, mock_requests):
        mock_st.session_state.get.return_value = False
        self._configured_mock(mock_st)
        # Login form isn't submitted; the beta signup form is.
        mock_st.form_submit_button.side_effect = [False, True]
        mock_st.text_input.side_effect = [
            "", "",  # login form fields (unused, submitted=False)
            "New User", "newuser", "somepassword", "somepassword", "ABC123",  # signup fields
        ]
        load_resp = mock.Mock()
        load_resp.raise_for_status.return_value = None
        load_resp.json.return_value = {"success": True, "payload": None}
        save_resp = mock.Mock()
        save_resp.raise_for_status.return_value = None
        save_resp.json.return_value = {"success": True}
        # require_auth() also calls _record_visit_once() first (2 POSTs:
        # load then save the shared counter), before _beta_signup's own
        # load-then-save (2 more) -- same response shapes work for both.
        mock_requests.post.side_effect = [load_resp, save_resp, load_resp, save_resp]

        with self.assertRaises(_Reran):
            require_auth()

        mock_st.success.assert_called()
        self.assertEqual(mock_st.session_state.user_plan, "beta")
        self.assertTrue(mock_st.session_state.user_is_paid)
        self.assertFalse(mock_st.session_state.user_is_admin)

    @mock.patch("auth.requests")
    @mock.patch("auth.st")
    def test_invalid_invite_code_shows_error_and_stops(self, mock_st, mock_requests):
        mock_st.session_state.get.return_value = False
        self._configured_mock(mock_st)
        mock_st.form_submit_button.side_effect = [False, True]
        mock_st.text_input.side_effect = [
            "", "",
            "New User", "newuser", "somepassword", "somepassword", "WRONG-CODE",
        ]

        with self.assertRaises(_Stopped):
            require_auth()

        mock_st.error.assert_called()
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
            "user_plan": "hunter",
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
        self.assertNotIn("user_plan", state)
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
