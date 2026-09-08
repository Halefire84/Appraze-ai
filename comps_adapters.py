"""
comps_adapters.py — pluggable sources of Comp objects for comps.py.

The adapter architecture the roadmap calls for: every source (manual
entry, a pasted CSV/export, a live marketplace API) implements the same
tiny interface and hands back a list of comps.Comp — comps.py doesn't
care where they came from. Adding a new source later (a different
marketplace API, a spreadsheet import) means writing one more small
adapter here, not touching the valuation math.

ManualCompsAdapter and CsvCompsAdapter are pure (no network) and always
available. EbayBrowseAdapter is real, working code against eBay's actual
Browse API, returning ACTIVE listings (asking prices) — available to any
eBay developer account immediately, no approval needed.

EbayMarketplaceInsightsAdapter is real code against eBay's actual sold-
item API, but eBay gates it behind a Limited Release approval this app
does NOT have by default (see its docstring for what that means and how
to request it) — until/unless that's approved, calling it raises
EbayInsightsNotApprovedError, and callers should fall back to
EbayBrowseAdapter instead. This module does not fake sold data to paper
over a missing approval.
"""

import base64
import io
import time
from typing import List, Protocol

import pandas as pd
import requests
import streamlit as st

from comps import ACTIVE, SOLD, Comp

CSV_COLUMNS = ["price", "source", "listing_type", "condition", "shipping", "listing_date", "title", "url"]


class CompsAdapter(Protocol):
    """Every adapter implements this one method. comps.summarize_comps()
    and comps.evaluate_with_comps() take a plain list of Comp, so callers
    can mix comps from multiple adapters freely before scoring them."""

    def fetch_comps(self, query: str, limit: int = 20) -> List[Comp]:
        ...


class ManualCompsAdapter:
    """Wraps comps a person typed in by hand (e.g. into the Market Comps
    tab's data editor after checking eBay/HiBid/CTBids sold listings
    themselves). This is the most reliable source available without a
    paid marketplace data API: a human who actually looked at real sold
    listings, transcribed as data instead of a vague AI guess."""

    def __init__(self, comps: List[Comp]):
        self._comps = comps

    def fetch_comps(self, query: str = "", limit: int = 20) -> List[Comp]:
        return list(self._comps[:limit])


class CsvCompsAdapter:
    """Parses a CSV (or a DataFrame already read from one) with columns
    matching CSV_COLUMNS — e.g. an export from a marketplace analytics
    tool, or a spreadsheet someone's been tracking sold prices in by hand.
    Only `price` is required; everything else defaults sensibly."""

    def __init__(self, csv_bytes: bytes = None, dataframe: pd.DataFrame = None):
        if dataframe is not None:
            self._df = dataframe
        elif csv_bytes is not None:
            self._df = pd.read_csv(io.BytesIO(csv_bytes))
        else:
            raise ValueError("CsvCompsAdapter needs either csv_bytes or dataframe")

    def fetch_comps(self, query: str = "", limit: int = 20) -> List[Comp]:
        comps = []
        for _, row in self._df.head(limit).iterrows():
            if "price" not in row or pd.isna(row.get("price")):
                continue
            comps.append(Comp(
                price=float(row["price"]),
                source=str(row.get("source", "CSV import")) if not pd.isna(row.get("source", "")) else "CSV import",
                listing_type=str(row.get("listing_type", "sold")).lower() if not pd.isna(row.get("listing_type", "")) else "sold",
                condition=str(row.get("condition", "")) if not pd.isna(row.get("condition", "")) else "",
                shipping=float(row.get("shipping", 0) or 0) if not pd.isna(row.get("shipping", 0)) else 0.0,
                listing_date=str(row.get("listing_date", "")) if not pd.isna(row.get("listing_date", "")) else None,
                title=str(row.get("title", "")) if not pd.isna(row.get("title", "")) else "",
                url=str(row.get("url", "")) if not pd.isna(row.get("url", "")) else "",
            ))
        return comps


class EbayAuthError(Exception):
    """Raised when EBAY_CLIENT_ID/EBAY_CLIENT_SECRET aren't configured."""
    pass


