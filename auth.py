"""
Appraze — Auth Module
------------------------------------------------
Authentication for the Appraze resale intelligence app, by Cooper River
Trading Co. (CRTC).

Production model:
- One shared Admin login for the owners (you + Ashley).
- Admin credentials come from Streamlit secrets, never source control.
- Admin sessions map to the existing shared `admin_shared` workspace.
- Public/demo users can use the existing isolated demo mode without
  touching real account data.
- Optional tester signup/login remains available for future paid users.

Passwords are SHA-256 hashed client-side before ever leaving the app for
Apps Script authentication (the tester signup/login path -- see the
2026-09-21 note below, this path is currently unreachable dead code, no
page calls it). The production Admin password (the only password path
actually reachable today) is checked with bcrypt -- see
_admin_login()/_admin_credentials_configured() below.

2026-09-21 auth hardening: migrated the Admin account's password check
from unsalted SHA-256 (vulnerable to rainbow-table attacks if the stored
hash ever leaked) to bcrypt (per-hash random salt, tunable work factor).
Scoped to the Admin path only because it's the only one any live page
actually calls -- render_login_gate()/login()/signup() below are real,
tested code but nothing imports or calls them from app.py or any
pages/*.py file today, so their SHA-256 usage, while still worth fixing
before public signup ever gets wired in, isn't reachable by an attacker
right now. See BACKLOG.md / .agent/HANDOFF.md.

_admin_credentials_configured() accepts EITHER a bcrypt hash (the new
format, starts with $2a$/$2b$/$2y$) OR a legacy 64-char SHA-256 hex
hash, so an existing deployment's CRTC_ADMIN_PASSWORD_HASH secret keeps
working unchanged -- migrating to bcrypt requires the deployment owner
to regenerate that secret (see AUTH_SETUP.md), and forcing that
regeneration by shipping a bcrypt-only check would have locked the
owner out of their own app the moment this deployed. Legacy SHA-256
verification is still constant-time (hmac.compare_digest) and still
works; it's just not what new secrets should be generated with.
"""

import hashlib
import hmac
import re
import time
from dataclasses import dataclass

import bcrypt
import requests
import streamlit as st

_BCRYPT_HASH_RE = re.compile(r"^\$2[aby]\$\d{2}\$.{53}$")


@dataclass
class AuthResult:
    success: bool
    display_name: str = ""
    is_admin: bool = False
    is_paid: bool = False
    username: str = ""
    error: str = ""
    plan: str = "free"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


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


def _is_legacy_sha256_hash(value: str) -> bool:
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _admin_credentials_configured() -> bool:
    """Return True when the dedicated shared Admin login is configured.

    Required secrets:
      CRTC_ADMIN_USERNAME
      CRTC_ADMIN_PASSWORD_HASH

    CRTC_ADMIN_PASSWORD_HASH is either a bcrypt hash (new, preferred --
    see AUTH_SETUP.md) or a legacy 64-char SHA-256 hex hash (still
    accepted so an existing deployment's secret keeps working unchanged).
    Keeping the hash in deployment secrets means the password is never
    committed to GitHub.
    """
    username = _secret("CRTC_ADMIN_USERNAME").strip()
    password_hash = _secret("CRTC_ADMIN_PASSWORD_HASH").strip()
    valid_format = bool(_BCRYPT_HASH_RE.match(password_hash)) or _is_legacy_sha256_hash(password_hash.lower())
    return bool(username and valid_format)


def _admin_login(username: str, password: str) -> AuthResult | None:
    """Authenticate the single shared owner/admin account locally.

    Returning None means the dedicated Admin account isn't configured, so
    the normal Apps Script tester-account login should be attempted.
    """
    if not _admin_credentials_configured():
        return None

    configured_username = _secret("CRTC_ADMIN_USERNAME").strip().lower()
    # NOT lowercased here -- a bcrypt hash's alphabet is case-sensitive
    # (unlike hex SHA-256, where case never mattered). Branch on format
    # before touching case.
    configured_hash = _secret("CRTC_ADMIN_PASSWORD_HASH").strip()
    supplied_username = str(username).strip().lower()

    if supplied_username != configured_username:
        return None

    if _BCRYPT_HASH_RE.match(configured_hash):
        password_ok = bcrypt.checkpw(password.encode("utf-8"), configured_hash.encode("utf-8"))
    else:
        # Legacy path -- still constant-time, still works, just not what
        # a freshly-generated secret should use. See AUTH_SETUP.md.
        password_ok = hmac.compare_digest(_hash_password(password), configured_hash.lower())
    if not password_ok:
        return AuthResult(False, error="incorrect password")

    return AuthResult(
        True,
        display_name="CRTC Admin",
        is_admin=True,
        is_paid=True,
        username=configured_username,
        plan="admin",
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
            return AuthResult(True, data.get("display_name", username), data.get("is_admin", False), data.get("is_paid", False), username=data.get("username", username.lower()), plan=data.get("plan", "free"))
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
            return AuthResult(True, data.get("display_name", username), data.get("is_admin", False), data.get("is_paid", False), username=data.get("username", username.lower()), plan=data.get("plan", "free"))
        return AuthResult(False, error=data.get("error", "login failed"))
    except Exception as e:
        return AuthResult(False, error=f"connection error: {e}")


def mark_paid(username: str, plan: str = "") -> bool:
    """Called once a Stripe Checkout Session is verified as paid — persists it
    so the person doesn't have to pay again on their next login. `plan` is
    one of subscription_plans.PLANS' keys (e.g. "hunter"); omit it to mark
    paid without changing which plan is on file (kept for any existing
    caller that only cares about the boolean)."""
    try:
        payload = {"token": _token(), "action": "set_paid", "username": username}
        if plan:
            payload["plan"] = plan
        resp = requests.post(_apps_script_url(), data=payload, timeout=15)
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

    st.markdown("## 🪙 Appraze™")
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
                        st.session_state.user_plan = result.plan
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
                        st.session_state.user_plan = result.plan
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
    for key in ("authenticated", "user_display_name", "user_is_admin", "user_is_paid", "user_plan", "username"):
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

    st.markdown("## 🪙 Appraze™")
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
                    st.session_state.user_is_paid = result.is_paid
                    st.session_state.user_plan = result.plan
                    st.session_state.username = result.username
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

    st.stop()
