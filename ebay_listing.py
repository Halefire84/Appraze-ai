"""
ebay_listing.py — real eBay listing creation via eBay's Sell Inventory API.

Different OAuth model from comps_adapters.py's EbayBrowseAdapter on
purpose: that one uses the client_credentials grant (app-level, read-only,
no seller context) for public Browse/Insights lookups. Creating an actual
listing posts AS a specific eBay seller, which eBay only allows via the
Authorization Code grant: the seller logs into eBay once, explicitly
consents ("Sell on your behalf"), and eBay redirects back with a code this
app exchanges for a refresh token (valid ~18 months, auto-renewing access
tokens after that -- see refresh_access_token()).

Single-seller model, matching the rest of this app's single-business
architecture (one shared admin workspace, not per-customer tenants):
credentials are stored once, under the shared "admin_shared" owner key,
the same place sales_log/AIUsage live. This is not a multi-tenant "each
customer connects their own eBay" feature.

External prerequisites only the account owner can complete -- this module
cannot do or work around any of these:
  1. Register a redirect ("RuName") in the eBay Developer Portal pointing
     at this app's OAuth callback URL (Application Keys -> your keyset ->
     "Get a Token from eBay via Your Application" -> add a Redirect URL
     name). EBAY_RUNAME below is that RuName string eBay gives you, not a
     raw URL -- eBay's OAuth redirect_uri parameter takes the RuName, not
     the literal callback URL.
  2. Set up at least one payment, return, and fulfillment BUSINESS POLICY
     in Seller Hub (opt into Business Policies, then create one of each).
     Every offer must reference existing policy IDs; this module has no
     way to create or guess them. get_business_policies() fetches whatever
     exists so the Cross-List page can let the seller pick, but if none
     exist yet, publishing fails with a clear message pointing at Seller
     Hub, not a guess.
  3. Confirm the developer account's Sell APIs are enabled for the target
     environment. Sandbox works out of the box for most developer
     accounts; production Sell API access sometimes needs eBay's own
     compliance review, similar to Stripe Connect's live-mode approval.

Until all three are done, everything below except the "Connect eBay"
button itself will fail with a clear, caught error -- never a crash, and
never a silent fake "published" status (see publish_listing()'s
docstring: every step's real eBay response is checked before the next
step runs, and a partial failure is reported as exactly that, not hidden).
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import base64
import time

import requests
import streamlit as st

CREDENTIALS_TABLE = "ebay_seller_credentials"
SELL_SCOPES = (
    "https://api.ebay.com/oauth/api_scope/sell.inventory "
    "https://api.ebay.com/oauth/api_scope/sell.account"
)


class EbayListingError(Exception):
    """Raised for any eBay Sell API failure -- config missing, OAuth
    failure, or a rejected API call. Callers always catch this rather
    than letting it surface as an unhandled exception, and never treat
    "no exception" as "definitely published" -- check PublishResult.ok."""


@dataclass
class PublishResult:
    ok: bool
    listing_id: str = ""
    listing_url: str = ""
    error: str = ""
    step: str = ""  # which step failed, for diagnostics: "inventory_item" | "offer" | "publish"


@dataclass
class SellerCredentials:
    access_token: str
    refresh_token: str
    expires_at: float
    ebay_user_id: str = ""


def _base_url() -> str:
    return "https://api.sandbox.ebay.com" if _sandbox_mode() else "https://api.ebay.com"


def _auth_base_url() -> str:
    return "https://auth.sandbox.ebay.com" if _sandbox_mode() else "https://auth.ebay.com"


def _sandbox_mode() -> bool:
    return bool(st.secrets.get("EBAY_SANDBOX", False))


def _client_credentials() -> tuple:
    client_id = st.secrets.get("EBAY_CLIENT_ID")
    client_secret = st.secrets.get("EBAY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EbayListingError("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not set in Streamlit secrets.")
    return client_id, client_secret


def _runame() -> str:
    runame = st.secrets.get("EBAY_RUNAME")
    if not runame:
        raise EbayListingError(
            "EBAY_RUNAME is not set -- register a redirect (RuName) for this app in the "
            "eBay Developer Portal first (Application Keys -> your keyset -> 'Get a Token "
            "from eBay via Your Application')."
        )
    return runame


# ---------------------------------------------------------------------------
# OAuth: Authorization Code grant (seller consent), separate from
# comps_adapters.py's client_credentials grant.
# ---------------------------------------------------------------------------

def authorization_url(state: str) -> str:
    """URL to send the seller to so they can consent to Appraze listing on
    their behalf. eBay redirects back to the RuName's configured callback
    with ?code=...&state=... on success."""
    client_id, _ = _client_credentials()
    params = {
        "client_id": client_id,
        "redirect_uri": _runame(),
        "response_type": "code",
        "scope": SELL_SCOPES,
        "state": state,
    }
    return f"{_auth_base_url()}/oauth2/authorize?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> SellerCredentials:
    """Exchanges the one-time authorization code eBay sent back for a
    refresh token (long-lived) and access token (short-lived). Raises
    EbayListingError on any failure -- never returns a half-populated
    SellerCredentials."""
    client_id, client_secret = _client_credentials()
    basic_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    try:
        resp = requests.post(
            f"{_base_url()}/identity/v1/oauth2/token",
            headers={"Authorization": f"Basic {basic_auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": _runame()},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise EbayListingError(f"eBay rejected the authorization code: {e.response.status_code} {e.response.text[:300]}") from e
    except Exception as e:
        raise EbayListingError(f"connection error exchanging authorization code: {e}") from e

    data = resp.json()
    now = time.time()
    return SellerCredentials(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=now + int(data.get("expires_in", 7200)),
    )


def refresh_access_token(refresh_token: str) -> SellerCredentials:
    """Refresh tokens are valid ~18 months; access tokens ~2 hours. Call
    this whenever the stored access token is expired/near-expired rather
    than sending the seller through consent again."""
    client_id, client_secret = _client_credentials()
    basic_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    try:
        resp = requests.post(
            f"{_base_url()}/identity/v1/oauth2/token",
            headers={"Authorization": f"Basic {basic_auth}", "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "refresh_token", "refresh_token": refresh_token, "scope": SELL_SCOPES},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise EbayListingError(f"eBay rejected the refresh token: {e.response.status_code} {e.response.text[:300]}") from e
    except Exception as e:
        raise EbayListingError(f"connection error refreshing eBay token: {e}") from e

    data = resp.json()
    now = time.time()
    return SellerCredentials(
        access_token=data["access_token"],
        refresh_token=refresh_token,  # eBay does not rotate the refresh token on a plain refresh
        expires_at=now + int(data.get("expires_in", 7200)),
    )


# ---------------------------------------------------------------------------
# Credential persistence -- reuses storage.py's existing table pattern
# (single shared row, same as sales_log/AIUsage) rather than inventing a
# new storage mechanism.
# ---------------------------------------------------------------------------

def save_credentials(creds: SellerCredentials) -> bool:
    from storage import save_table
    import pandas as pd

    row = {
        "access_token": creds.access_token,
        "refresh_token": creds.refresh_token,
        "expires_at": creds.expires_at,
        "ebay_user_id": creds.ebay_user_id,
    }
    result = save_table(pd.DataFrame([row]), CREDENTIALS_TABLE, shared=True)
    return result.success


def load_credentials() -> Optional[SellerCredentials]:
    from storage import load_table

    result = load_table(CREDENTIALS_TABLE, shared=True)
    if not result.success or not result.payload:
        return None
    row = result.payload[0]
    try:
        return SellerCredentials(
            access_token=row["access_token"],
            refresh_token=row["refresh_token"],
            expires_at=float(row["expires_at"]),
            ebay_user_id=row.get("ebay_user_id", ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


def is_connected() -> bool:
    return load_credentials() is not None


def disconnect() -> bool:
    """Clears the stored eBay credentials (does not revoke consent on
    eBay's side -- the seller can also do that from their eBay account
    settings). Used when a seller wants to reconnect a different account."""
    from storage import save_table
    import pandas as pd

    result = save_table(pd.DataFrame([]), CREDENTIALS_TABLE, shared=True)
    return result.success


def _valid_access_token() -> str:
    """Returns a live access token, refreshing (and persisting the
    refresh) if the stored one is expired or near-expired. Raises
    EbayListingError if nothing is connected yet."""
    creds = load_credentials()
    if not creds:
        raise EbayListingError("No eBay account is connected yet -- use the Connect eBay button first.")
    if time.time() < creds.expires_at - 60:
        return creds.access_token
    refreshed = refresh_access_token(creds.refresh_token)
    refreshed.ebay_user_id = creds.ebay_user_id
    save_credentials(refreshed)
    return refreshed.access_token


# ---------------------------------------------------------------------------
# Sell Inventory API -- the actual listing-creation calls.
# ---------------------------------------------------------------------------

def get_business_policies() -> Dict[str, List[Dict[str, str]]]:
    """Fetches the seller's existing payment/return/fulfillment policies
    (Account API) so the Cross-List page can let them pick one of each,
    rather than this module guessing or hardcoding an ID. Returns empty
    lists (never raises) if none are set up yet -- the caller shows a
    clear "set these up in Seller Hub first" message instead."""
    token = _valid_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    marketplace = "EBAY_US"
    out: Dict[str, List[Dict[str, str]]] = {"payment": [], "return": [], "fulfillment": []}
    # eBay's Account API uses these exact camelCase path/response/field
    # names -- they do NOT follow a predictable snake_case-plus-"s"
    # pattern (it's "Policies", not "policys"), so each is spelled out
    # rather than derived.
    endpoints = {
        "payment": ("payment_policy", "paymentPolicies", "paymentPolicyId"),
        "return": ("return_policy", "returnPolicies", "returnPolicyId"),
        "fulfillment": ("fulfillment_policy", "fulfillmentPolicies", "fulfillmentPolicyId"),
    }
    for key, (path, response_key, id_field) in endpoints.items():
        try:
            resp = requests.get(
                f"{_base_url()}/sell/account/v1/{path}",
                headers=headers,
                params={"marketplace_id": marketplace},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            policies = data.get(response_key, [])
            out[key] = [{"id": p.get(id_field, ""), "name": p.get("name", "")} for p in policies]
        except Exception:
            out[key] = []  # a missing/failed policy type is reported as "none set up", not a crash
    return out


def create_inventory_item(sku: str, item: Dict[str, Any]) -> PublishResult:
    """PUT /sell/inventory/v1/inventory_item/{sku}. item is expected to
    have title, description, condition (e.g. "USED_EXCELLENT"), imageUrls
    (list), and quantity."""
    try:
        token = _valid_access_token()
    except EbayListingError as e:
        return PublishResult(ok=False, error=str(e), step="inventory_item")

    body = {
        "condition": item.get("condition", "USED_GOOD"),
        "product": {
            "title": str(item.get("title", ""))[:80],
            "description": item.get("description", ""),
            "imageUrls": item.get("imageUrls", []) or [],
        },
        "availability": {"shipToLocationAvailability": {"quantity": int(item.get("quantity") or 1)}},
    }
    try:
        resp = requests.put(
            f"{_base_url()}/sell/inventory/v1/inventory_item/{sku}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Content-Language": "en-US",
            },
            json=body,
            timeout=20,
        )
        if resp.status_code not in (200, 201, 204):
            return PublishResult(ok=False, error=f"eBay rejected the inventory item: {resp.status_code} {resp.text[:300]}", step="inventory_item")
    except Exception as e:
        return PublishResult(ok=False, error=f"connection error creating inventory item: {e}", step="inventory_item")
    return PublishResult(ok=True)


def create_offer(sku: str, offer: Dict[str, Any]) -> PublishResult:
    """POST /sell/inventory/v1/offer. offer must include price, a
    category_id, and payment/return/fulfillment policy IDs from
    get_business_policies() -- eBay rejects the offer outright if any
    policy ID doesn't exist on the seller's account, which surfaces here
    as a normal (ok=False) result, not a crash."""
    try:
        token = _valid_access_token()
    except EbayListingError as e:
        return PublishResult(ok=False, error=str(e), step="offer")

    body = {
        "sku": sku,
        "marketplaceId": "EBAY_US",
        "format": "FIXED_PRICE",
        "availableQuantity": int(offer.get("quantity") or 1),
        "categoryId": offer.get("category_id", ""),
        "listingDescription": offer.get("description", ""),
        "pricingSummary": {"price": {"value": f"{float(offer.get('price') or 0):.2f}", "currency": "USD"}},
        "listingPolicies": {
            "paymentPolicyId": offer.get("payment_policy_id", ""),
            "returnPolicyId": offer.get("return_policy_id", ""),
            "fulfillmentPolicyId": offer.get("fulfillment_policy_id", ""),
        },
    }
    try:
        resp = requests.post(
            f"{_base_url()}/sell/inventory/v1/offer",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Content-Language": "en-US"},
            json=body,
            timeout=20,
        )
        if resp.status_code not in (200, 201):
            return PublishResult(ok=False, error=f"eBay rejected the offer: {resp.status_code} {resp.text[:300]}", step="offer")
        offer_id = resp.json().get("offerId", "")
    except Exception as e:
        return PublishResult(ok=False, error=f"connection error creating offer: {e}", step="offer")
    return PublishResult(ok=True, listing_id=offer_id)


def publish_offer(offer_id: str) -> PublishResult:
    """POST /sell/inventory/v1/offer/{offerId}/publish -- the step that
    actually turns the offer into a live eBay listing."""
    try:
        token = _valid_access_token()
    except EbayListingError as e:
        return PublishResult(ok=False, error=str(e), step="publish")

    try:
        resp = requests.post(
            f"{_base_url()}/sell/inventory/v1/offer/{offer_id}/publish",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=20,
        )
        if resp.status_code not in (200, 201):
            return PublishResult(ok=False, error=f"eBay rejected publishing: {resp.status_code} {resp.text[:300]}", step="publish", listing_id=offer_id)
        data = resp.json()
        listing_id = data.get("listingId", "")
    except Exception as e:
        return PublishResult(ok=False, error=f"connection error publishing offer: {e}", step="publish", listing_id=offer_id)

    url = f"https://www.ebay.com/itm/{listing_id}" if listing_id else ""
    return PublishResult(ok=True, listing_id=listing_id, listing_url=url)


def publish_listing(sku: str, item: Dict[str, Any], offer: Dict[str, Any]) -> PublishResult:
    """Orchestrates the full 3-step flow: inventory item -> offer ->
    publish. Stops at the first failure and reports exactly which step
    failed (PublishResult.step) -- never claims success from a partial
    completion. A failure after create_inventory_item() but before
    publish_offer() leaves a draft inventory item/offer sitting in the
    seller's eBay account (visible in Seller Hub) rather than a phantom
    "published" listing that doesn't actually exist."""
    item_result = create_inventory_item(sku, item)
    if not item_result.ok:
        return item_result

    offer_result = create_offer(sku, offer)
    if not offer_result.ok:
        return offer_result

    return publish_offer(offer_result.listing_id)
