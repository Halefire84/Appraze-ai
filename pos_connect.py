"""
pos_connect.py — Appraze POS backend for the mobile apps (Stripe Connect).

WHY THIS EXISTS
---------------
Android v5 asked each merchant to paste their Stripe SECRET key into the
phone, stored it in EncryptedSharedPreferences, and called api.stripe.com
directly. A secret key inside a distributed app can be pulled off a rooted
or backed-up device and used to move money, issue refunds and read every
customer in that Stripe account. Secrets must never live on-device.

THE NEW MODEL
-------------
- Appraze is a Stripe Connect *platform*. The ONLY Stripe secret is the
  platform key (STRIPE_PLATFORM_SECRET_KEY), and it lives on this server.
- A merchant taps "Connect Stripe" in the app. This server creates a
  Standard-style connected account (full Stripe Dashboard, merchant pays
  their own Stripe fees, Stripe owns onboarding/KYC and negative-balance
  liability) and returns a Stripe-hosted onboarding link. The merchant
  finishes setup on Stripe's site, never in Appraze.
- The app receives a random *device token* (256-bit) that maps to that
  connected account. The phone stores only this token. It is not a Stripe
  credential: it can only ask THIS server to create/check Checkout Sessions
  that pay the merchant's own account, and the merchant can revoke it
  (Disconnect) at any time. Only a SHA-256 hash of it is stored here.
- Each charge is a one-time Stripe Checkout Session created *on the
  connected account* (Stripe-Account header = a "direct charge"). Money
  settles to the merchant's Stripe balance and bank, never through Appraze.
  Checkout Sessions are used instead of Payment Links because a Payment
  Link can be paid any number of times; a Session is paid once.
- The same invoice_id always maps to the same Stripe Idempotency-Key, so an
  app retry after a timeout returns the SAME session instead of a second one
  (same rule as pos.py on the web).

TAP TO PAY (in person): the same device token also drives Stripe Terminal
Tap to Pay on Android. The server creates a Terminal location (the
merchant's business address), connection tokens and card_present
PaymentIntents — all ON the merchant's connected account — so the phone's
NFC reader charges the customer's card straight into the merchant's
balance. Whether a tap payment succeeded is always re-read from Stripe here,
never taken from the app's word.

NOT the Appraze subscription flow: Appraze's own revenue (Play Billing / web
Stripe subscription in billing.py) is separate and untouched by this module.

ENVIRONMENT
-----------
    STRIPE_PLATFORM_SECRET_KEY   Appraze platform key (restricted key with
                                 Connect + Checkout write access recommended).
    POS_PUBLIC_BASE_URL          https URL where this service is reachable;
                                 used for Stripe return/refresh/success pages.
    POS_CONNECT_DB               SQLite path for device tokens (default
                                 ./pos_connect.sqlite3). Must be on a
                                 persistent disk in production.
    POS_CONNECT_ALLOW_LIVE       must be "1" to use an sk_live_/rk_live_ key.
                                 Default refuses live keys (sandbox only until
                                 the owner explicitly flips it).
    POS_MAX_AMOUNT_CENTS         per-charge ceiling (default 1000000 = $10,000).
    STRIPE_API_BASE              override for tests (stripe-mock); default
                                 https://api.stripe.com.
"""

from __future__ import annotations

import hashlib
import html
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from typing import Any, Callable, Deque, Dict, Optional, Tuple

import requests
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger("pos_connect")

STRIPE_API_BASE_DEFAULT = "https://api.stripe.com"
MIN_AMOUNT_CENTS = 50  # Stripe's USD minimum charge
DEFAULT_MAX_AMOUNT_CENTS = 1_000_000
MAX_DESCRIPTION_LEN = 200
INVOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SESSION_ID_RE = re.compile(r"^cs_[A-Za-z0-9_]{1,250}$")
PAYMENT_INTENT_ID_RE = re.compile(r"^pi_[A-Za-z0-9_]{1,250}$")
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


