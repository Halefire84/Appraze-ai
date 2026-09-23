"""
Cooper River Trading Co. — CRTC Auth Module
------------------------------------------------
Authentication for the CRTC resale intelligence app.

Production model:
- One shared Admin login for the owners (you + Ashley).
- Admin credentials come from Streamlit secrets, never source control.
- Admin sessions map to the existing shared `admin_shared` workspace.
- Public/demo users can use the existing isolated demo mode without
  touching real account data.
- Optional tester signup/login remains available for future paid users.

The shared Admin password is verified locally against a bcrypt hash stored
in Streamlit secrets (CRTC_ADMIN_PASSWORD_HASH) -- see AUTH_SETUP.md for
the migration off the old unsalted-SHA-256 scheme and how to generate a
bcrypt hash. Admin login is also rate-limited: repeated wrong passwords for
the same username trigger an exponential-backoff lockout (see
_record_failed_login below) so the shared credential can't be brute-forced
by an unattended script.

The separate tester signup/login path below still hashes passwords with
SHA-256 client-side before sending them to the Apps Script backend
(AppsScript_Code.gs) -- that backend is a different system, out of this
module's control, and already expects that exact wire format. It is not
the credential this fix addresses; nothing this app stores or compares
locally still uses unsalted SHA-256.
"""

import hashlib
import re
import threading
import time
from dataclasses import dataclass
from typing import Dict

import bcrypt
import requests
import streamlit as st


@dataclass
class AuthResult:
    success: bool
    display_name: str = ""
    is_admin: bool = False
    is_paid: bool = False
    username: str = ""
    error: str = ""


def _hash_password(password: str) -> str:
    """SHA-256 wire hash for the Apps Script tester-account backend only --
    see the module docstring. Never used for the local Admin credential."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


_BCRYPT_HASH_RE = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")


def _looks_like_bcrypt_hash(value: str) -> bool:
    return bool(_BCRYPT_HASH_RE.match(value or ""))


def _verify_admin_password(password: str, bcrypt_hash: str) -> bool:
    """Constant-time bcrypt comparison. bcrypt.checkpw raises on a malformed
    hash (e.g. a leftover SHA-256 hex string from before the migration) --
    treated as "does not match" rather than a crash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), bcrypt_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Brute-force protection for the shared Admin login.
#
# Deliberately process-global (not st.session_state, which is per-browser-
# session and trivially bypassed by opening a new one) and in-memory (not a
# new external dependency for a single-shared-credential app). This bounds
# an unattended password-guessing script to a handful of attempts per
# backoff window; it does not protect against a distributed attack spread
# across many app instances, which is out of scope for this single-process
# deployment model (same limitation as decision_policy.EventLog's in-memory
# state).
# ---------------------------------------------------------------------------
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_BASE_SECONDS = 30.0
LOCKOUT_MAX_SECONDS = 15 * 60.0

_login_attempts_lock = threading.Lock()
_login_attempts: Dict[str, Dict[str, float]] = {}


def _seconds_until_unlock(username: str) -> float:
    with _login_attempts_lock:
        state = _login_attempts.get(username)
        if not state:
            return 0.0
        return max(0.0, state["locked_until"] - time.time())


def _record_failed_login(username: str) -> None:
    with _login_attempts_lock:
        state = _login_attempts.setdefault(username, {"count": 0.0, "locked_until": 0.0})
        state["count"] += 1
        if state["count"] >= MAX_LOGIN_ATTEMPTS:
            backoff = min(LOCKOUT_MAX_SECONDS, LOCKOUT_BASE_SECONDS * (2 ** (state["count"] - MAX_LOGIN_ATTEMPTS)))
            state["locked_until"] = time.time() + backoff


def _clear_failed_logins(username: str) -> None:
    with _login_attempts_lock:
        _login_attempts.pop(username, None)


def _secret(key: str, default: str = "") -> str:
    """Read one Streamlit secret, failing safe to `default` for ANY error --
    not just a missing key, but a deployment with no secrets store at all.
    st.secrets.get(key, default) does NOT protect against that second case:
    Secrets.get() only falls back to `default` on a missing *key* inside an
    existing store; when the store itself doesn't exist yet (a fresh deploy
    before any secret is set), the underlying access raises
    StreamlitSecretNotFoundError instead of returning. Every credential
    check in this file goes through here so "no secrets configured yet"
    means "treat as not configured", never an unhandled crash."""
    try:
        return str(st.secrets.get(key, default))
    except Exception:
        return default