_BROWSE_SCOPE = "https://api.ebay.com/oauth/api_scope"
# A separate scope, only ever granted on apps eBay has approved for the
# Limited Release Marketplace Insights API - requesting it doesn't affect
# the Browse scope above, since each is cached and requested independently
# (see _token_cache, keyed by scope string).
_INSIGHTS_SCOPE = "https://api.ebay.com/oauth/api_scope/buy.marketplace.insights"

_token_cache = {}  # scope string -> {"access_token": ..., "expires_at": ...}


def _ebay_client_credentials() -> tuple:
    client_id = st.secrets.get("EBAY_CLIENT_ID")
    client_secret = st.secrets.get("EBAY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EbayAuthError("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not set in Streamlit secrets.")
    return client_id, client_secret


def _get_ebay_access_token(scope: str = _BROWSE_SCOPE) -> str:
    """OAuth2 client_credentials grant against eBay's identity API. The
    default scope only unlocks public Browse endpoints, not anything
    account-specific, so there's no user consent flow needed. Cached
    in-process per scope until shortly before it expires (tokens are
    valid ~2 hours) so every comps lookup doesn't re-authenticate."""
    now = time.time()
    cached = _token_cache.get(scope)
    if cached and now < cached["expires_at"] - 60:
        return cached["access_token"]

    client_id, client_secret = _ebay_client_credentials()
    basic_auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "client_credentials",
            "scope": scope,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache[scope] = {
        "access_token": data["access_token"],
        "expires_at": now + int(data.get("expires_in", 7200)),
    }
    return data["access_token"]


class EbayBrowseAdapter:
    """
    Real eBay Browse API integration — ACTIVE listings only (current
    asking prices), not sold/completed sales. eBay retired the old
    Finding API's findCompletedItems, and sold-item data now lives behind
    the Marketplace Insights API, which requires eBay's approved partner
    access this app doesn't have. Rather than fake sold data to paper
    over that gap, every comp this adapter returns is tagged
    listing_type="active" so comps.summarize_comps() correctly rates its
    confidence lower than real sold evidence (see comps.py's
    _rate_confidence) — an honest "here's what people are asking right
    now" signal instead of a fabricated "here's what it sold for."

    If EBAY_CLIENT_ID/EBAY_CLIENT_SECRET aren't configured, fetch_comps
    raises EbayAuthError — callers should catch that and show a
    "not configured" message, same pattern as every other optional
    integration in this app (Stripe, Anthropic, Gmail).
    """

    _SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    def __init__(self, marketplace_id: str = "EBAY_US"):
        self.marketplace_id = marketplace_id

    def fetch_comps(self, query: str, limit: int = 20) -> List[Comp]:
        if not query.strip():
            return []
        token = _get_ebay_access_token()
        resp = requests.get(
            self._SEARCH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            },
            params={"q": query, "limit": min(limit, 50)},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()

        comps = []
        for item in data.get("itemSummaries", []) or []:
            price_info = item.get("price") or {}
            shipping_options = item.get("shippingOptions") or []
            shipping_cost = 0.0
            if shipping_options:
                shipping_cost = float((shipping_options[0].get("shippingCost") or {}).get("value", 0) or 0)
            try:
                price = float(price_info.get("value", 0) or 0)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            comps.append(Comp(
                price=price,
                source="eBay",
                listing_type=ACTIVE,
                condition=item.get("condition", ""),
                shipping=shipping_cost,
                listing_date=None,
                title=item.get("title", ""),
                url=item.get("itemWebUrl", ""),
            ))
        return comps


class EbayInsightsNotApprovedError(Exception):
    """Raised when eBay's API rejects a Marketplace Insights call because
    this app isn't (yet) approved for it - error code 1100 "Access denied"
    is eBay's documented signal for exactly this, distinct from a bad
    request or bad credentials. Callers should catch this specifically and
    fall back to EbayBrowseAdapter, not treat it as a generic failure."""
    pass


class EbayMarketplaceInsightsAdapter:
    """
    Real eBay Marketplace Insights API integration — actual SOLD prices
    (last 90 days), not asking prices. This is the API that ANSWERS the
    gap EbayBrowseAdapter's docstring calls out.

    THE CATCH, and it's a real one: this is a "Limited Release" API. An
    ordinary eBay developer account (the same EBAY_CLIENT_ID/SECRET used
    for Browse above) does NOT get access to this just by existing - eBay
    has to separately approve your app for it, and multiple developers in
    eBay's own community forums report that in practice this approval now
    goes almost exclusively to large/enterprise partners, not solo or
    small-business developers - see is_marketplace_insights_configured()
    to check approval status without guessing, and this module's
    docstring / DEPLOY.md for exactly how to apply.

    Field names below (itemSales, lastSoldPrice, lastSoldDate, condition,
    itemWebUrl, title) come from eBay's public docs and Marketplace
    Insights community reports - I could not fetch eBay's live schema
    page directly (developer.ebay.com blocks automated fetches), so if
    eBay ever changes this shape, parsing here may need updating. Test
    against eBay's Sandbox environment first if you get approved, before
    trusting this against real budget decisions.

    Never fabricates sold data - if the API call fails for any reason
    other than a confirmed "not approved yet" response, it raises rather
    than silently returning nothing or falling back on its own; the
    caller decides what a failure should look like to the user.
    """

    _SEARCH_URL = "https://api.ebay.com/buy/marketplace_insights/v1_beta/item_sales/search"

    def __init__(self, marketplace_id: str = "EBAY_US"):
        self.marketplace_id = marketplace_id

    def fetch_comps(self, query: str, limit: int = 20) -> List[Comp]:
        if not query.strip():
            return []
        token = _get_ebay_access_token(scope=_INSIGHTS_SCOPE)
        resp = requests.get(
            self._SEARCH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            },
            params={"q": query, "limit": min(limit, 50)},
            timeout=20,
        )
        if resp.status_code == 403:
            errors = (resp.json().get("errors") or []) if resp.headers.get("content-type", "").startswith("application/json") else []
            if any(e.get("errorId") == 1100 for e in errors):
                raise EbayInsightsNotApprovedError(
                    "eBay returned error 1100 (Access denied) - this app isn't approved for the "
                    "Marketplace Insights API yet. Falling back to active-listing comps instead."
                )
        resp.raise_for_status()
        data = resp.json()

        comps = []
        for item in data.get("itemSales", []) or []:
            sold_price_info = item.get("lastSoldPrice") or {}
            try:
                price = float(sold_price_info.get("value", 0) or 0)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue
            comps.append(Comp(
                price=price,
                source="eBay (sold)",
                listing_type=SOLD,
                condition=item.get("condition", ""),
                shipping=0.0,  # not exposed on this endpoint - price above is item price only
                listing_date=item.get("lastSoldDate"),
                title=item.get("title", ""),
                url=item.get("itemWebUrl", ""),
            ))
        return comps


