"""
Tests for pos_connect.py — the Stripe Connect POS backend that replaced the
Android app's on-device Stripe secret key.

Two layers:
  * Unit/HTTP tests against a fake Stripe (always run, no network).
  * Contract tests against stripe-mock (Stripe's official OpenAPI-validated
    mock). Run only when STRIPE_MOCK_URL is set, e.g.:

        stripe-mock -http-port 12111 &
        STRIPE_MOCK_URL=http://localhost:12111 python3 -m pytest tests/test_pos_connect.py -v
"""

import os
import tempfile
import unittest
from unittest import mock

import requests
from fastapi.testclient import TestClient

import pos_connect
import stripe_webhook_server
from pos_connect import (
    PosConnectError,
    PosConnectService,
    RateLimiter,
    StripeClient,
    TokenStore,
    _flatten,
)

ENV = {
    "STRIPE_PLATFORM_SECRET_KEY": "sk_test_platform_123",
    "POS_PUBLIC_BASE_URL": "https://pos.example.test",
}


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeStripe:
    """Records calls and answers like Stripe for the handful of endpoints used."""

    def __init__(self, charges_enabled=True):
        self.calls = []
        self.charges_enabled = charges_enabled
        self.sessions = {}
        self.intents = {}
        self.fail_path = None  # (path suffix, FakeResponse) to return instead

    def _record(self, method, url, data, headers):
        self.calls.append({"method": method, "url": url, "data": dict(data or {}), "headers": dict(headers)})
        if self.fail_path and url.endswith(self.fail_path[0]):
            return self.fail_path[1]
        path = url.split("://", 1)[1].split("/", 1)[1]
        path = "/" + path
        if method == "POST" and path == "/v1/accounts":
            return FakeResponse(200, {"id": "acct_new1", "charges_enabled": False, "details_submitted": False})
        if method == "GET" and path.startswith("/v1/accounts/"):
            return FakeResponse(200, {"id": path.rsplit("/", 1)[1], "charges_enabled": self.charges_enabled,
                                      "details_submitted": self.charges_enabled})
        if method == "POST" and path == "/v1/account_links":
            return FakeResponse(200, {"url": "https://connect.stripe.com/setup/s/abc"})
        if method == "POST" and path == "/v1/checkout/sessions":
            key = headers.get("Idempotency-Key")
            if key not in self.sessions:
                self.sessions[key] = {
                    "id": f"cs_test_{len(self.sessions) + 1}",
                    "url": f"https://checkout.stripe.com/c/pay/cs_test_{len(self.sessions) + 1}",
                    "account": headers.get("Stripe-Account"),
                    "metadata": {"invoice_id": data.get("metadata[invoice_id]")},
                }
            return FakeResponse(200, self.sessions[key])
        if method == "GET" and path.startswith("/v1/checkout/sessions/"):
            sid = path.rsplit("/", 1)[1]
            for s in self.sessions.values():
                if s["id"] == sid and s["account"] == headers.get("Stripe-Account"):
                    return FakeResponse(200, {**s, "status": "complete", "payment_status": "paid",
                                              "amount_total": 1234})
            return FakeResponse(404, {"error": {"message": "No such checkout.session"}})
        if method == "POST" and path == "/v1/terminal/locations":
            return FakeResponse(200, {"id": "tml_1", "display_name": data.get("display_name")})
        if method == "POST" and path == "/v1/terminal/connection_tokens":
            return FakeResponse(200, {"secret": "pst_test_secret", "location": data.get("location")})
        if method == "POST" and path == "/v1/payment_intents":
            key = headers.get("Idempotency-Key")
            if key not in self.intents:
                n = len(self.intents) + 1
                self.intents[key] = {"id": f"pi_test_{n}", "client_secret": f"pi_test_{n}_secret_x",
                                     "created": 1790000000, "account": headers.get("Stripe-Account"),
                                     "metadata": {"invoice_id": data.get("metadata[invoice_id]")}}
            return FakeResponse(200, self.intents[key])
        if method == "GET" and path.startswith("/v1/payment_intents/"):
            pid = path.rsplit("/", 1)[1]
            for pi in self.intents.values():
                if pi["id"] == pid and pi["account"] == headers.get("Stripe-Account"):
                    return FakeResponse(200, {**pi, "status": "succeeded", "amount_received": 1234})
            return FakeResponse(404, {"error": {"message": "No such payment_intent"}})
        return FakeResponse(404, {"error": {"message": "unknown path " + path}})

    def post(self, url, data=None, headers=None, timeout=None):
        return self._record("POST", url, data, headers or {})

    def get(self, url, params=None, headers=None, timeout=None):
        return self._record("GET", url, params, headers or {})


