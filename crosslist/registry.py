"""Adapter registry + feature-flag gating.

Single place that knows all six marketplace adapters and their
Coming Soon status. ``get_adapter()`` returns an adapter instance for
formatting (always allowed — formatting is pure and offline).
``get_adapter_gated()`` additionally enforces the APPRAZE_CROSSLIST
feature flag for anything that could publish.
"""

from __future__ import annotations

from typing import Dict, List, Type

from crosslist import depop, ebay, etsy, facebook, mercari, poshmark
from crosslist.base import CrosslistDisabledError, MarketplaceAdapter
from crosslist.config import MARKETPLACES, crosslisting_enabled

_ADAPTER_CLASSES: Dict[str, Type[MarketplaceAdapter]] = {
    "ebay": ebay.EbayAdapter,
    "etsy": etsy.EtsyAdapter,
    "depop": depop.DepopStubAdapter,
    "poshmark": poshmark.PoshmarkAdapter,
    "mercari": mercari.MercariAdapter,
    "facebook": facebook.FacebookMarketplaceAdapter,
}


def get_adapter(marketplace_id: str) -> MarketplaceAdapter:
    """Return an adapter instance. Formatting is pure/offline: always allowed."""
    try:
        cls = _ADAPTER_CLASSES[marketplace_id.strip().lower()]
    except KeyError:
        raise ValueError(f"unknown marketplace: {marketplace_id!r}")
    return cls()


def get_adapter_gated(marketplace_id: str) -> MarketplaceAdapter:
    """Like get_adapter(), but refuses when the feature flag is OFF."""
    if not crosslisting_enabled():
        raise CrosslistDisabledError(
            "Cross-listing is disabled (APPRAZE_CROSSLIST is not set). "
            "Scaffold is 'Coming Soon' — nothing may publish."
        )
    return get_adapter(marketplace_id)


def list_marketplaces() -> List[dict]:
    """All six marketplaces with Coming Soon status + current flag state."""
    enabled = crosslisting_enabled()
    return [
        {
            "id": mid,
            "label": meta["label"],
            "mode": meta["mode"],
            "status": meta["status"],
            "notes": meta["notes"],
            "enabled": enabled,
        }
        for mid, meta in MARKETPLACES.items()
    ]