_insights_approval_cache = {"approved": None}


def is_marketplace_insights_configured() -> bool:
    """True only once EBAY_CLIENT_ID/SECRET are set AND eBay has actually
    approved this app for Marketplace Insights. There's no "check my
    approval status" endpoint eBay exposes, and getting a token for the
    insights scope can succeed even on an unapproved app - the rejection
    (error 1100) only shows up when the search endpoint itself is called.
    So this makes one real, tiny search call and checks whether eBay
    accepts or rejects it. Cached for the life of this process after the
    first check (approval status won't change mid-session), so this
    doesn't cost a network round-trip on every Streamlit rerun."""
    if _insights_approval_cache["approved"] is not None:
        return _insights_approval_cache["approved"]
    try:
        EbayMarketplaceInsightsAdapter().fetch_comps("test", limit=1)
        approved = True
    except EbayInsightsNotApprovedError:
        approved = False
    except EbayAuthError:
        approved = False
    except requests.exceptions.RequestException:
        # A network hiccup isn't a real "not approved" answer - don't
        # cache a false negative, just try again on the next call.
        return False
    _insights_approval_cache["approved"] = approved
    return approved


def is_ebay_configured() -> bool:
    try:
        _ebay_client_credentials()
        return True
    except EbayAuthError:
        return False
