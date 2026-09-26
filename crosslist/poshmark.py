"""Poshmark adapter — assisted publishing only. NO private APIs, ever.

How it works: ``format_listing()`` builds the complete assisted payload
(title, price, description, photos, hashtags, condition label, shipping
note) plus the official public listing-creation URL and clipboard-ready
text. The seller opens the URL, pastes the payload into Poshmark's own
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

# Poshmark's official public sell entry point (verify if it ever changes).
POSHMARK_CREATE_URL = "https://poshmark.com/sell"

# Appraze Condition -> Poshmark condition picker label.
CONDITION_LABELS = {
    Condition.NEW: "New without tags",
    Condition.LIKE_NEW: "Like new",
    Condition.GOOD: "Good",
    Condition.FAIR: "Fair",
    Condition.FOR_PARTS: "Fair",  # disclose "for parts" in the description
}


class PoshmarkAdapter(MarketplaceAdapter):
    """Assisted-publishing adapter for Poshmark."""

    marketplace_id = "poshmark"

    def format_listing(self, master: MasterListing) -> FormattedListing:
        warnings = []
        if master.condition is Condition.FOR_PARTS:
            warnings.append(
                "Poshmark has no 'for parts' condition; labeled 'Fair' — "
                "disclose 'for parts' clearly in the description."
            )
        payload = build_assisted_payload(
            master,
            marketplace_id=self.marketplace_id,
            deep_link=POSHMARK_CREATE_URL,
            hashtags=("#poshmark", "#shopmycloset"),
            condition_label=CONDITION_LABELS[master.condition],
        )
        warnings.append(
            "Assisted publishing: open the deep link, paste the payload "
            "into Poshmark's own form, and click publish yourself."
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
            "Poshmark is assisted-only by design: open "
            f"{POSHMARK_CREATE_URL}, paste the generated payload into "
            "Poshmark's own form, and click publish yourself. "
            "No API call is ever made."
        )

    def delist(self, external_id: str) -> Dict[str, Any]:
        self._require_enabled()
        raise NotConfiguredError(
            "Poshmark delist is manual in this scaffold: remove the listing "
            "in the Poshmark app/site and record it in DelistTracker. "
            "TODO: official integration if one ever becomes available."
        )
