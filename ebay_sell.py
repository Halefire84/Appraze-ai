"""CRTC eBay Sell API adapter — SANDBOX ONLY.

This is the publishing surface. It is deliberately separate from the eBay
BROWSE/finding code in `comps_adapters.py` / `ebay_holy_grail.py`, which only
reads market data with a client-credentials token. Publishing needs a *user*
token (authorization-code flow), a different app config, and different scopes,
so it gets its own module and its own `EBAY_SELL_*` environment prefix.

Every endpoint here points at eBay's sandbox. There is no production switch in
this milestone: `_SANDBOX_*` constants are the only hosts used, so a
misconfigured environment cannot accidentally post a real listing.

Publish flow (see `publish_master`):
    master listing record
      -> master_to_inventory_item()        (pure, unit-tested mapping)
      -> createOrReplaceInventoryItem(sku)
      -> createOffer(sku)                  (fixed price, FIXED_PRICE format)
      -> publishOffer(offerId)             -> eBay listingId

Secrets are read from the environment (or an untracked `ebay_config.json`) and
are never logged: `EbayConfig.__repr__` redacts them, and no function in this
module prints a token, code, or client secret.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# --- Sandbox endpoints. Intentionally not configurable in milestone 1. -------
_SANDBOX_AUTH_HOST = "https://auth.sandbox.ebay.com"
_SANDBOX_API_HOST = "https://api.sandbox.ebay.com"
AUTHORIZE_URL = f"{_SANDBOX_AUTH_HOST}/oauth2/authorize"
TOKEN_URL = f"{_SANDBOX_API_HOST}/identity/v1/oauth2/token"
INVENTORY_BASE = f"{_SANDBOX_API_HOST}/sell/inventory/v1"

DEFAULT_SCOPES = (
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",
)

CONFIG_FILE = Path("ebay_config.json")
TOKEN_FILE = Path(".ebay_tokens.json")

# Refresh a little early so a token can't expire mid-request.
_EXPIRY_SKEW_SECONDS = 120
_TIMEOUT = 30

# eBay condition enums keyed by the loose condition strings the app already
# stores on master listings (Flip Ledger free-texts these).
_CONDITION_MAP = {
    "new": "NEW",
    "brand new": "NEW",
    "new with tags": "NEW_WITH_TAGS",
    "new without tags": "NEW_WITHOUT_TAGS",
    "new other": "NEW_OTHER",
    "open box": "NEW_OTHER",
    "like new": "LIKE_NEW",
    "excellent": "USED_EXCELLENT",
    "very good": "USED_VERY_GOOD",
    "good": "USED_GOOD",
    "used": "USED_GOOD",
    "acceptable": "USED_ACCEPTABLE",
    "fair": "USED_ACCEPTABLE",
    "for parts": "FOR_PARTS_OR_NOT_WORKING",
    "parts only": "FOR_PARTS_OR_NOT_WORKING",
    "broken": "FOR_PARTS_OR_NOT_WORKING",
}
_DEFAULT_CONDITION = "USED_GOOD"


class EbaySellError(RuntimeError):
    """Any failure in the Sell API path: config, auth, or an eBay API error."""


class EbaySellConfigError(EbaySellError):
    """Required EBAY_SELL_* settings are missing."""


class EbaySellAuthError(EbaySellError):
    """No usable user token — the owner needs to run the authorize flow."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class EbayConfig:
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    redirect_uri: str = ""  # eBay calls this the RuName
    marketplace_id: str = "EBAY_US"
    merchant_location_key: str = ""
    fulfillment_policy_id: str = ""
    payment_policy_id: str = ""
    return_policy_id: str = ""

    def __repr__(self) -> str:  # never leak the secret into logs or tracebacks
        return (
            f"EbayConfig(client_id={'set' if self.client_id else 'unset'}, "
            f"client_secret={'set' if self.client_secret else 'unset'}, "
            f"redirect_uri={'set' if self.redirect_uri else 'unset'}, "
            f"marketplace_id={self.marketplace_id!r})"
        )

    def require_auth_fields(self) -> None:
        missing = [
            name
            for name, value in (
                ("EBAY_SELL_CLIENT_ID", self.client_id),
                ("EBAY_SELL_CLIENT_SECRET", self.client_secret),
                ("EBAY_SELL_REDIRECT_URI", self.redirect_uri),
            )
            if not value
        ]
        if missing:
            raise EbaySellConfigError(
                "Missing eBay Sell credentials: " + ", ".join(missing)
                + ". See docs/EBAY_SELL_SETUP.md."
            )

    def require_offer_fields(self) -> None:
        """Business policies + location are required by createOffer/publishOffer."""
        missing = [
            name
            for name, value in (
                ("EBAY_SELL_MERCHANT_LOCATION_KEY", self.merchant_location_key),
                ("EBAY_SELL_FULFILLMENT_POLICY_ID", self.fulfillment_policy_id),
                ("EBAY_SELL_PAYMENT_POLICY_ID", self.payment_policy_id),
                ("EBAY_SELL_RETURN_POLICY_ID", self.return_policy_id),
            )
            if not value
        ]
        if missing:
            raise EbaySellConfigError(
                "Missing eBay Sell offer settings: " + ", ".join(missing)
                + ". Create sandbox business policies and a merchant location first "
                "— see docs/EBAY_SELL_SETUP.md."
            )


