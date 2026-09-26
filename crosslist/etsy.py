"""Etsy adapter — official Etsy Open API v3 listings scaffolding.

Intended (NOT YET WIRED) flow:
  1. OAuth 2.0 Authorization-Code (+PKCE) -> seller access token
     (scopes: listings_w, shops_w — see crosslist.config).
  2. POST /v3/application/shops/{shop_id}/listings        (createListing)
  3. POST /v3/application/shops/{shop_id}/listings/{id}/images
     (uploadListingImage) once per photo
  4. Publish: listings are active immediately on create (state=active),
     or create as draft then POST .../listings/{id}/publish.

No credentials exist anywhere; every credential-dependent step is a
clearly-marked TODO. ``format_listing()`` is pure and builds the
createListing body; ``publish()`` / ``delist()`` raise until wired.
"""

from __future__ import annotations

from typing import Any, Dict

from crosslist.base import FormattedListing, MarketplaceAdapter, NotConfiguredError
from crosslist.config import ETSY_API_BASE_URL, ETSY_API_SCOPES
from crosslist.models import MasterListing

ETSY_TITLE_LIMIT = 140

# TODO: replace with the seller's real shop configuration (Etsy dashboard /
# getShop). Nothing here is a real credential.
TODO_SHOP_ID = "TODO_ETSY_SHOP_ID"
TODO_TAXONOMY_ID = "TODO_ETSY_TAXONOMY_ID"  # seller taxonomy (category) id
TODO_SHIPPING_PROFILE_ID = "TODO_ETSY_SHIPPING_PROFILE_ID"
# TODO: choose per item from Etsy's when_made enum (resale items on Etsy
# must be vintage — 20+ years old — or craft supplies).
TODO_WHEN_MADE = "TODO_ETSY_WHEN_MADE"


class EtsyAdapter(MarketplaceAdapter):
    """Formats listings for the official Etsy Open API v3."""

    marketplace_id = "etsy"

    def __init__(self) -> None:
        # TODO: wire OAuth — API key + shared secret + redirect URI live in
        # server-side secrets (never in the repo), token refresh + storage.
        self.base_url = ETSY_API_BASE_URL
        self.scopes = list(ETSY_API_SCOPES)
        self.access_token: str | None = None  # TODO: obtain via OAuth flow

    # -- pure formatting -------------------------------------------------
    def format_listing(self, master: MasterListing) -> FormattedListing:
        master.validate()
        warnings: list = []

        title = master.title
        if len(title) > ETSY_TITLE_LIMIT:
            title = title[:ETSY_TITLE_LIMIT]
            warnings.append(f"title truncated to {ETSY_TITLE_LIMIT} chars for Etsy")
        warnings.append(
            "taxonomy_id / shipping_profile_id / when_made are TODO placeholders; "
            "the seller must configure them before any real listing."
        )

        # Mirrors the createListing request body (Etsy Open API v3).
        listing_body = {
            "quantity": master.quantity,
            "title": title,
            "description": master.description,
            "price": round(master.price, 2),
            "who_made": "someone_else",  # resale of pre-owned goods
            "is_supply": False,
            "when_made": TODO_WHEN_MADE,
            "taxonomy_id": TODO_TAXONOMY_ID,
            "shipping_profile_id": TODO_SHIPPING_PROFILE_ID,
            "is_personalizable": False,
            "should_auto_renew": False,
            # TODO: upload each photo via uploadListingImage, then set
            # image_ids here from the upload responses.
            "image_urls": list(master.photos),
        }
        payload: Dict[str, Any] = {
            "shop_id": TODO_SHOP_ID,
            "listing": listing_body,
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
            "Etsy publish() not wired in scaffold. TODO: "
            "1) OAuth 2.0 Authorization-Code (+PKCE) -> seller access token; "
            "2) POST /v3/application/shops/{shop_id}/listings; "
            "3) uploadListingImage per photo; "
            "4) activate / publishListingDraft."
        )

    def delist(self, external_id: str) -> Dict[str, Any]:
        self._require_enabled()
        raise NotConfiguredError(
            "Etsy delist() not wired in scaffold. TODO: deleteListing "
            "(DELETE /v3/application/shops/{shop_id}/listings/{listing_id}) "
            "or updateListing state=inactive."
        )