class PosConnectError(Exception):
    """An error with an HTTP status and a message safe to show the app user."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

def _platform_key() -> str:
    key = os.environ.get("STRIPE_PLATFORM_SECRET_KEY", "").strip()
    if not key:
        raise PosConnectError(503, "POS server is not configured (no Stripe platform key).")
    is_live = key.startswith("sk_live_") or key.startswith("rk_live_")
    if is_live and os.environ.get("POS_CONNECT_ALLOW_LIVE", "") != "1":
        raise PosConnectError(503, "POS live mode is not enabled on this server.")
    return key


def _public_base() -> str:
    base = os.environ.get("POS_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise PosConnectError(503, "POS server is not configured (no public base URL).")
    return base


def _max_amount_cents() -> int:
    try:
        return int(os.environ.get("POS_MAX_AMOUNT_CENTS", DEFAULT_MAX_AMOUNT_CENTS))
    except ValueError:
        return DEFAULT_MAX_AMOUNT_CENTS


# --------------------------------------------------------------------------
# Stripe HTTP client (no SDK — same approach as pos.py / billing.py)
# --------------------------------------------------------------------------

def _flatten(params: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """Stripe form encoding: {"a": {"b": 1}} -> {"a[b]": "1"}; lists by index."""
    out: Dict[str, str] = {}
    for k, v in params.items():
        key = f"{prefix}[{k}]" if prefix else str(k)
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        elif isinstance(v, (list, tuple)):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    out.update(_flatten(item, f"{key}[{i}]"))
                else:
                    out[f"{key}[{i}]"] = str(item)
        elif isinstance(v, bool):
            out[key] = "true" if v else "false"
        elif v is not None:
            out[key] = str(v)
    return out


class StripeClient:
    def __init__(self, secret_key: str, api_base: Optional[str] = None,
                 http: Optional[requests.Session] = None, timeout: float = 20.0):
        self.secret_key = secret_key
        self.api_base = (api_base or os.environ.get("STRIPE_API_BASE") or STRIPE_API_BASE_DEFAULT).rstrip("/")
        self.http = http or requests.Session()
        self.timeout = timeout

    def request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, *,
                account: Optional[str] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.secret_key}"}
        if account:
            headers["Stripe-Account"] = account
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        url = self.api_base + path
        data = _flatten(params or {})
        try:
            if method == "GET":
                resp = self.http.get(url, params=data, headers=headers, timeout=self.timeout)
            else:
                resp = self.http.post(url, data=data, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            logger.warning("Stripe request failed: %s %s: %s", method, path, type(e).__name__)
            raise PosConnectError(502, "Couldn't reach Stripe. Try again.")
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code >= 400:
            err = body.get("error") if isinstance(body, dict) else None
            msg = (err or {}).get("message") or f"Stripe returned HTTP {resp.status_code}."
            code = (err or {}).get("code") or ""
            logger.warning("Stripe error %s on %s %s: %s", resp.status_code, method, path, code or msg)
            if code == "idempotency_key_in_use" or "idempotent" in msg.lower():
                raise PosConnectError(409, "This invoice was already used for a different charge. Start a new sale.")
            status = 404 if resp.status_code == 404 else 502
            raise PosConnectError(status, f"Stripe error: {msg}")
        return body if isinstance(body, dict) else {}


# --------------------------------------------------------------------------
# Device-token store
# --------------------------------------------------------------------------

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenStore:
    """Maps sha256(device_token) -> connected account id. SQLite, one
    connection per call so it is safe under the threaded ASGI server."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get("POS_CONNECT_DB", "pos_connect.sqlite3")
        self._lock = threading.Lock()
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS pos_devices ("
                " token_hash TEXT PRIMARY KEY,"
                " account_id TEXT NOT NULL,"
                " created_at TEXT NOT NULL,"
                " revoked_at TEXT)"
            )
            c.execute(
                "CREATE TABLE IF NOT EXISTS pos_locations ("
                " account_id TEXT PRIMARY KEY,"
                " location_id TEXT NOT NULL,"
                " created_at TEXT NOT NULL)"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def issue(self, account_id: str) -> str:
        token = "apt_" + secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO pos_devices (token_hash, account_id, created_at) VALUES (?, ?, ?)",
                      (hash_token(token), account_id, now))
        return token

    def account_for(self, token: str) -> Optional[str]:
        if not token:
            return None
        with self._conn() as c:
            row = c.execute("SELECT account_id FROM pos_devices WHERE token_hash = ? AND revoked_at IS NULL",
                            (hash_token(token),)).fetchone()
        return row[0] if row else None

    def location_for(self, account_id: str) -> Optional[str]:
        with self._conn() as c:
            row = c.execute("SELECT location_id FROM pos_locations WHERE account_id = ?",
                            (account_id,)).fetchone()
        return row[0] if row else None

    def save_location(self, account_id: str, location_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as c:
            c.execute("INSERT OR REPLACE INTO pos_locations (account_id, location_id, created_at) VALUES (?, ?, ?)",
                      (account_id, location_id, now))

    def revoke(self, token: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn() as c:
            cur = c.execute("UPDATE pos_devices SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                            (now, hash_token(token)))
        return cur.rowcount > 0


# --------------------------------------------------------------------------
# Rate limiting (in-process; see docs/POS_STRIPE_CONNECT.md for limits)
# --------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._clock = clock

    def allow(self, bucket: str, key: str, limit: int, window_s: float) -> bool:
        now = self._clock()
        with self._lock:
            q = self._hits[(bucket, key)]
            while q and now - q[0] >= window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


# --------------------------------------------------------------------------
# Input validation (app input is untrusted)
# --------------------------------------------------------------------------

def validate_amount_cents(value: Any) -> int:
    # bool is an int subclass in Python — never accept True as 1 cent.
    if isinstance(value, bool) or not isinstance(value, int):
        raise PosConnectError(400, "amount_cents must be a whole number of cents.")
    max_cents = _max_amount_cents()
    if value < MIN_AMOUNT_CENTS:
        raise PosConnectError(400, "Amount must be at least $0.50.")
    if value > max_cents:
        raise PosConnectError(400, f"Amount is over the ${max_cents / 100:,.2f} per-charge limit.")
    return value


def validate_description(value: Any) -> str:
    if not isinstance(value, str):
        raise PosConnectError(400, "Add a description.")
    d = _CONTROL_CHARS_RE.sub(" ", value).strip()
    if not d:
        raise PosConnectError(400, "Add a description.")
    if len(d) > MAX_DESCRIPTION_LEN:
        raise PosConnectError(400, f"Description is over {MAX_DESCRIPTION_LEN} characters.")
    return d


def validate_invoice_id(value: Any) -> str:
    if value is None or value == "":
        return f"AND-{date.today().isoformat()}-{secrets.token_hex(4)}"
    if not isinstance(value, str) or not INVOICE_ID_RE.match(value):
        raise PosConnectError(400, "invoice_id must be 1-64 letters, digits, '-' or '_'.")
    return value


def _clean_text(value: Any, field: str, max_len: int, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise PosConnectError(400, f"{field} must be text.")
    v = _CONTROL_CHARS_RE.sub(" ", value).strip()
    if required and not v:
        raise PosConnectError(400, f"{field} is required.")
    if len(v) > max_len:
        raise PosConnectError(400, f"{field} is over {max_len} characters.")
    return v


def validate_location(body: Dict[str, Any]) -> Dict[str, Any]:
    """A Stripe Terminal location needs a real business address (Stripe uses
    it for tax and card-network rules)."""
    country = _clean_text(body.get("country") or "US", "Country", 2).upper()
    if not COUNTRY_RE.match(country):
        raise PosConnectError(400, "Country must be a 2-letter code like US.")
    return {
        "display_name": _clean_text(body.get("display_name"), "Business name", 100),
        "address": {
            "line1": _clean_text(body.get("line1"), "Street address", 200),
            "city": _clean_text(body.get("city"), "City", 100),
            "state": _clean_text(body.get("state"), "State", 50, required=(country == "US")),
            "postal_code": _clean_text(body.get("postal_code"), "ZIP / postal code", 20),
            "country": country,
        },
    }


def iso_from_unix(ts: Any) -> Optional[str]:
    """Stripe 'created' (unix seconds) -> ISO-8601 UTC, for sale logs."""
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Core operations (framework-free so they are unit-testable)
# --------------------------------------------------------------------------

class PosConnectService:
    def __init__(self, store: TokenStore, client_factory: Optional[Callable[[], StripeClient]] = None):
        self.store = store
        self._client_factory = client_factory or (lambda: StripeClient(_platform_key()))

    def client(self) -> StripeClient:
        return self._client_factory()

    def _onboarding_link(self, client: StripeClient, account_id: str) -> str:
        base = _public_base()
        link = client.request("POST", "/v1/account_links", {
            "account": account_id,
            "type": "account_onboarding",
            "refresh_url": f"{base}/pos/connect/refresh",
            "return_url": f"{base}/pos/connect/return",
        })
        url = link.get("url")
        if not url:
            raise PosConnectError(502, "Stripe returned no onboarding link.")
        return url

    def start(self) -> Dict[str, Any]:
        client = self.client()
        acct = client.request("POST", "/v1/accounts", {
            "controller": {
                "stripe_dashboard": {"type": "full"},
                "fees": {"payer": "account"},
                "losses": {"payments": "stripe"},
                "requirement_collection": "stripe",
            },
            "metadata": {"source": "appraze_android_pos"},
        }, idempotency_key="pos-acct-" + secrets.token_hex(16))
        account_id = acct.get("id")
        if not account_id:
            raise PosConnectError(502, "Stripe returned no account id.")
        url = self._onboarding_link(client, account_id)
        token = self.store.issue(account_id)
        logger.info("POS connect started for %s", account_id)
        return {"device_token": token, "account_id": account_id, "onboarding_url": url}

    def status(self, account_id: str) -> Dict[str, Any]:
        acct = self.client().request("GET", f"/v1/accounts/{account_id}")
        return {
            "account_id": account_id,
            "charges_enabled": bool(acct.get("charges_enabled")),
            "details_submitted": bool(acct.get("details_submitted")),
        }

    def link(self, account_id: str) -> Dict[str, Any]:
        return {"onboarding_url": self._onboarding_link(self.client(), account_id)}

    def checkout(self, account_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        amount = validate_amount_cents(body.get("amount_cents"))
        desc = validate_description(body.get("description"))
        invoice_id = validate_invoice_id(body.get("invoice_id"))
        client = self.client()
        acct = client.request("GET", f"/v1/accounts/{account_id}")
        if not acct.get("charges_enabled"):
            raise PosConnectError(409, "Finish Stripe setup before taking payments.")
        base = _public_base()
        session = client.request("POST", "/v1/checkout/sessions", {
            "mode": "payment",
            "line_items": [{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": amount,
                    "product_data": {"name": desc},
                },
                "quantity": 1,
            }],
            "client_reference_id": invoice_id,
            "metadata": {"invoice_id": invoice_id, "source": "appraze_android_pos"},
            "payment_intent_data": {"metadata": {"invoice_id": invoice_id, "source": "appraze_android_pos"}},
            "success_url": f"{base}/pos/checkout/done",
            "cancel_url": f"{base}/pos/checkout/cancelled",
        }, account=account_id, idempotency_key=f"pos-checkout-{account_id}-{invoice_id}")
        if not session.get("url") or not session.get("id"):
            raise PosConnectError(502, "Stripe returned no checkout page.")
        logger.info("POS checkout %s created on %s: invoice=%s amount_cents=%s",
                    session["id"], account_id, invoice_id, amount)
        return {"checkout_url": session["url"], "session_id": session["id"],
                "invoice_id": invoice_id, "amount_cents": amount,
                "created_at": iso_from_unix(session.get("created")) or utc_now_iso()}

    def checkout_status(self, account_id: str, session_id: str) -> Dict[str, Any]:
        if not SESSION_ID_RE.match(session_id or ""):
            raise PosConnectError(400, "Invalid session id.")
        # Retrieved on the caller's own account: another merchant's session id 404s.
        s = self.client().request("GET", f"/v1/checkout/sessions/{session_id}", account=account_id)
        return {
            "session_id": session_id,
            "status": s.get("status"),
            "payment_status": s.get("payment_status"),
            "paid": s.get("payment_status") == "paid",
            "amount_total": s.get("amount_total"),
            "invoice_id": (s.get("metadata") or {}).get("invoice_id"),
            "created_at": iso_from_unix(s.get("created")),
            "checked_at": utc_now_iso(),
        }

    # ---- Tap to Pay (Stripe Terminal, card-present, on the merchant's account) ----

    def _require_charges_enabled(self, client: StripeClient, account_id: str) -> None:
        acct = client.request("GET", f"/v1/accounts/{account_id}")
        if not acct.get("charges_enabled"):
            raise PosConnectError(409, "Finish Stripe setup before taking payments.")

    def terminal_location(self, account_id: str) -> Dict[str, Any]:
        return {"location_id": self.store.location_for(account_id)}

    def create_terminal_location(self, account_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        params = validate_location(body)
        existing = self.store.location_for(account_id)
        if existing:
            return {"location_id": existing, "created": False}
        loc = self.client().request("POST", "/v1/terminal/locations", params, account=account_id,
                                    idempotency_key=f"pos-loc-{account_id}")
        location_id = loc.get("id")
        if not location_id:
            raise PosConnectError(502, "Stripe returned no location id.")
        self.store.save_location(account_id, location_id)
        logger.info("POS Terminal location %s created on %s", location_id, account_id)
        return {"location_id": location_id, "created": True}

    def connection_token(self, account_id: str) -> Dict[str, Any]:
        location_id = self.store.location_for(account_id)
        if not location_id:
            raise PosConnectError(409, "Add your business address before using Tap to Pay.")
        tok = self.client().request("POST", "/v1/terminal/connection_tokens",
                                    {"location": location_id}, account=account_id)
        secret = tok.get("secret")
        if not secret:
            raise PosConnectError(502, "Stripe returned no connection token.")
        return {"secret": secret, "location_id": location_id}

    def create_tap_payment(self, account_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        amount = validate_amount_cents(body.get("amount_cents"))
        desc = validate_description(body.get("description"))
        invoice_id = validate_invoice_id(body.get("invoice_id"))
        client = self.client()
        self._require_charges_enabled(client, account_id)
        pi = client.request("POST", "/v1/payment_intents", {
            "amount": amount,
            "currency": "usd",
            "payment_method_types": ["card_present"],
            "capture_method": "automatic",
            "description": desc,
            "metadata": {"invoice_id": invoice_id, "source": "appraze_android_tap_to_pay"},
        }, account=account_id, idempotency_key=f"pos-tap-{account_id}-{invoice_id}")
        if not pi.get("id") or not pi.get("client_secret"):
            raise PosConnectError(502, "Stripe returned no payment.")
        logger.info("POS tap payment %s created on %s: invoice=%s amount_cents=%s",
                    pi["id"], account_id, invoice_id, amount)
        return {"payment_intent_id": pi["id"], "client_secret": pi["client_secret"],
                "invoice_id": invoice_id, "amount_cents": amount,
                "created_at": iso_from_unix(pi.get("created")) or utc_now_iso()}

    def tap_payment_status(self, account_id: str, payment_intent_id: str) -> Dict[str, Any]:
        if not PAYMENT_INTENT_ID_RE.match(payment_intent_id or ""):
            raise PosConnectError(400, "Invalid payment id.")
        # Server-side truth: the app's own "success" callback is never the record of payment.
        pi = self.client().request("GET", f"/v1/payment_intents/{payment_intent_id}", account=account_id)
        return {
            "payment_intent_id": payment_intent_id,
            "status": pi.get("status"),
            "paid": pi.get("status") == "succeeded",
            "amount_received": pi.get("amount_received"),
            "invoice_id": (pi.get("metadata") or {}).get("invoice_id"),
            "created_at": iso_from_unix(pi.get("created")),
            "checked_at": utc_now_iso(),
        }


# --------------------------------------------------------------------------
# HTTP layer
# --------------------------------------------------------------------------

_limiter = RateLimiter()
_service: Optional[PosConnectService] = None
_service_lock = threading.Lock()

# (limit, window seconds)
LIMIT_START_PER_IP = (5, 3600.0)
LIMIT_START_GLOBAL = (200, 86400.0)
LIMIT_AUTHED_PER_TOKEN = (60, 60.0)
LIMIT_CHECKOUT_PER_ACCOUNT = (30, 60.0)
LIMIT_TERMINAL_TOKEN_PER_ACCOUNT = (30, 60.0)


def get_service() -> PosConnectService:
    global _service
    with _service_lock:
        if _service is None:
            _service = PosConnectService(TokenStore())
        return _service


def set_service(service: Optional[PosConnectService], limiter: Optional[RateLimiter] = None) -> None:
    """Test hook: swap the service (and optionally reset the rate limiter)."""
    global _service, _limiter
    with _service_lock:
        _service = service
    if limiter is not None:
        _limiter = limiter


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _bearer(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _err(e: PosConnectError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content={"ok": False, "error": e.message})


def _limit(bucket: str, key: str, rule: Tuple[int, float]) -> None:
    if not _limiter.allow(bucket, key, rule[0], rule[1]):
        raise PosConnectError(429, "Too many requests. Wait a minute and try again.")


def _authed_account(request: Request) -> Tuple[str, str]:
    token = _bearer(request)
    account = get_service().store.account_for(token) if token else None
    if not account:
        raise PosConnectError(401, "This device isn't connected to Stripe. Connect again.")
    _limit("authed", hash_token(token), LIMIT_AUTHED_PER_TOKEN)
    return token, account


async def _json_body(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        raise PosConnectError(400, "Request body must be JSON.")
    if not isinstance(body, dict):
        raise PosConnectError(400, "Request body must be a JSON object.")
    return body


router = APIRouter()


@router.post("/pos/connect/start")
def connect_start(request: Request):
    try:
        _limit("start_ip", _client_ip(request), LIMIT_START_PER_IP)
        _limit("start_global", "all", LIMIT_START_GLOBAL)
        return {"ok": True, **get_service().start()}
    except PosConnectError as e:
        return _err(e)


@router.get("/pos/connect/status")
def connect_status(request: Request):
    try:
        _, account = _authed_account(request)
        return {"ok": True, **get_service().status(account)}
    except PosConnectError as e:
        return _err(e)


@router.post("/pos/connect/link")
def connect_link(request: Request):
    try:
        _, account = _authed_account(request)
        return {"ok": True, **get_service().link(account)}
    except PosConnectError as e:
        return _err(e)


@router.post("/pos/disconnect")
def disconnect(request: Request):
    try:
        token, account = _authed_account(request)
        get_service().store.revoke(token)
        logger.info("POS device token revoked for %s", account)
        return {"ok": True}
    except PosConnectError as e:
        return _err(e)


@router.post("/pos/checkout")
async def checkout(request: Request):
    try:
        _, account = _authed_account(request)
        body = await _json_body(request)
        _limit("checkout", account, LIMIT_CHECKOUT_PER_ACCOUNT)
        result = await run_in_threadpool(get_service().checkout, account, body)
        return {"ok": True, **result}
    except PosConnectError as e:
        return _err(e)


@router.get("/pos/checkout/{session_id}/status")
def checkout_status(session_id: str, request: Request):
    try:
        _, account = _authed_account(request)
        return {"ok": True, **get_service().checkout_status(account, session_id)}
    except PosConnectError as e:
        return _err(e)


@router.get("/pos/terminal/location")
def terminal_location(request: Request):
    try:
        _, account = _authed_account(request)
        return {"ok": True, **get_service().terminal_location(account)}
    except PosConnectError as e:
        return _err(e)


@router.post("/pos/terminal/location")
async def create_terminal_location(request: Request):
    try:
        _, account = _authed_account(request)
        body = await _json_body(request)
        result = await run_in_threadpool(get_service().create_terminal_location, account, body)
        return {"ok": True, **result}
    except PosConnectError as e:
        return _err(e)


@router.post("/pos/terminal/connection_token")
def terminal_connection_token(request: Request):
    try:
        _, account = _authed_account(request)
        _limit("terminal_token", account, LIMIT_TERMINAL_TOKEN_PER_ACCOUNT)
        return {"ok": True, **get_service().connection_token(account)}
    except PosConnectError as e:
        return _err(e)


@router.post("/pos/terminal/payment_intent")
async def terminal_payment_intent(request: Request):
    try:
        _, account = _authed_account(request)
        body = await _json_body(request)
        _limit("checkout", account, LIMIT_CHECKOUT_PER_ACCOUNT)
        result = await run_in_threadpool(get_service().create_tap_payment, account, body)
        return {"ok": True, **result}
    except PosConnectError as e:
        return _err(e)


@router.get("/pos/terminal/payment_intent/{payment_intent_id}/status")
def terminal_payment_status(payment_intent_id: str, request: Request):
    try:
        _, account = _authed_account(request)
        return {"ok": True, **get_service().tap_payment_status(account, payment_intent_id)}
    except PosConnectError as e:
        return _err(e)


def _page(title: str, message: str) -> HTMLResponse:
    body = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#FAF8F3;color:#1C1B1F;"
        "display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0;padding:24px}"
        "main{max-width:420px;text-align:center}h1{color:#8C6D1F;font-size:22px}</style></head>"
        f"<body><main><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p></main></body></html>"
    )
    return HTMLResponse(body)


@router.get("/pos/connect/return")
def connect_return():
    return _page("Stripe setup saved", "Return to Appraze and open the POS tab to check your status.")


@router.get("/pos/connect/refresh")
def connect_refresh():
    return _page("Link expired", "Return to Appraze and tap Finish Stripe Setup to get a fresh link.")


@router.get("/pos/checkout/done")
def checkout_done():
    return _page("Payment received", "Thank you. You can close this page.")


@router.get("/pos/checkout/cancelled")
def checkout_cancelled():
    return _page("Payment cancelled", "No charge was made. You can close this page.")
