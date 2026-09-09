from tenant_context import DEMO_TENANT_ID, OWNER_TENANT_ID, customer_tenant_id, require_tenant, tenant_from_session


def test_admin_tenant_ignores_workspace_override():
    context = tenant_from_session({"authenticated": True, "username": "owner", "user_is_admin": True, "workspace": "attacker"})
    assert context.tenant_id == OWNER_TENANT_ID
    assert context.is_admin


def test_customers_get_distinct_tenants():
    assert customer_tenant_id("Alice") != customer_tenant_id("Bob")
    assert customer_tenant_id(" Alice ") == customer_tenant_id("alice")


def test_demo_is_isolated():
    context = tenant_from_session({"authenticated": True, "username": "demo", "user_is_demo": True, "user_is_admin": False})
    assert context.tenant_id == DEMO_TENANT_ID
    assert context.is_demo


def test_unauthenticated_has_no_tenant():
    assert tenant_from_session({}) is None


def test_workspace_cannot_change_customer_tenant():
    session = {"authenticated": True, "username": "alice", "workspace": "owner"}
    assert require_tenant(session).tenant_id == customer_tenant_id("alice")


def test_empty_customer_username_is_rejected():
    assert tenant_from_session({"authenticated": True, "user_is_admin": False}) is None
