"""Authentication for Appraze.

The deployment supports a shared owner/admin account plus normal customer
accounts. Customer sessions are later mapped to their own tenant by
``tenant_context.py``; browser-supplied workspace values are never trusted.
"""

import hashlib
import hmac
from dataclasses import dataclass

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
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _secret(key: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(key, default))
    except Exception:
        return default


def _apps_script_url() -> str:
    url = _secret("APPS_SCRIPT_URL")
    if not url:
        raise RuntimeError("APPS_SCRIPT_URL is not set in Streamlit secrets.")
    return url


def _token() -> str:
    token = _secret("APPS_SCRIPT_TOKEN")
    if not token:
        raise RuntimeError("APPS_SCRIPT_TOKEN is not set in Streamlit secrets.")
    return token


def _admin_credentials_configured() -> bool:
    username = _secret("CRTC_ADMIN_USERNAME").strip()
    password_hash = _secret("CRTC_ADMIN_PASSWORD_HASH").strip().lower()
    return bool(username and len(password_hash) == 64)


def _admin_login(username: str, password: str) -> AuthResult | None:
    if not _admin_credentials_configured():
        return None
    configured_username = _secret("CRTC_ADMIN_USERNAME").strip().lower()
    configured_hash = _secret("CRTC_ADMIN_PASSWORD_HASH").strip().lower()
    if str(username).strip().lower() != configured_username:
        return None
    if not hmac.compare_digest(_hash_password(password), configured_hash):
        return AuthResult(False, error="incorrect password")
    return AuthResult(
        True,
        display_name="Appraze Admin",
        is_admin=True,
        is_paid=True,
        username=configured_username,
    )


def _set_session(result: AuthResult, is_demo: bool = False) -> None:
    st.session_state.authenticated = True
    st.session_state.user_display_name = result.display_name
    st.session_state.user_is_admin = result.is_admin
    st.session_state.user_is_paid = result.is_paid
    st.session_state.username = result.username
    st.session_state.user_is_demo = is_demo


def current_tenant():
    """Return the server-derived tenant context for the current session."""
    from tenant_context import tenant_from_session
    return tenant_from_session(st.session_state)


def signup(username: str, password: str, display_name: str = "", admin_code: str = "") -> AuthResult:
    try:
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
            return AuthResult(
                True,
                data.get("display_name", username),
                data.get("is_admin", False),
                data.get("is_paid", False),
                username=data.get("username", username.lower()),
            )
        return AuthResult(False, error=data.get("error", "signup failed"))
    except Exception as e:
        return AuthResult(False, error=f"connection error: {e}")


def login(username: str, password: str) -> AuthResult:
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
            return AuthResult(
                True,
                data.get("display_name", username),
                data.get("is_admin", False),
                data.get("is_paid", False),
                username=data.get("username", username.lower()),
            )
        return AuthResult(False, error=data.get("error", "login failed"))
    except Exception as e:
        return AuthResult(False, error=f"connection error: {e}")


def mark_paid(username: str) -> bool:
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
    if st.session_state.get("authenticated"):
        return True

    st.markdown("## 🪙 Appraze")
    st.caption("Resale intelligence workspace — sign in or create your account")

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
                        _set_session(result)
                        st.rerun()
                    else:
                        st.error(result.error)

    with tab_signup:
        st.caption("Create a customer account. Your data is isolated from other accounts.")
        with st.form("signup_form"):
            new_display = st.text_input("Your name", key="signup_display")
            new_u = st.text_input("Choose a username", key="signup_username")
            new_p = st.text_input("Choose a password", type="password", key="signup_password")
            new_p2 = st.text_input("Confirm password", type="password", key="signup_password2")
            admin_code = st.text_input("Admin invite code (optional)", type="password", key="signup_admin_code")
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
                        _set_session(result)
                        st.success(f"Welcome, {result.display_name}!")
                        st.rerun()
                    else:
                        st.error(result.error)
    return False


def logout() -> None:
    for key in (
        "authenticated",
        "user_display_name",
        "user_is_admin",
        "user_is_paid",
        "username",
        "user_is_demo",
    ):
        st.session_state.pop(key, None)


def require_auth() -> None:
    """Require a valid Appraze account on every Streamlit page.

    This intentionally accepts both the shared Admin account and normal
    customer accounts. Each authenticated session receives its tenant from
    server-side identity; no page may select a tenant through ``workspace``.
    """
    if st.session_state.get("authenticated"):
        if current_tenant() is None:
            logout()
        else:
            return
    render_login_gate()
    st.stop()
