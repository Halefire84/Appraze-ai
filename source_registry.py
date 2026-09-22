"""CRTC legitimate marketplace/auction source registry.

The registry is metadata and routing only. It deliberately contains no
scraping or anti-bot logic. Each source can later receive an adapter that
uses an official API, permitted feed/export, public catalog, or user-provided
input allowed by that source's terms.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    name: str
    source_type: str
    acquisition_methods: tuple
    active_evidence: bool = True
    sold_evidence: bool = False
    geographic_coverage: str = "US"
    enabled: bool = False
    source_url: str = ""
    adapter: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


_DEFAULT_SOURCES = (
    SourceDefinition("ebay", "eBay", "marketplace", ("official_api",), True, False, adapter="EbayBrowseAdapter", enabled=True),
    SourceDefinition("ctbids", "CTBids / Estate Auctions", "estate_auction", ("public_catalog", "permitted_feed", "user_export")),
    SourceDefinition("shopgoodwill", "ShopGoodwill", "charity_auction", ("public_catalog", "permitted_feed", "user_export")),
    SourceDefinition("hibid", "HiBid", "auction_platform", ("public_catalog", "permitted_feed", "user_export")),
    SourceDefinition("proxibid", "Proxibid", "auction_platform", ("public_catalog", "permitted_feed", "user_export")),
    SourceDefinition("liveauctioneers", "LiveAuctioneers", "auction_platform", ("public_catalog", "permitted_feed", "user_export")),
    SourceDefinition("invaluable", "Invaluable", "auction_platform", ("public_catalog", "permitted_feed", "user_export")),
    SourceDefinition("auctionzip", "AuctionZip", "auction_directory", ("public_catalog", "user_provided")),
    SourceDefinition("ebth", "Everything But The House", "estate_auction", ("public_catalog", "user_export")),
    SourceDefinition("maxsold", "MaxSold", "estate_auction", ("public_catalog", "user_export")),
    SourceDefinition("gsa", "GSA Auctions", "government_surplus", ("public_catalog", "permitted_feed")),
    SourceDefinition("govdeals", "GovDeals", "government_surplus", ("public_catalog", "user_export")),
    SourceDefinition("publicsurplus", "Public Surplus", "government_surplus", ("public_catalog", "user_export")),
    SourceDefinition("govplanet", "GovPlanet", "government_surplus", ("public_catalog", "user_export")),
    SourceDefinition("propertyroom", "PropertyRoom", "seized_property", ("public_catalog", "user_export")),
    SourceDefinition("municibid", "Municibid", "government_surplus", ("public_catalog", "user_export")),
    SourceDefinition("purplewave", "Purple Wave", "equipment_auction", ("public_catalog", "user_export")),
    SourceDefinition("regional_auction_houses", "Regional & Independent Auction Houses", "local_auction", ("public_catalog", "user_provided")),
    SourceDefinition("liquidation", "Retail / Commercial Liquidation", "liquidation", ("official_api", "public_catalog", "user_export")),
    SourceDefinition("specialty", "Specialty Jewelry / Watch / Coin / Collectible Auctions", "specialty_auction", ("public_catalog", "user_provided")),
)


class SourceRegistry:
    """In-memory registry used by acquisition/UI layers.

    A source is not enabled merely because it appears in the registry. It
    must have an adapter and a permitted acquisition method before being
    turned on for automated collection.
    """

    def __init__(self, sources: Iterable[SourceDefinition] = _DEFAULT_SOURCES):
        self._sources = {source.key: source for source in sources}

    def get(self, key: str) -> Optional[SourceDefinition]:
        return self._sources.get(key)

    def all(self) -> List[SourceDefinition]:
        return list(self._sources.values())

    def enabled(self) -> List[SourceDefinition]:
        return [source for source in self._sources.values() if source.enabled and source.adapter]

    def register(self, source: SourceDefinition) -> None:
        if not source.key.strip():
            raise ValueError("Source key cannot be empty")
        self._sources[source.key] = source

    def as_dict(self) -> Dict[str, Dict[str, object]]:
        return {key: source.to_dict() for key, source in self._sources.items()}


def default_source_registry() -> SourceRegistry:
    return SourceRegistry()