def _apps_script_url() -> str:
    url = st.secrets.get("APPS_SCRIPT_URL")
    if not url:
        raise RuntimeError("APPS_SCRIPT_URL is not set in Streamlit secrets.")
    return url


def _token() -> str:
    token = st.secrets.get("APPS_SCRIPT_TOKEN")
    if not token:
        raise RuntimeError("APPS_SCRIPT_TOKEN is not set in Streamlit secrets.")
    return token


def _admin_credentials_configured() -> bool:
    """Return True when the dedicated shared Admin login is configured.

    Required secrets:
      CRTC_ADMIN_USERNAME
      CRTC_ADMIN_PASSWORD_HASH

    CRTC_ADMIN_PASSWORD_HASH must be a bcrypt hash of the desired password
    (e.g. `$2b$12$...`), not a raw SHA-256 hex digest -- see AUTH_SETUP.md
    for the migration and how to generate one. Keeping the hash in
    deployment secrets means the password is never committed to GitHub.
    """
    username = _secret("CRTC_ADMIN_USERNAME").strip()
    password_hash = _secret("CRTC_ADMIN_PASSWORD_HASH").strip()
    return bool(username and _looks_like_bcrypt_hash(password_hash))


def _admin_login(username: str, password: str) -> AuthResult | None:
    """Authenticate the single shared owner/admin account locally.

    Returning None means the dedicated Admin account isn't configured, so
    the normal Apps Script tester-account login should be attempted.
    """
    if not _admin_credentials_configured():
        return None

    configured_username = _secret("CRTC_ADMIN_USERNAME").strip().lower()
    configured_hash = _secret("CRTC_ADMIN_PASSWORD_HASH").strip()
    supplied_username = str(username).strip().lower()

    if supplied_username != configured_username:
        return None

    locked_for = _seconds_until_unlock(supplied_username)
    if locked_for > 0:
        return AuthResult(
            False,
            error=f"Too many failed attempts. Try again in {int(locked_for) + 1}s.",
        )

    if not _verify_admin_password(password, configured_hash):
        _record_failed_login(supplied_username)
        return AuthResult(False, error="incorrect password")

    _clear_failed_logins(supplied_username)
    return AuthResult(
        True,
        display_name="CRTC Admin",
        is_admin=True,
        is_paid=True,
        username=configured_username,
    )


