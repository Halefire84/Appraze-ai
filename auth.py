"""
Appraze authentication helpers.

Authentication establishes a server-derived tenant context for the public SaaS.
The tenant id is never selected by a browser-supplied workspace value.
"""

import hashlib
from dataclasses import dataclass

import requests
import streamlit as st

from tenant_context import tenant_from_session


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
    username = str(st.secrets.get("CRTC_ADMIN_USERNAME", "")).strip()
    password_hash = str(st.secrets.get("CRTC_ADMIN_PASSWORD_HASH", "")).strip().lower()
    return bool(username and len(password_hash) == 64)


def _admin_login(username: str, password: str) -> AuthResult | None:
    if not _admin_credentials_configured():
        return None
    configured_username = str(st.secrets.get("CRTC_ADMIN_USERNAME", "")).strip().lower()
    configured_hash = str(st.secrets.get("CRTC_ADMIN_PASSWORD_HASH", "")).strip().lower()
    if str(username).strip().lower() != configured_username:
        return None
    if _hash_password(password) != configured_hash:
        return AuthResult(False, error="incorrect password")
    return AuthResult(True, "Appraze Admin", True, True, configured_username)


def set_authenticated_session(result: AuthResult, *, is_demo: bool = False) -> None:
    """Set trusted authentication fields and derive the tenant server-side."""
    st.session_state.authenticated = True
    st.session_state.user_display_name = result.display_name
    st.session_state.user_is_admin = result.is_admin
    st.session_state.user_is_paid = result.is_paid
    st.session_state.username = result.username
    st.session_state.user_is_demo = is_demo

    context = tenant_from_session(st.session_state)
    if context is None:
        raise RuntimeError("Authenticated session could not establish tenant context.")
    st.session_state.tenant_id = context.tenant_id
    st.session_state.user_role = context.role


def current_tenant():
    """Return the server-derived tenant for the current authenticated session."""
    return tenant_from_session(st.session_state)


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
                data.get("username", username.lower()),
            )
        return AuthResult(False, error=data.get("error", "login failed"))
    except Exception as e:
        return AuthResult(False, error=f"connection error: {e}")


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
                data.get("username", username.lower()),
            )
        return AuthResult(False, error=data.get("error", "signup failed"))
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
        # Re-derive on every page execution so stale/mutated workspace values
        # cannot silently become an authorization boundary.
        context = current_tenant()
        if context is None:
            st.session_state.authenticated = False
            return False
        st.session_state.tenant_id = context.tenant_id
        st.session_state.user_role = context.role
        return True

    st.markdown("## 🪙 Appraze")
    st.caption("Sign in to your private Appraze workspace")
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
                        set_authenticated_session(result)
                        st.rerun()
                    else:
                        st.error(result.error)

    with tab_signup:
        st.caption("Create your own private customer workspace.")
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
                        set_authenticated_session(result)
                        st.rerun()
                    else:
                        st.error(result.error)
    return False
