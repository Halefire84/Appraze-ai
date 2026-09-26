"""Assisted-publishing framework for Poshmark / Mercari / Facebook Marketplace.

NO private or reverse-engineered APIs are used, ever. For these three
marketplaces each adapter:

  1. Generates the COMPLETE listing payload (title, price, description,
     photos, hashtags, category hint, condition label, shipping note).
  2. Builds a prefill / open-in-browser helper: the marketplace's official
     public listing-creation URL (deep link) plus clipboard-ready text the
     seller pastes into the marketplace's own form.
  3. The HUMAN clicks the final publish button in the marketplace's own UI.

A :class:`crosslist.tracker.DelistTracker` records where each item was
listed so a future official integration (or the human) can delist
consistently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence

from crosslist.base import NotConfiguredError
from crosslist.models import MasterListing


class AssistedPublishRequiredError(NotConfiguredError):
    """Raised by assisted adapters: the human must click publish."""


@dataclass
class AssistedListingPayload:
    """Everything a human needs to list the item by hand."""

    marketplace_id: str
    title: str
    price_display: str  # e.g. "$45.00"
    description: str
    photos: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    category_hint: str = ""
    condition_label: str = ""
    shipping_note: str = ""
    deep_link: str = ""  # official public listing-creation URL
    clipboard_text: str = ""  # paste-ready: title / price / description / tags

    def to_dict(self) -> dict:
        return {
            "marketplace_id": self.marketplace_id,
            "title": self.title,
            "price_display": self.price_display,
            "description": self.description,
            "photos": list(self.photos),
            "hashtags": list(self.hashtags),
            "category_hint": self.category_hint,
            "condition_label": self.condition_label,
            "shipping_note": self.shipping_note,
            "deep_link": self.deep_link,
            "clipboard_text": self.clipboard_text,
        }


def default_hashtags(master: MasterListing, extra: Sequence[str] = ()) -> List[str]:
    """Small deterministic hashtag set from brand/category plus extras."""
    tags: List[str] = []
    for word in (master.brand, master.category):
        for part in str(word).replace("-", " ").split():
            clean = "".join(c for c in part if c.isalnum())
            if clean:
                tags.append("#" + clean.lower())
    tags.extend(extra)
    seen = set()
    unique: List[str] = []
    for tag in tags:
        tag = tag if tag.startswith("#") else "#" + tag
        if tag not in seen:
            seen.add(tag)
            unique.append(tag)
    return unique


def build_clipboard_text(master: MasterListing, hashtags: Sequence[str]) -> str:
    """Paste-ready text: title, price, description, hashtags."""
    lines = [
        master.title,
        "",
        f"Price: ${master.price:.2f}",
        "",
        master.description,
    ]
    if hashtags:
        lines += ["", " ".join(hashtags)]
    return "\n".join(lines)


def build_shipping_note(master: MasterListing) -> str:
    ship = master.shipping
    if ship.cost > 0:
        return f"Ships via {ship.method} — ${ship.cost:.2f} shipping"
    return f"Ships via {ship.method} — free shipping"


def build_assisted_payload(
    master: MasterListing,
    *,
    marketplace_id: str,
    deep_link: str,
    hashtags: Sequence[str] = (),
    condition_label: str = "",
) -> AssistedListingPayload:
    """Build the complete assisted payload for one marketplace."""
    master.validate()
    tags = default_hashtags(master, hashtags)
    return AssistedListingPayload(
        marketplace_id=marketplace_id,
        title=master.title,
        price_display=f"${master.price:.2f}",
        description=master.description,
        photos=list(master.photos),
        hashtags=tags,
        category_hint=master.category,
        condition_label=condition_label,
        shipping_note=build_shipping_note(master),
        deep_link=deep_link,
        clipboard_text=build_clipboard_text(master, tags),
    )