class Base(unittest.TestCase):
    charges_enabled = True

    def setUp(self):
        self.env = mock.patch.dict(os.environ, ENV)
        self.env.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TokenStore(os.path.join(self.tmp.name, "pos.sqlite3"))
        self.fake = FakeStripe(charges_enabled=self.charges_enabled)
        self.service = PosConnectService(
            self.store, client_factory=lambda: StripeClient(pos_connect._platform_key(), http=self.fake))
        pos_connect.set_service(self.service, RateLimiter())
        self.client = TestClient(stripe_webhook_server.app)

    def tearDown(self):
        pos_connect.set_service(None, RateLimiter())
        self.env.stop()
        self.tmp.cleanup()

    def connect(self):
        r = self.client.post("/pos/connect/start")
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def auth(self, token):
        return {"Authorization": f"Bearer {token}"}


class TestConnectFlow(Base):
    def test_start_creates_standard_style_account_and_returns_token_not_secret(self):
        body = self.connect()
        self.assertEqual(body["account_id"], "acct_new1")
        self.assertTrue(body["device_token"].startswith("apt_"))
        self.assertEqual(body["onboarding_url"], "https://connect.stripe.com/setup/s/abc")
        self.assertNotIn("sk_test_platform_123", str(body))
        acct_call = self.fake.calls[0]
        self.assertEqual(acct_call["data"]["controller[stripe_dashboard][type]"], "full")
        self.assertEqual(acct_call["data"]["controller[fees][payer]"], "account")
        self.assertEqual(acct_call["data"]["controller[losses][payments]"], "stripe")
        link_call = self.fake.calls[1]
        self.assertEqual(link_call["data"]["return_url"], "https://pos.example.test/pos/connect/return")
        self.assertEqual(link_call["data"]["type"], "account_onboarding")

    def test_token_is_stored_hashed_only(self):
        body = self.connect()
        import sqlite3
        rows = sqlite3.connect(self.store.path).execute("SELECT token_hash, account_id FROM pos_devices").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0][0], body["device_token"])
        self.assertEqual(rows[0][0], pos_connect.hash_token(body["device_token"]))

    def test_status_requires_token(self):
        self.assertEqual(self.client.get("/pos/connect/status").status_code, 401)
        r = self.client.get("/pos/connect/status", headers=self.auth("apt_bogus"))
        self.assertEqual(r.status_code, 401)

    def test_status_reports_account_state(self):
        tok = self.connect()["device_token"]
        r = self.client.get("/pos/connect/status", headers=self.auth(tok))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["charges_enabled"])

    def test_link_returns_fresh_onboarding_url(self):
        tok = self.connect()["device_token"]
        r = self.client.post("/pos/connect/link", headers=self.auth(tok))
        self.assertEqual(r.json()["onboarding_url"], "https://connect.stripe.com/setup/s/abc")

    def test_disconnect_revokes_token(self):
        tok = self.connect()["device_token"]
        self.assertEqual(self.client.post("/pos/disconnect", headers=self.auth(tok)).status_code, 200)
        self.assertEqual(self.client.get("/pos/connect/status", headers=self.auth(tok)).status_code, 401)

    def test_start_is_rate_limited_per_ip(self):
        for _ in range(pos_connect.LIMIT_START_PER_IP[0]):
            self.connect()
        r = self.client.post("/pos/connect/start")
        self.assertEqual(r.status_code, 429)