def signup(username: str, password: str, display_name: str = "", admin_code: str = "") -> AuthResult:
    try:
        # POST, not GET - AppsScript_Code.gs's doPost reads e.parameter the
        # same way doGet does, but a GET here would put the auth token and
        # password hash in the URL, where they'd land in server access logs,
        # any proxy in between, and browser history.
        resp = requests.post(
            _apps_script_url(),
            data={
                "token": _token(),
                "action": "signup",
                "username": username,
                "password_hash": _hash_password(password),
                "display_name": display_name or username,
                "admin_code": admin_code,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return AuthResult(True, data.get("display_name", username), data.get("is_admin", False), data.get("is_paid", False), username=data.get("username", username.lower()))
        return AuthResult(False, error=data.get("error", "signup failed"))
    except Exception as e:
        return AuthResult(False, error=f"connection error: {e}")


def login(username: str, password: str) -> AuthResult:
    # Owner/admin login is intentionally checked first and does not depend on
    # the Google Sheet being reachable. This gives the two owners one simple
    # shared login while keeping the existing tester/paid-user system intact.
    admin_result = _admin_login(username, password)
    if admin_result is not None:
        return admin_result

    try:
        resp = requests.post(
            _apps_script_url(),
            data={
                "token": _token(),
                "action": "login",
                "username": username,
                "password_hash": _hash_password(password),
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            return AuthResult(True, data.get("display_name", username), data.get("is_admin", False), data.get("is_paid", False), username=data.get("username", username.lower()))
        return AuthResult(False, error=data.get("error", "login failed"))
    except Exception as e:
        return AuthResult(False, error=f"connection error: {e}")


def mark_paid(username: str) -> bool:
    """Called once a Stripe Checkout Session is verified as paid — persists it
    so the person doesn't have to pay again on their next login."""
    try:
        resp = requests.post(
            _apps_script_url(),
            data={"token": _token(), "action": "set_paid", "username": username},
            timeout=15,
        )
        resp.raise_for_status()
        return bool(resp.json().get("success"))
    except Exception:
        return False


def render_login_gate() -> bool:
    """
    Renders a login/signup form. Returns True if the current session is
    authenticated (and sets st.session_state.user_display_name / user_is_admin),
    False otherwise — caller should st.stop() when this returns False.
    """
    if st.session_state.get("authenticated"):
        return True

    st.markdown("## 🪙 CRTC")
    st.caption("Cooper River Trading Co. — private workspace")

    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            u = st.text_input("Username", key="login_username")
            p = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log In", use_container_width=True)
            if submitted:
                if not u or not p:
                    st.warning("Enter both a username and password.")
                else:
                    result = login(u, p)
                    if result.success:
                        st.session_state.authenticated = True
                        st.session_state.user_display_name = result.display_name
                        st.session_state.user_is_admin = result.is_admin
                        st.session_state.user_is_paid = result.is_paid
                        st.session_state.username = result.username
                        st.rerun()
                    else:
                        st.error(result.error)

    with tab_signup:
        st.caption("Tester accounts are optional. The two owners use the shared Admin login.")
        with st.form("signup_form"):
            new_display = st.text_input("Your name", key="signup_display")
            new_u = st.text_input("Choose a username", key="signup_username")
            new_p = st.text_input("Choose a password", type="password", key="signup_password")
            new_p2 = st.text_input("Confirm password", type="password", key="signup_password2")
            admin_code = st.text_input(
                "Admin invite code (leave blank unless you have one)",
                type="password",
                key="signup_admin_code",
            )
            submitted = st.form_submit_button("Create Account", use_container_width=True)
            if submitted:
                if not new_u or not new_p:
                    st.warning("Username and password are both required.")
                elif new_p != new_p2:
                    st.warning("Passwords don't match.")
                elif len(new_p) < 4:
                    st.warning("Password should be at least 4 characters.")
                else:
                    result = signup(new_u, new_p, new_display, admin_code)
                    if result.success:
                        st.session_state.authenticated = True
                        st.session_state.user_display_name = result.display_name
                        st.session_state.user_is_admin = result.is_admin
                        st.session_state.user_is_paid = result.is_paid
                        st.session_state.username = result.username
                        st.success(f"Welcome, {result.display_name}!")
                        st.rerun()
                    else:
                        st.error(result.error)

    return False


def logout() -> None:
    """Clear every session key an authenticated session sets. The one place
    both app.py's sidebar and any future page should call to sign out, so
    logout can never leave a stale key behind for a page that checks it."""
    for key in ("authenticated", "user_display_name", "user_is_admin", "user_is_paid", "username"):
        st.session_state.pop(key, None)


def require_auth() -> None:
    """
    The one authentication gate every production Streamlit page calls,
    right after st.set_page_config(), as its first line of real work:

        from auth import require_auth
        require_auth()

    This is deliberately NOT "check app.py's login and trust pages inherit
    it" -- Streamlit's pages/ directory makes every page independently
    reachable by its own URL without app.py's script ever running, so each
    page must enforce this for itself. require_auth() st.stop()s outright
    on any unauthenticated path (not configured, wrong credentials, no
    attempt yet) rather than returning a bool for the caller to check --
    a page that forgets an `if not require_auth(): st.stop()` check would
    silently render protected content, which is exactly the bug this
    exists to close everywhere at once.

    Reuses the existing single shared-Admin credential model (hashed
    CRTC_ADMIN_USERNAME / CRTC_ADMIN_PASSWORD_HASH secrets, see
    AUTH_SETUP.md) rather than a new auth system, and rather than the
    Apps-Script tester/signup path below -- this keeps the app the simple
    single-workspace Admin tool it's meant to be, not a multi-tenant
    product. If the Admin secrets aren't configured yet, this fails
    SAFE: no login form is even rendered (nothing to guess against), and
    there is no default/fallback password that ever grants access.
    """
    if st.session_state.get("authenticated"):
        return

    st.markdown("## 🪙 CRTC")
    st.caption("Cooper River Trading Co. — sign in to continue")

    if not _admin_credentials_configured():
        st.error(
            "Admin login is not configured for this deployment. Set "
            "CRTC_ADMIN_USERNAME and CRTC_ADMIN_PASSWORD_HASH in Streamlit "
            "Secrets before this app can be used — see AUTH_SETUP.md."
        )
        st.stop()

    with st.form("crtc_admin_login_form"):
        username = st.text_input("Username", key="crtc_login_username")
        password = st.text_input("Password", type="password", key="crtc_login_password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            if not username or not password:
                st.warning("Enter both a username and password.")
            else:
                result = _admin_login(username, password)
                if result is not None and result.success:
                    st.session_state.authenticated = True
                    st.session_state.user_display_name = result.display_name
                    st.session_state.user_is_admin = result.is_admin
                    st.session_state.username = result.username
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

    st.stop()
