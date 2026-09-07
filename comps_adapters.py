"""
comps_adapters.py — pluggable sources of Comp objects for comps.py.

The adapter architecture the roadmap calls for: every source (manual
entry, a pasted CSV/export, a live marketplace API) implements the same
tiny interface and hands back a list of comps.Comp — comps.py doesn't
care where they came from. Adding a new source later (a different
marketplace API, a spreadsheet import, eBay's Marketplace Insights API
once/if that partner access is approved) means writing one more small
adapter here, not touching the valuation math.

ManualCompsAdapter and CsvCompsAdapter are pure (no network) and always
available. EbayBrowseAdapter is real, working code against eBay's actual
Browse API — but it only returns ACTIVE listings (asking prices), because
eBay gates sold-listing data (the old Finding API's findCompletedItems is
retired; the Marketplace Insights API for sold data requires approved
partner access this app doesn't have). This module does not fake sold
data to fill that gap — see EbayBrowseAdapter's docstring.
"""

import base64
import io
import time
from typing import List, Protocol

import pandas as pd
import requests
import streamlit as st

from comps import ACTIVE, Comp

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


_token_cache = {"access_token": None, "expires_at": 0}


def _ebay_client_credentials() -> tuple:
    client_id = st.secrets.get("EBAY_CLIENT_ID")
    client_secret = st.secrets.get("EBAY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EbayAuthError("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not set in Streamlit secrets.")
    return client_id, client_secret


def _get_ebay_access_token() -> str:
    """OAuth2 client_credentials grant against eBay's identity API — this
    scope (https://api.ebay.com/oauth/api_scope) only unlocks public
    browse endpoints, not anything account-specific, so there's no user
    consent flow needed. Cached in-process until shortly before it
    expires (tokens are valid ~2 hours) so every comps lookup doesn't
    re-authenticate."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

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
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 7200))
    return _token_cache["access_token"]


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


def is_ebay_configured() -> bool:
    try:
        _ebay_client_credentials()
        return True
    except EbayAuthError:
        return False