class TestCheckout(Base):
    def setUp(self):
        super().setUp()
        self.token = self.connect()["device_token"]

    def checkout(self, **body):
        return self.client.post("/pos/checkout", json=body, headers=self.auth(self.token))

    def test_creates_direct_charge_session_on_connected_account(self):
        r = self.checkout(amount_cents=1234, description="Vintage lamp", invoice_id="AND-1")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["checkout_url"].startswith("https://checkout.stripe.com/"))
        self.assertEqual(body["invoice_id"], "AND-1")
        call = [c for c in self.fake.calls if c["url"].endswith("/v1/checkout/sessions")][0]
        self.assertEqual(call["headers"]["Stripe-Account"], "acct_new1")
        self.assertEqual(call["headers"]["Authorization"], "Bearer sk_test_platform_123")
        self.assertEqual(call["headers"]["Idempotency-Key"], "pos-checkout-acct_new1-AND-1")
        self.assertEqual(call["data"]["line_items[0][price_data][unit_amount]"], "1234")
        self.assertEqual(call["data"]["mode"], "payment")
        self.assertEqual(call["data"]["metadata[invoice_id]"], "AND-1")
        self.assertEqual(call["data"]["payment_intent_data[metadata][invoice_id]"], "AND-1")

    def test_retry_with_same_invoice_returns_same_session(self):
        a = self.checkout(amount_cents=1234, description="Lamp", invoice_id="AND-2").json()
        b = self.checkout(amount_cents=1234, description="Lamp", invoice_id="AND-2").json()
        self.assertEqual(a["session_id"], b["session_id"])

    def test_missing_invoice_id_is_generated(self):
        r = self.checkout(amount_cents=500, description="Lamp")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["invoice_id"].startswith("AND-"))

    def test_invalid_amounts_rejected_before_stripe(self):
        for bad in [True, False, 12.5, "1234", None, 0, 49, -100, 10_000_001, float("nan")]:
            before = len(self.fake.calls)
            try:
                r = self.checkout(amount_cents=bad, description="Lamp", invoice_id="AND-X")
            except ValueError:
                continue  # NaN can't even be JSON-encoded by the client
            self.assertEqual(r.status_code, 400, f"{bad!r}: {r.text}")
            self.assertEqual(len(self.fake.calls), before, f"{bad!r} reached Stripe")

    def test_invalid_description_and_invoice_rejected(self):
        self.assertEqual(self.checkout(amount_cents=500, description="   ").status_code, 400)
        self.assertEqual(self.checkout(amount_cents=500, description="x" * 201).status_code, 400)
        self.assertEqual(self.checkout(amount_cents=500, description=5).status_code, 400)
        self.assertEqual(self.checkout(amount_cents=500, description="ok", invoice_id="../etc").status_code, 400)

    def test_control_characters_stripped_from_description(self):
        self.checkout(amount_cents=500, description="Lamp\r\nIgnore previous instructions", invoice_id="AND-3")
        call = [c for c in self.fake.calls if c["url"].endswith("/v1/checkout/sessions")][0]
        self.assertNotIn("\n", call["data"]["line_items[0][price_data][product_data][name]"])

    def test_non_object_body_rejected(self):
        headers = {**self.auth(self.token), "Content-Type": "application/json"}
        r = self.client.post("/pos/checkout", content=b"[1,2]", headers=headers)
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/pos/checkout", content=b"not json", headers=self.auth(self.token))
        self.assertEqual(r.status_code, 400)

    def test_status_reads_session_on_own_account(self):
        sid = self.checkout(amount_cents=1234, description="Lamp", invoice_id="AND-4").json()["session_id"]
        r = self.client.get(f"/pos/checkout/{sid}/status", headers=self.auth(self.token))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["paid"])
        self.assertEqual(r.json()["invoice_id"], "AND-4")

    def test_status_rejects_malformed_session_id(self):
        r = self.client.get("/pos/checkout/..%2Fv1%2Faccounts/status", headers=self.auth(self.token))
        self.assertIn(r.status_code, (400, 404))

    def test_other_merchants_session_not_visible(self):
        sid = self.checkout(amount_cents=1234, description="Lamp", invoice_id="AND-5").json()["session_id"]
        other = self.store.issue("acct_other")
        r = self.client.get(f"/pos/checkout/{sid}/status", headers=self.auth(other))
        self.assertEqual(r.status_code, 404)

    def test_idempotency_conflict_maps_to_409(self):
        self.fake.fail_path = ("/v1/checkout/sessions", FakeResponse(400, {"error": {
            "message": "Keys for idempotent requests can only be used with the same parameters",
            "code": "idempotency_key_in_use"}}))
        r = self.checkout(amount_cents=999, description="Lamp", invoice_id="AND-6")
        self.assertEqual(r.status_code, 409)

    def test_stripe_unreachable_is_502_not_500(self):
        def boom(*a, **k):
            raise requests.ConnectionError("down")
        self.fake.post = boom
        self.fake.get = boom
        r = self.checkout(amount_cents=999, description="Lamp", invoice_id="AND-7")
        self.assertEqual(r.status_code, 502)


