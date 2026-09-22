"""CRTC auction-source adapters for permitted catalog/export input.

These adapters intentionally do not scrape, bypass anti-bot controls, or
pretend that a source has an API when it does not. They accept records from a
public catalog, permitted export/feed, or user-provided catalog and normalize
those records into the existing CRTC listing schema.
"""
from typing import Any, Dict, Iterable, List

from listing_normalizer import normalize_listing


SUPPORTED_SOURCES = {
    "ctbids": "CTBids / Estate Auctions",
    "shopgoodwill": "ShopGoodwill",
    "hibid": "HiBid",
}


class AuctionCatalogAdapter:
    """Normalize permitted catalog/export records for one auction source."""

    def __init__(self, source_key: str):
        if source_key not in SUPPORTED_SOURCES:
            raise ValueError(f"Unsupported auction source: {source_key}")
        self.source_key = source_key
        self.source_name = SUPPORTED_SOURCES[source_key]

    def normalize_records(self, records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for record in records:
            item = dict(record)
            item.setdefault("source", self.source_name)
            item.setdefault("source_listing_id", item.get("lot_id", item.get("id", "")))
            item.setdefault("url", item.get("source_url", ""))
            normalized.append(normalize_listing(item))
        return normalized


def build_catalog_adapter(source_key: str) -> AuctionCatalogAdapter:
    """Return a safe adapter for CTBids, ShopGoodwill, or HiBid."""
    return AuctionCatalogAdapter(source_key)
