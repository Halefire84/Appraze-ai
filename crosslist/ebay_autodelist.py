"""Auto-delist orchestration for eBay sandbox listings.

When an item sells on any channel (or a listing is otherwise retired),
the corresponding eBay offers must be withdrawn so the item cannot be
purchased twice. This module provides the auto-delist primitives built
on top of :mod:`ebay_sell` (the sandbox-only Sell API client).

All eBay calls go through ``ebay_sell``. No credentials are hardcoded;
they come from ``ebay_sell.load_config()`` (``EBAY_SELL_*`` environment
variables or an untracked ``ebay_config.json``). Nothing here touches
production — ``ebay_sell`` only defines sandbox hosts.
"""

from __future__ import annotations

from typing import Any

try:
    import ebay_sell  # repo-root sandbox-only Sell API client
    from ebay_sell import EbaySellClient
except ImportError:  # pragma: no cover - repo root must be on sys.path
    ebay_sell = None  # type: ignore[assignment]
    EbaySellClient = Any  # type: ignore[assignment,misc]


def _require_ebay_sell():
    """Return the ebay_sell module or raise a clear error."""
    if ebay_sell is None:
        raise RuntimeError(
            "ebay_sell module not available; ensure the repo root is on sys.path"
        )
    return ebay_sell


def delist_offers_for_sku(client: "EbaySellClient", sku: str) -> dict[str, Any]:
    """Withdraw every published eBay offer for a SKU (auto-delist primitive).

    Lists offers by SKU via the Sell Inventory API and withdraws each one
    whose status is PUBLISHED. Non-published offers are left alone.

    Returns a summary dict::

        {"sku": ..., "offers_withdrawn": [...], "status": "delisted" | "no_live_offers"}
    """
    mod = _require_ebay_sell()
    resp = client.get("/sell/inventory/v1/offer", params={"sku": sku})
    offers = resp.get("offers", []) if isinstance(resp, dict) else []
    withdrawn: list[str] = []
    for offer in offers:
        offer_id = offer.get("offerId")
        if offer.get("status") == "PUBLISHED" and offer_id:
            mod.withdraw_offer(client, offer_id)
            withdrawn.append(offer_id)
    return {
        "sku": sku,
        "offers_withdrawn": withdrawn,
        "status": "delisted" if withdrawn else "no_live_offers",
    }


def auto_delist_sku(sku: str) -> dict[str, Any]:
    """Auto-delist a SKU end-to-end on the eBay sandbox.

    Loads config, refreshes the access token, builds a client, and withdraws
    all published offers for the SKU. Call this when an item sells on any
    channel so the eBay listing cannot be purchased twice.

    Raises:
        ebay_sell.EbayConfigError: when credentials are not configured.
        ebay_sell.EbayApiError: when the eBay API returns an error.
    """
    mod = _require_ebay_sell()
    config = mod.load_config()
    token = mod.get_valid_access_token(config)
    client = mod.EbaySellClient(token)
    return delist_offers_for_sku(client, sku)
