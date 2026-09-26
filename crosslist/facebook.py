"""Facebook Marketplace adapter — assisted publishing only. NO private APIs, ever.

How it works: ``format_listing()`` builds the complete assisted payload
(title, price, description, photos, condition label, shipping note) plus
the official public listing-creation URL and clipboard-ready text. The
seller opens the URL, pastes the payload into Facebook's own Marketplace
form, and clicks publish themselves. ``publish()`` therefore raises
``AssistedPublishRequiredError`` by design — no API call is ever made.
"""

from __future__ import annotations

from typing import Any, Dict

from crosslist.assisted import (
    AssistedPublishRequiredError,
    build_assisted_payload,
)
from crosslist.base import FormattedListing, MarketplaceAdapter, NotConfiguredError
from crosslist.models import Condition, MasterListing

# Facebook's official public Marketplace create-item entry point
# (verify if it ever changes).
FACEBOOK_CREATE_URL = "https://www.facebook.com/marketplace/create/item"

# Appraze Condition -> Facebook Marketplace condition picker label.
CONDITION_LABELS = {
    Condition.NEW: "New",
    Condition.LIKE_NEW: "Used - like new",
    Condition.GOOD: "Used - good",
    Condition.FAIR: "Used - fair",
    Condition.FOR_PARTS: "Used - fair",  # disclose "for parts" in the description
}


class FacebookMarketplaceAdapter(MarketplaceAdapter):
    """Assisted-publishing adapter for Facebook Marketplace."""

    marketplace_id = "facebook"

    def format_listing(self, master: MasterListing) -> FormattedListing:
        warnings = []
        if master.condition is Condition.FOR_PARTS:
            warnings.append(
                "Facebook Marketplace has no 'for parts' condition; labeled "
                "'Used - fair' — disclose 'for parts' clearly in the description."
            )
        # Facebook Marketplace does not use hashtags; pass none.
        payload = build_assisted_payload(
            master,
            marketplace_id=self.marketplace_id,
            deep_link=FACEBOOK_CREATE_URL,
            hashtags=(),
            condition_label=CONDITION_LABELS[master.condition],
        )
        warnings.append(
            "Assisted publishing: open the deep link, paste the payload "
            "into Facebook's own Marketplace form, and click publish yourself."
        )
        return FormattedListing(
            marketplace_id=self.marketplace_id,
            payload=payload.to_dict(),
            warnings=warnings,
            assist={
                "deep_link": payload.deep_link,
                "clipboard_text": payload.clipboard_text,
            },
        )

    def publish(self, formatted: FormattedListing) -> Dict[str, Any]:
        self._require_enabled()
        raise AssistedPublishRequiredError(
            "Facebook Marketplace is assisted-only by design: open "
            f"{FACEBOOK_CREATE_URL}, paste the generated payload into "
            "Facebook's own Marketplace form, and click publish yourself. "
            "No API call is ever made."
        )

    def delist(self, external_id: str) -> Dict[str, Any]:
        self._require_enabled()
        raise NotConfiguredError(
            "Facebook Marketplace delist is manual in this scaffold: remove "
            "the listing in Facebook's Marketplace UI and record it in "
            "DelistTracker. TODO: official integration if one ever becomes "
            "available."
        )
