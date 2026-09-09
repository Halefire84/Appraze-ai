import pytest

from tenant_context import (
    DEMO_TENANT_ID,
    OWNER_TENANT_ID,
    customer_tenant_id,
    require_tenant,
    tenant_from_session,
)


def test_admin_session_maps_to_owner_tenant():
    ctx = require_tenant(
        {
            "authenticated": True,
            "username": "Chris",
            "user_is_admin": True,
            "workspace": "attacker-supplied-value",
        }
    )
    assert ctx.tenant_id == OWNER_TENANT_ID
    assert ctx.is_admin
    assert not ctx.is_demo


def test_customers_get_distinct_tenants():
    alice = require_tenant({"authenticated": True, "username": "Alice"})
    bob = require_tenant({"authenticated": True, "username": "Bob"})
    assert alice.is_customer
    assert bob.is_customer
    assert alice.tenant_id != bob.tenant_id
    assert alice.tenant_id == customer_tenant_id("alice")


def test_demo_isolation_is_explicit():
    ctx = require_tenant(
        {"authenticated": True, "username": "demo", "user_is_demo": True}
    )
    assert ctx.tenant_id == DEMO_TENANT_ID
    assert ctx.is_demo
    assert not ctx.is_admin


def test_unauthenticated_session_has_no_tenant():
    assert tenant_from_session({}) is None
    with pytest.raises(PermissionError):
        require_tenant({})


def test_workspace_value_cannot_change_customer_tenant():
    session = {
        "authenticated": True,
        "username": "alice",
        "workspace": "tenant:bob",
    }
    ctx = require_tenant(session)
    assert ctx.tenant_id == customer_tenant_id("alice")


def test_empty_customer_username_is_rejected():
    with pytest.raises(PermissionError):
        require_tenant({"authenticated": True, "username": ""})
