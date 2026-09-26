"""Mercari adapter — assisted publishing only. NO private APIs, ever.

How it works: ``format_listing()`` builds the complete assisted payload
(title, price, description, photos, hashtags, condition label, shipping
note) plus the official public listing-creation URL and clipboard-ready
text. The seller opens the URL, pastes the payload into Mercari's own
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

# Mercari's official public sell entry point (verify if it ever changes).
MERCARI_CREATE_URL = "https://www.mercari.com/sell/"

# Appraze Condition -> Mercari condition picker label.
CONDITION_LABELS = {
    Condition.NEW: "New",
    Condition.LIKE_NEW: "Like new",
    Condition.GOOD: "Good",
    Condition.FAIR: "Fair",
    Condition.FOR_PARTS: "Fair",  # disclose "for parts" in the description
}


class MercariAdapter(MarketplaceAdapter):
    """Assisted-publishing adapter for Mercari."""

    marketplace_id = "mercari"

    def format_listing(self, master: MasterListing) -> FormattedListing:
        warnings = []
        if master.condition is Condition.FOR_PARTS:
            warnings.append(
                "Mercari has no 'for parts' condition; labeled 'Fair' — "
                "disclose 'for parts' clearly in the description."
            )
        payload = build_assisted_payload(
            master,
            marketplace_id=self.marketplace_id,
            deep_link=MERCARI_CREATE_URL,
            hashtags=("#mercari",),
            condition_label=CONDITION_LABELS[master.condition],
        )
        warnings.append(
            "Assisted publishing: open the deep link, paste the payload "
            "into Mercari's own form, and click publish yourself."
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
            "Mercari is assisted-only by design: open "
            f"{MERCARI_CREATE_URL}, paste the generated payload into "
            "Mercari's own form, and click publish yourself. "
            "No API call is ever made."
        )

    def delist(self, external_id: str) -> Dict[str, Any]:
        self._require_enabled()
        raise NotConfiguredError(
            "Mercari delist is manual in this scaffold: remove the listing "
            "in the Mercari app/site and record it in DelistTracker. "
            "TODO: official integration if one ever becomes available."
        )
