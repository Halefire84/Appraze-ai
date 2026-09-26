"""Appraze cross-listing scaffold — six-marketplace architecture.

One master listing is adapted and (eventually) published to: eBay, Etsy,
Depop, Poshmark, Mercari, and Facebook Marketplace.

SCAFFOLD STATUS (see docs/CROSSLIST_SCAFFOLD.md for the honest done/stubbed list):
- Everything in this package is behind the ``APPRAZE_CROSSLIST`` feature flag
  (default OFF) and labeled "Coming Soon". Nothing here publishes anything real.
- eBay / Etsy: official-API scaffolding only, with placeholder credentials
  and clearly-marked TODOs.
- Depop: stub only — awaiting partner-API approval.
- Poshmark / Mercari / Facebook Marketplace: NO private or
  reverse-engineered APIs are used, ever. Assisted-publishing framework only:
  each adapter generates the complete listing payload plus a
  prefill / open-in-browser helper, and the human clicks the final publish
  button. A delist tracker stub records where each item was listed.

Hard rules honored by this package:
- No reverse-engineered private APIs.
- No real credentials anywhere (placeholders + TODO only).
- No real listings, purchases, or money movement.
"""

from crosslist.base import MarketplaceAdapter
from crosslist.config import MARKETPLACES, crosslisting_enabled
from crosslist.models import (
    Condition,
    MasterListing,
    ShippingInfo,
)
from crosslist.registry import get_adapter, list_marketplaces

__all__ = [
    "MARKETPLACES",
    "Condition",
    "MarketplaceAdapter",
    "MasterListing",
    "ShippingInfo",
    "crosslisting_enabled",
    "get_adapter",
    "list_marketplaces",
]