ADDRESS = {"display_name": "Cooper River Trading", "line1": "1 Main St", "city": "Charleston",
           "state": "SC", "postal_code": "29401", "country": "US"}


class TestTapToPay(Base):
    def setUp(self):
        super().setUp()
        self.token = self.connect()["device_token"]

    def post(self, path, body=None):
        return self.client.post(path, json=body, headers=self.auth(self.token))

    def add_location(self):
        r = self.post("/pos/terminal/location", ADDRESS)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_location_created_on_connected_account_once(self):
        self.assertIsNone(self.client.get("/pos/terminal/location", headers=self.auth(self.token))
                          .json()["location_id"])
        first = self.add_location()
        self.assertEqual(first, {"ok": True, "location_id": "tml_1", "created": True})
        second = self.add_location()
        self.assertFalse(second["created"])
        loc_calls = [c for c in self.fake.calls if c["url"].endswith("/v1/terminal/locations")]
        self.assertEqual(len(loc_calls), 1)
        self.assertEqual(loc_calls[0]["headers"]["Stripe-Account"], "acct_new1")
        self.assertEqual(loc_calls[0]["data"]["address[state]"], "SC")

    def test_location_validation(self):
        self.assertEqual(self.post("/pos/terminal/location", {**ADDRESS, "line1": ""}).status_code, 400)
        self.assertEqual(self.post("/pos/terminal/location", {**ADDRESS, "country": "USA"}).status_code, 400)
        self.assertEqual(self.post("/pos/terminal/location", {**ADDRESS, "state": ""}).status_code, 400)
        self.assertEqual(self.post("/pos/terminal/location", {**ADDRESS, "city": 5}).status_code, 400)
        self.assertEqual(self.post("/pos/terminal/location", {**ADDRESS, "display_name": "x" * 101})
                         .status_code, 400)
        # Non-US addresses may omit state.
        self.assertEqual(self.post("/pos/terminal/location", {**ADDRESS, "state": "", "country": "gb"})
                         .status_code, 200)

    def test_connection_token_requires_location(self):
        self.assertEqual(self.post("/pos/terminal/connection_token").status_code, 409)
        self.add_location()
        r = self.post("/pos/terminal/connection_token")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["secret"], "pst_test_secret")
        call = [c for c in self.fake.calls if c["url"].endswith("/v1/terminal/connection_tokens")][0]
        self.assertEqual(call["headers"]["Stripe-Account"], "acct_new1")
        self.assertEqual(call["data"]["location"], "tml_1")

    def test_connection_token_requires_auth(self):
        self.assertEqual(self.client.post("/pos/terminal/connection_token").status_code, 401)

    def test_tap_payment_is_card_present_on_merchant_account_with_timestamp(self):
        r = self.post("/pos/terminal/payment_intent",
                      {"amount_cents": 1234, "description": "Lamp", "invoice_id": "TAP-1"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["payment_intent_id"], "pi_test_1")
        self.assertEqual(body["client_secret"], "pi_test_1_secret_x")
        self.assertEqual(body["created_at"], "2026-09-21T14:13:20+00:00")
        call = [c for c in self.fake.calls if c["url"].endswith("/v1/payment_intents")][0]
        self.assertEqual(call["headers"]["Stripe-Account"], "acct_new1")
        self.assertEqual(call["headers"]["Idempotency-Key"], "pos-tap-acct_new1-TAP-1")
        self.assertEqual(call["data"]["payment_method_types[0]"], "card_present")
        self.assertEqual(call["data"]["amount"], "1234")
        self.assertEqual(call["data"]["capture_method"], "automatic")

    def test_tap_retry_same_invoice_same_intent(self):
        a = self.post("/pos/terminal/payment_intent", {"amount_cents": 800, "description": "x", "invoice_id": "T2"})
        b = self.post("/pos/terminal/payment_intent", {"amount_cents": 800, "description": "x", "invoice_id": "T2"})
        self.assertEqual(a.json()["payment_intent_id"], b.json()["payment_intent_id"])

    def test_tap_payment_validates_like_checkout(self):
        for bad in [True, 49, "100", 10_000_001]:
            r = self.post("/pos/terminal/payment_intent", {"amount_cents": bad, "description": "x"})
            self.assertEqual(r.status_code, 400, bad)
        self.assertFalse(any(c["url"].endswith("/v1/payment_intents") for c in self.fake.calls))

    def test_tap_status_is_read_from_stripe_on_own_account(self):
        created = self.post("/pos/terminal/payment_intent",
                            {"amount_cents": 1234, "description": "Lamp", "invoice_id": "TAP-3"})
        pid = created.json()["payment_intent_id"]
        r = self.client.get(f"/pos/terminal/payment_intent/{pid}/status", headers=self.auth(self.token))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["paid"])
        self.assertEqual(r.json()["invoice_id"], "TAP-3")
        self.assertIn("checked_at", r.json())
        other = self.store.issue("acct_other")
        r = self.client.get(f"/pos/terminal/payment_intent/{pid}/status", headers=self.auth(other))
        self.assertEqual(r.status_code, 404)
        r = self.client.get("/pos/terminal/payment_intent/cs_nope/status", headers=self.auth(self.token))
        self.assertEqual(r.status_code, 400)

    def test_checkout_response_has_timestamp(self):
        r = self.post("/pos/checkout", {"amount_cents": 500, "description": "Lamp", "invoice_id": "L1"})
        self.assertIn("created_at", r.json())