def _config_file_values(path: Path = CONFIG_FILE) -> Dict[str, Any]:
    """Untracked local fallback for the environment. Missing/!invalid -> {}."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_config(env: Optional[Dict[str, str]] = None, config_path: Path = CONFIG_FILE) -> EbayConfig:
    """Build config from EBAY_SELL_* env vars, falling back to ebay_config.json.

    The `EBAY_SELL_` prefix keeps these distinct from the Browse-API
    EBAY_CLIENT_ID/EBAY_CLIENT_SECRET used by comps_adapters.py — the two are
    usually different eBay applications (production keys vs sandbox keys).
    """
    env = os.environ if env is None else env
    file_values = _config_file_values(config_path)

    def pick(key: str, default: str = "") -> str:
        value = env.get(f"EBAY_SELL_{key}") or file_values.get(key) or file_values.get(f"EBAY_SELL_{key}")
        return str(value).strip() if value else default

    return EbayConfig(
        client_id=pick("CLIENT_ID"),
        client_secret=pick("CLIENT_SECRET"),
        redirect_uri=pick("REDIRECT_URI"),
        marketplace_id=pick("MARKETPLACE_ID", "EBAY_US"),
        merchant_location_key=pick("MERCHANT_LOCATION_KEY"),
        fulfillment_policy_id=pick("FULFILLMENT_POLICY_ID"),
        payment_policy_id=pick("PAYMENT_POLICY_ID"),
        return_policy_id=pick("RETURN_POLICY_ID"),
    )


def write_config_template(path: Path = CONFIG_FILE) -> Path:
    """Create an untracked ebay_config.json template with empty values.

    Never overwrites an existing file — the owner's real keys live here.
    """
    if path.exists():
        return path
    template = {
        "_comment": "SANDBOX eBay Sell API keys. Untracked (.gitignore). Never commit.",
        "CLIENT_ID": "",
        "CLIENT_SECRET": "",
        "REDIRECT_URI": "",
        "MARKETPLACE_ID": "EBAY_US",
        "MERCHANT_LOCATION_KEY": "",
        "FULFILLMENT_POLICY_ID": "",
        "PAYMENT_POLICY_ID": "",
        "RETURN_POLICY_ID": "",
    }
    path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# OAuth2 authorization-code flow
# ---------------------------------------------------------------------------
def get_authorization_url(
    scopes: Optional[List[str]] = None,
    redirect_uri: Optional[str] = None,
    config: Optional[EbayConfig] = None,
    state: Optional[str] = None,
) -> str:
    """Build the sandbox consent URL the owner opens in a browser."""
    config = config or load_config()
    config.require_auth_fields()
    params = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri or config.redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes or DEFAULT_SCOPES),
    }
    if state:
        params["state"] = state
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _basic_auth_header(config: EbayConfig) -> str:
    raw = f"{config.client_id}:{config.client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _post_token(config: EbayConfig, payload: Dict[str, str]) -> Dict[str, Any]:
    try:
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(config),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data=payload,
            timeout=_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        raise EbaySellAuthError(f"eBay token request failed: {exc}") from exc
    if resp.status_code >= 400:
        # Bodies here can echo the grant; surface eBay's error code only.
        raise EbaySellAuthError(
            f"eBay token request rejected (HTTP {resp.status_code}): {_error_summary(resp)}"
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise EbaySellAuthError("eBay token response was not JSON.") from exc


def _store_tokens(data: Dict[str, Any], token_path: Path, previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Persist tokens with an absolute expiry. Refresh responses often omit
    refresh_token, so carry the previous one forward."""
    previous = previous or {}
    tokens = {
        "access_token": data.get("access_token", ""),
        "expires_at": time.time() + float(data.get("expires_in") or 0),
        "refresh_token": data.get("refresh_token") or previous.get("refresh_token", ""),
        "refresh_token_expires_at": (
            time.time() + float(data["refresh_token_expires_in"])
            if data.get("refresh_token_expires_in")
            else previous.get("refresh_token_expires_at")
        ),
        "token_type": data.get("token_type", "User Access Token"),
    }
    save_tokens(tokens, token_path)
    return tokens


