"""Tenant context primitives for Appraze's public SaaS.

This module deliberately contains no Streamlit UI and no persistence calls.
It provides one server-side-derived tenant identity for application services.
The tenant is derived from the authenticated session, never from a browser
supplied workspace id.

The existing owner data remains in the legacy ``business`` workspace during
migration; ``OWNER_TENANT_ID`` is the stable application-level identity for
that workspace. Customer tenant ids are deterministic from their normalized
account username, while the demo tenant is permanently isolated.
"""

from dataclasses import dataclass
import re
from typing import Mapping, Optional

OWNER_TENANT_ID = "owner"
DEMO_TENANT_ID = "demo"


def _normalize_username(username: str) -> str:
    value = str(username or "").strip().lower()
    if not value:
        raise ValueError("authenticated username is required")
    if len(value) > 128:
        raise ValueError("authenticated username is too long")
    return value


def customer_tenant_id(username: str) -> str:
    """Return the stable tenant id for an authenticated customer account."""
    normalized = _normalize_username(username)
    # Keep the generated id opaque-ish and filesystem/storage safe. The
    # username itself is not exposed as the workspace key.
    slug = re.sub(r"[^a-z0-9._-]+", "-", normalized).strip("-")
    if not slug:
        raise ValueError("username cannot produce a tenant id")
    return f"tenant:{slug}"


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    role: str
    username: str = ""
    is_demo: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == "ADMIN"

    @property
    def is_customer(self) -> bool:
        return self.role == "CUSTOMER"


def tenant_from_session(session: Mapping[str, object]) -> Optional[TenantContext]:
    """Build tenant context from trusted server-side session state.

    Returns None when the session is not authenticated. ``workspace`` is
    intentionally ignored: callers cannot select another tenant by putting a
    different workspace id into session state or a request parameter.
    """
    if not bool(session.get("authenticated", False)) and not bool(session.get("authed", False)):
        return None

    username = str(session.get("username", "")).strip()
    is_admin = bool(session.get("user_is_admin", False))
    is_demo = bool(session.get("user_is_demo", False))

    if is_demo:
        return TenantContext(DEMO_TENANT_ID, "DEMO", username=username, is_demo=True)
    if is_admin:
        return TenantContext(OWNER_TENANT_ID, "ADMIN", username=username)
    if not username:
        return None
    return TenantContext(customer_tenant_id(username), "CUSTOMER", username=username)


def require_tenant(session: Mapping[str, object]) -> TenantContext:
    context = tenant_from_session(session)
    if context is None:
        raise PermissionError("authenticated tenant context is required")
    return context