class TestOnboardingIncomplete(Base):
    charges_enabled = False

    def test_checkout_blocked_until_charges_enabled(self):
        tok = self.connect()["device_token"]
        r = self.client.post("/pos/checkout", json={"amount_cents": 500, "description": "Lamp"},
                             headers=self.auth(tok))
        self.assertEqual(r.status_code, 409)
        self.assertFalse(any(c["url"].endswith("/v1/checkout/sessions") for c in self.fake.calls))

    def test_tap_payment_blocked_until_charges_enabled(self):
        tok = self.connect()["device_token"]
        r = self.client.post("/pos/terminal/payment_intent", json={"amount_cents": 500, "description": "Lamp"},
                             headers=self.auth(tok))
        self.assertEqual(r.status_code, 409)


class TestConfigGuards(Base):
    def test_live_key_refused_by_default(self):
        with mock.patch.dict(os.environ, {"STRIPE_PLATFORM_SECRET_KEY": "sk_live_abc"}):
            r = self.client.post("/pos/connect/start")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.fake.calls, [])

    def test_live_key_allowed_only_with_explicit_flag(self):
        with mock.patch.dict(os.environ, {"STRIPE_PLATFORM_SECRET_KEY": "rk_live_abc",
                                          "POS_CONNECT_ALLOW_LIVE": "1"}):
            self.assertEqual(pos_connect._platform_key(), "rk_live_abc")

    def test_missing_key_is_503(self):
        with mock.patch.dict(os.environ, {"STRIPE_PLATFORM_SECRET_KEY": ""}):
            self.assertEqual(self.client.post("/pos/connect/start").status_code, 503)

    def test_missing_public_base_is_503(self):
        with mock.patch.dict(os.environ, {"POS_PUBLIC_BASE_URL": ""}):
            self.assertEqual(self.client.post("/pos/connect/start").status_code, 503)

    def test_static_pages_do_not_need_auth(self):
        for path in ["/pos/connect/return", "/pos/connect/refresh", "/pos/checkout/done",
                     "/pos/checkout/cancelled"]:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn("text/html", r.headers["content-type"])

    def test_existing_webhook_health_still_works(self):
        self.assertEqual(self.client.get("/healthz").json()["ok"], True)