def load_tokens(token_path: Path = TOKEN_FILE) -> Dict[str, Any]:
    try:
        data = json.loads(Path(token_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_tokens(tokens: Dict[str, Any], token_path: Path = TOKEN_FILE) -> None:
    path = Path(token_path)
    path.write_text(json.dumps(tokens, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)  # best effort; some filesystems reject it
    except OSError:
        pass


def exchange_code_for_tokens(
    code: str,
    config: Optional[EbayConfig] = None,
    token_path: Path = TOKEN_FILE,
) -> Dict[str, Any]:
    """Trade the ?code= from the consent redirect for user tokens."""
    config = config or load_config()
    config.require_auth_fields()
    if not code or not str(code).strip():
        raise EbaySellAuthError("No authorization code supplied.")
    data = _post_token(
        config,
        {
            "grant_type": "authorization_code",
            "code": urllib.parse.unquote(str(code).strip()),
            "redirect_uri": config.redirect_uri,
        },
    )
    return _store_tokens(data, token_path)


def refresh_access_token(
    config: Optional[EbayConfig] = None,
    token_path: Path = TOKEN_FILE,
) -> Dict[str, Any]:
    config = config or load_config()
    config.require_auth_fields()
    tokens = load_tokens(token_path)
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise EbaySellAuthError(
            "No refresh token stored. Run the authorize flow again "
            "(see docs/EBAY_SELL_SETUP.md)."
        )
    data = _post_token(
        config,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": " ".join(DEFAULT_SCOPES),
        },
    )
    return _store_tokens(data, token_path, previous=tokens)


def get_valid_access_token(
    config: Optional[EbayConfig] = None,
    token_path: Path = TOKEN_FILE,
) -> str:
    """Return a live access token, refreshing when it is expired or near expiry."""
    tokens = load_tokens(token_path)
    access_token = tokens.get("access_token")
    expires_at = float(tokens.get("expires_at") or 0)
    if access_token and expires_at - _EXPIRY_SKEW_SECONDS > time.time():
        return access_token
    if not tokens.get("refresh_token"):
        raise EbaySellAuthError(
            "eBay sandbox is not authorized yet. Get the authorization URL, approve it "
            "in a browser, then paste the code (see docs/EBAY_SELL_SETUP.md)."
        )
    refreshed = refresh_access_token(config=config, token_path=token_path)
    token = refreshed.get("access_token")
    if not token:
        raise EbaySellAuthError("eBay returned no access token on refresh.")
    return token


def is_authorized(token_path: Path = TOKEN_FILE) -> bool:
    """True when a token file with a refresh token exists — no network call."""
    return bool(load_tokens(token_path).get("refresh_token"))


# ---------------------------------------------------------------------------
# Master listing -> eBay inventory item (pure)
# ---------------------------------------------------------------------------
def _clean_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def map_condition(raw: Any) -> str:
    """Map the app's free-text condition onto an eBay condition enum."""
    text = str(raw or "").strip().lower()
    if not text:
        return _DEFAULT_CONDITION
    if text.upper().replace(" ", "_") in set(_CONDITION_MAP.values()):
        return text.upper().replace(" ", "_")
    return _CONDITION_MAP.get(text, _DEFAULT_CONDITION)


def master_to_inventory_item(master: Dict[str, Any]) -> Dict[str, Any]:
    """Pure mapping: master listing record -> createOrReplaceInventoryItem body.

    Unit-tested; does no I/O and does not need credentials. Weight/dimension
    fields are optional on the master record and are omitted when absent rather
    than sent as zeros, which eBay rejects.
    """
    master = master or {}
    title = str(master.get("title") or "Untitled item").strip()[:80]
    description = str(master.get("description") or title).strip()
    quantity = int(_clean_number(master.get("quantity"), 1)) or 1

    package: Dict[str, Any] = {}
    weight = _clean_number(master.get("weight_lbs") or master.get("weight"))
    if weight > 0:
        package["weight"] = {"value": round(weight, 2), "unit": "POUND"}
    length = _clean_number(master.get("length_in") or master.get("length"))
    width = _clean_number(master.get("width_in") or master.get("width"))
    height = _clean_number(master.get("height_in") or master.get("height"))
    if length > 0 and width > 0 and height > 0:
        package["dimensions"] = {
            "length": round(length, 2),
            "width": round(width, 2),
            "height": round(height, 2),
            "unit": "INCH",
        }
    if package:
        package["packageType"] = str(master.get("package_type") or "PACKAGE_THICK_ENVELOPE")

    images = [str(u).strip() for u in (master.get("image_urls") or []) if str(u or "").strip()]
    if not images and master.get("image_url"):
        images = [str(master["image_url"]).strip()]

    product: Dict[str, Any] = {"title": title, "description": description}
    if images:
        product["imageUrls"] = images[:12]  # eBay caps gallery images at 12
    for record_key, ebay_key in (("brand", "brand"), ("mpn", "mpn"), ("upc", "upc")):
        value = str(master.get(record_key) or "").strip()
        if value:
            product[ebay_key] = [value] if ebay_key in {"upc"} else value

    # Some categories require item specifics (aspects) beyond brand/mpn/upc
    # (e.g. "Type") to publish. The app doesn't collect these yet, so pass
    # through an optional pre-built map rather than guessing per category.
    aspects = master.get("ebay_aspects")
    if isinstance(aspects, dict) and aspects:
        product["aspects"] = {
            str(name): [str(v) for v in (values if isinstance(values, list) else [values])]
            for name, values in aspects.items()
            if str(name).strip()
        }

    item: Dict[str, Any] = {
        "product": product,
        "condition": map_condition(master.get("condition")),
        "availability": {"shipToLocationAvailability": {"quantity": quantity}},
    }
    condition_note = str(master.get("condition_notes") or "").strip()
    if condition_note:
        item["conditionDescription"] = condition_note[:1000]
    if package:
        item["packageWeightAndSize"] = package
    return item


def master_to_offer(master: Dict[str, Any], config: EbayConfig) -> Dict[str, Any]:
    """Fixed-price offer body for the mapped inventory item."""
    master = master or {}
    price = _clean_number(master.get("price"))
    quantity = int(_clean_number(master.get("quantity"), 1)) or 1
    offer: Dict[str, Any] = {
        "sku": str(master.get("sku") or ""),
        "marketplaceId": config.marketplace_id,
        "format": "FIXED_PRICE",
        "availableQuantity": quantity,
        "pricingSummary": {"price": {"value": f"{price:.2f}", "currency": "USD"}},
        "listingPolicies": {
            "fulfillmentPolicyId": config.fulfillment_policy_id,
            "paymentPolicyId": config.payment_policy_id,
            "returnPolicyId": config.return_policy_id,
        },
    }
    # No merchantLocationKey here: config's stored key can go stale (renamed
    # or deleted in the sandbox account), which 404s createOffer with "Location
    # information not found". publish_master() resolves the seller's actual
    # location at publish time instead of trusting this config value.
    description = str(master.get("description") or "").strip()
    if description:
        offer["listingDescription"] = description
    category_id = str(master.get("ebay_category_id") or "").strip()
    if category_id:
        offer["categoryId"] = category_id
    return offer


# ---------------------------------------------------------------------------
# Inventory client (sandbox)
# ---------------------------------------------------------------------------
def _error_summary(resp: requests.Response) -> str:
    """Compact, secret-free rendering of an eBay error body."""
    try:
        body = resp.json()
    except ValueError:
        return (resp.text or "").strip()[:300] or "no response body"
    errors = body.get("errors") if isinstance(body, dict) else None
    if isinstance(errors, list) and errors:
        return "; ".join(
            f"{e.get('errorId', '?')}: {e.get('message', '')} {e.get('longMessage', '')}".strip()
            for e in errors[:3]
        )[:500]
    return json.dumps(body)[:300]


class EbaySellClient:
    """Thin sandbox Sell/Inventory client. One access token per instance."""

    def __init__(
        self,
        config: Optional[EbayConfig] = None,
        access_token: Optional[str] = None,
        token_path: Path = TOKEN_FILE,
        session: Optional[requests.Session] = None,
    ):
        self.config = config or load_config()
        self.token_path = token_path
        self._access_token = access_token
        self.session = session or requests

    @property
    def access_token(self) -> str:
        if not self._access_token:
            self._access_token = get_valid_access_token(config=self.config, token_path=self.token_path)
        return self._access_token

    def _headers(self, content_language: bool = False) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": self.config.marketplace_id,
        }
        if content_language:
            # Required by createOrReplaceInventoryItem / createOffer.
            headers["Content-Language"] = "en-US"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        content_language: bool = False,
        treat_404_as_empty: bool = False,
    ) -> Dict[str, Any]:
        url = f"{INVENTORY_BASE}{path}"
        # eBay's sandbox edge 411s a POST with no body at all; always send a
        # real JSON body (even just {}) so Content-Length is set correctly.
        body = {} if json_body is None and method in ("POST", "PUT") else json_body
        try:
            resp = self.session.request(
                method,
                url,
                headers=self._headers(content_language=content_language),
                json=body,
                timeout=_TIMEOUT,
            )
        except requests.exceptions.RequestException as exc:
            raise EbaySellError(f"eBay sandbox request failed ({method} {path}): {exc}") from exc
        if resp.status_code >= 400:
            if treat_404_as_empty and resp.status_code == 404:
                return {}
            raise EbaySellError(
                f"eBay sandbox {method} {path} failed (HTTP {resp.status_code}): {_error_summary(resp)}"
            )
        if resp.status_code == 204 or not (resp.content or b"").strip():
            return {}
        try:
            return resp.json()
        except ValueError:
            return {}

    # -- inventory item ----------------------------------------------------
    def create_or_replace_inventory_item(self, sku: str, item_dict: Dict[str, Any]) -> Dict[str, Any]:
        """PUT the inventory item. eBay returns 204 No Content on success."""
        if not sku:
            raise EbaySellError("Cannot create an inventory item without a SKU.")
        return self._request(
            "PUT",
            f"/inventory_item/{urllib.parse.quote(str(sku), safe='')}",
            json_body=item_dict,
            content_language=True,
        )

    def get_inventory_item(self, sku: str) -> Dict[str, Any]:
        return self._request("GET", f"/inventory_item/{urllib.parse.quote(str(sku), safe='')}")

    # -- location ------------------------------------------------------------
    def find_merchant_location_key(self) -> Optional[str]:
        """An ENABLED merchant location key that actually exists for this seller.

        publishOffer resolves <Item.Country> from the offer's merchantLocationKey.
        A missing/invalid key fails createOffer ("Location information not
        found"); no key at all fails publishOffer ("No <Item.Country> exists").
        Config's stored key can go stale, so look up what's real instead.
        """
        data = self._request("GET", "/location")
        for location in data.get("locations") or []:
            if location.get("merchantLocationStatus") == "ENABLED" and location.get("merchantLocationKey"):
                return str(location["merchantLocationKey"])
        return None

    # -- offer -------------------------------------------------------------
    def create_offer(self, sku: str, offer_dict: Dict[str, Any]) -> str:
        """Create a fixed-price offer and return its offerId."""
        body = dict(offer_dict or {})
        body["sku"] = str(sku)
        body.setdefault("format", "FIXED_PRICE")
        data = self._request("POST", "/offer", json_body=body, content_language=True)
        offer_id = data.get("offerId")
        if not offer_id:
            raise EbaySellError("eBay created the offer but returned no offerId.")
        return str(offer_id)

    def find_offer_id(self, sku: str) -> Optional[str]:
        """Existing offerId for a SKU, if any — createOffer 409s on duplicates.

        eBay returns HTTP 404 ("Offer is not available") when the SKU has no
        offer yet — that's a normal "no existing offer" result, not a failure.
        """
        data = self._request(
            "GET",
            f"/offer?sku={urllib.parse.quote(str(sku), safe='')}&marketplace_id={self.config.marketplace_id}",
            treat_404_as_empty=True,
        )
        offers = data.get("offers") or []
        for offer in offers:
            if offer.get("offerId"):
                return str(offer["offerId"])
        return None

    def update_offer(self, offer_id: str, offer_dict: Dict[str, Any]) -> Dict[str, Any]:
        return self._request(
            "PUT",
            f"/offer/{urllib.parse.quote(str(offer_id), safe='')}",
            json_body=offer_dict,
            content_language=True,
        )

    def publish_offer(self, offer_id: str) -> str:
        """Publish an offer and return the eBay listingId."""
        data = self._request("POST", f"/offer/{urllib.parse.quote(str(offer_id), safe='')}/publish")
        listing_id = data.get("listingId")
        if not listing_id:
            raise EbaySellError("eBay published the offer but returned no listingId.")
        return str(listing_id)

    def get_offer_status(self, offer_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/offer/{urllib.parse.quote(str(offer_id), safe='')}")

    def withdraw_offer(self, offer_id: str) -> Dict[str, Any]:
        """End the sandbox listing but keep the offer — used for cleanup."""
        return self._request("POST", f"/offer/{urllib.parse.quote(str(offer_id), safe='')}/withdraw")


# ---------------------------------------------------------------------------
# End-to-end publish
# ---------------------------------------------------------------------------
def publish_master(
    master: Dict[str, Any],
    config: Optional[EbayConfig] = None,
    client: Optional[EbaySellClient] = None,
    token_path: Path = TOKEN_FILE,
) -> Dict[str, str]:
    """Auth -> inventory item -> offer -> publish, for one master listing.

    Returns {"sku", "offer_id", "listing_id"}. Raises EbaySellError (or a
    subclass) on any failure; callers leave listing state unchanged on raise.
    """
    config = config or (client.config if client else load_config())
    config.require_auth_fields()
    config.require_offer_fields()

    sku = str((master or {}).get("sku") or "").strip()
    if not sku:
        raise EbaySellError("Master listing has no SKU; cannot publish to eBay.")

    client = client or EbaySellClient(config=config, token_path=token_path)
    client.create_or_replace_inventory_item(sku, master_to_inventory_item(master))

    offer_body = master_to_offer(master, config)
    location_key = client.find_merchant_location_key()
    if location_key:
        offer_body["merchantLocationKey"] = location_key
    existing = client.find_offer_id(sku)
    if existing:
        # Re-publishing the same SKU: update in place instead of 409-ing.
        client.update_offer(existing, offer_body)
        offer_id = existing
    else:
        offer_id = client.create_offer(sku, offer_body)

    listing_id = client.publish_offer(offer_id)
    return {"sku": sku, "offer_id": offer_id, "listing_id": listing_id}
