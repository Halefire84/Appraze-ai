"""eBay adapter — official eBay Sell API scaffolding.

Intended (NOT YET WIRED) flow:
  1. OAuth Authorization-Code grant -> user access token
     (scopes: sell.inventory, sell.account — see crosslist.config).
  2. PUT /sell/inventory/v1/inventory_item/{sku}   (createOrReplaceInventoryItem)
  3. POST /sell/inventory/v1/offer                  (createOffer)
  4. POST /sell/inventory/v1/offer/{offerId}/publish (publishOffer)

No credentials exist anywhere in this repo; every credential-dependent
step is a clearly-marked TODO. ``format_listing()`` is pure and builds
the inventory-item + offer structure; ``publish()`` / ``delist()``
raise until wired.
"""

from __future__ import annotations

from typing import Any, Dict

from crosslist.base import FormattedListing, MarketplaceAdapter, NotConfiguredError
from crosslist.config import (
    EBAY_API_SCOPES,
    EBAY_PRODUCTION_BASE_URL,
    EBAY_SANDBOX_BASE_URL,
)
from crosslist.models import Condition, MasterListing

EBAY_US_MARKETPLACE_ID = "EBAY_US"
FORMAT_TYPE_FIXED_PRICE = "FIXED_PRICE"
EBAY_TITLE_LIMIT = 80

# Appraze Condition -> eBay condition ID. Condition IDs are
# category-dependent on eBay; TODO: refine per category taxonomy.
CONDITION_MAP = {
    Condition.NEW: "1000",  # New
    Condition.LIKE_NEW: "3010",  # Pre-owned — Excellent
    Condition.GOOD: "3030",  # Pre-owned — Good
    Condition.FAIR: "3040",  # Pre-owned — Fair
    Condition.FOR_PARTS: "4000",  # For parts or not working
}

# TODO: replace with real policy IDs from the seller's eBay account
# (Sell API: getFulfillmentPolicies / getPaymentPolicies / getReturnPolicies).
TODO_FULFILLMENT_POLICY_ID = "TODO_FULFILLMENT_POLICY_ID"
TODO_PAYMENT_POLICY_ID = "TODO_PAYMENT_POLICY_ID"
TODO_RETURN_POLICY_ID = "TODO_RETURN_POLICY_ID"


class EbayAdapter(MarketplaceAdapter):
    """Formats listings for the official eBay Sell Inventory API."""

    marketplace_id = "ebay"

    def __init__(self, *, sandbox: bool = True) -> None:
        # TODO: wire OAuth — client_id / client_secret / redirect URI live in
        # server-side secrets (never in the repo), token refresh + storage.
        self.base_url = EBAY_SANDBOX_BASE_URL if sandbox else EBAY_PRODUCTION_BASE_URL
        self.scopes = list(EBAY_API_SCOPES)
        self.access_token: str | None = None  # TODO: obtain via OAuth flow

    # -- pure formatting -------------------------------------------------
    def format_listing(self, master: MasterListing) -> FormattedListing:
        master.validate()
        warnings: list = []

        title = master.title
        if len(title) > EBAY_TITLE_LIMIT:
            title = title[:EBAY_TITLE_LIMIT]
            warnings.append(f"title truncated to {EBAY_TITLE_LIMIT} chars for eBay")

        sku = master.sku or "APPRAZE-SKU"
        if not master.sku:
            warnings.append("no sku provided; using placeholder 'APPRAZE-SKU'")

        inventory_item = {
            "sku": sku,
            "product": {
                "title": title,
                "description": master.description,
                "condition": CONDITION_MAP[master.condition],
                "imageUrls": list(master.photos),
                # TODO: brand/size/color aspects per category requirements.
            },
            "availability": {
                "shipToLocationAvailability": {"quantity": master.quantity}
            },
        }
        offer = {
            "sku": sku,
            "marketplaceId": EBAY_US_MARKETPLACE_ID,
            "formatType": FORMAT_TYPE_FIXED_PRICE,
            "pricingSummary": {
                "price": {"value": f"{master.price:.2f}", "currency": "USD"}
            },
            "listingPolicies": {
                "fulfillmentPolicyId": TODO_FULFILLMENT_POLICY_ID,
                "paymentPolicyId": TODO_PAYMENT_POLICY_ID,
                "returnPolicyId": TODO_RETURN_POLICY_ID,
            },
        }
        payload: Dict[str, Any] = {
            "sku": sku,
            "inventory_item": inventory_item,
            "offer": offer,
        }
        return FormattedListing(
            marketplace_id=self.marketplace_id,
            payload=payload,
            warnings=warnings,
        )

    # -- not wired --------------------------------------------------------
    def publish(self, formatted: FormattedListing) -> Dict[str, Any]:
        self._require_enabled()
        raise NotConfiguredError(
            "eBay publish() not wired in scaffold. TODO: "
            "1) OAuth Authorization-Code flow -> user access token; "
            "2) PUT /sell/inventory/v1/inventory_item/{sku}; "
            "3) POST /sell/inventory/v1/offer; "
            "4) POST /sell/inventory/v1/offer/{offerId}/publish."
        )

    def delist(self, external_id: str) -> Dict[str, Any]:
        self._require_enabled()
        raise NotConfiguredError(
            "eBay delist() not wired in scaffold. TODO: withdrawOffer "
            "(POST /sell/inventory/v1/offer/{offerId}/withdraw) and/or "
            "deleteInventoryItem."
        )