class TestHelpers(unittest.TestCase):
    def test_flatten_nested(self):
        self.assertEqual(_flatten({"a": {"b": 1, "c": [{"d": "x"}]}, "e": True, "f": None}),
                         {"a[b]": "1", "a[c][0][d]": "x", "e": "true"})

    def test_rate_limiter_window(self):
        now = [0.0]
        rl = RateLimiter(clock=lambda: now[0])
        self.assertTrue(rl.allow("b", "k", 2, 10))
        self.assertTrue(rl.allow("b", "k", 2, 10))
        self.assertFalse(rl.allow("b", "k", 2, 10))
        now[0] = 10.0
        self.assertTrue(rl.allow("b", "k", 2, 10))

    def test_iso_from_unix(self):
        self.assertEqual(pos_connect.iso_from_unix(0), "1970-01-01T00:00:00+00:00")
        self.assertIsNone(pos_connect.iso_from_unix(None))
        self.assertIsNone(pos_connect.iso_from_unix(True))
        self.assertIsNone(pos_connect.iso_from_unix(1e20))

    def test_error_carries_status(self):
        e = PosConnectError(418, "x")
        self.assertEqual((e.status, e.message), (418, "x"))


@unittest.skipUnless(os.environ.get("STRIPE_MOCK_URL"), "set STRIPE_MOCK_URL to run stripe-mock contract tests")
class TestStripeMockContract(unittest.TestCase):
    """Every Stripe request this module sends is validated by stripe-mock
    against Stripe's published OpenAPI spec (unknown/invalid params -> 400)."""

    def setUp(self):
        self.env = mock.patch.dict(os.environ, ENV)
        self.env.start()
        self.tmp = tempfile.TemporaryDirectory()
        base = os.environ["STRIPE_MOCK_URL"]
        self.service = PosConnectService(
            TokenStore(os.path.join(self.tmp.name, "pos.sqlite3")),
            client_factory=lambda: StripeClient("sk_test_123", api_base=base))

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_full_flow_request_shapes_accepted(self):
        started = self.service.start()
        acct = started["account_id"]
        self.assertTrue(acct.startswith("acct_"))
        self.assertTrue(started["onboarding_url"].startswith("https://"))
        self.assertIn("charges_enabled", self.service.status(acct))
        self.assertTrue(self.service.link(acct)["onboarding_url"].startswith("https://"))
        # stripe-mock fixtures report charges_enabled=false; bypass that gate
        # to validate the checkout request shape itself.
        client = self.service.client()
        orig = client.request

        def request(method, path, params=None, **kw):
            if method == "GET" and path.startswith("/v1/accounts/"):
                return {"id": acct, "charges_enabled": True}
            return orig(method, path, params, **kw)
        client.request = request
        self.service._client_factory = lambda: client
        out = self.service.checkout(acct, {"amount_cents": 1234, "description": "Lamp", "invoice_id": "AND-M1"})
        self.assertTrue(out["session_id"].startswith("cs_"))
        self.assertTrue(out["checkout_url"].startswith("https://"))
        st = self.service.checkout_status(acct, out["session_id"])
        self.assertIn("payment_status", st)

    def test_tap_to_pay_request_shapes_accepted(self):
        acct = self.service.start()["account_id"]
        loc = self.service.create_terminal_location(acct, ADDRESS)
        self.assertTrue(loc["location_id"].startswith("tml_"))
        self.assertTrue(self.service.connection_token(acct)["secret"])
        client = self.service.client()
        orig = client.request

        def request(method, path, params=None, **kw):
            if method == "GET" and path.startswith("/v1/accounts/"):
                return {"id": acct, "charges_enabled": True}
            return orig(method, path, params, **kw)
        client.request = request
        self.service._client_factory = lambda: client
        pi = self.service.create_tap_payment(acct, {"amount_cents": 1234, "description": "Lamp",
                                                    "invoice_id": "TAP-M1"})
        self.assertTrue(pi["payment_intent_id"].startswith("pi_"))
        self.assertTrue(pi["client_secret"])
        self.assertIn("status", self.service.tap_payment_status(acct, pi["payment_intent_id"]))
