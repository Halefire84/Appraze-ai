"""Legitimate acquisition-to-Radar bridges for CRTC."""
from dataclasses import dataclass
from typing import Any, Dict, List

from comps_adapters import EbayAuthError, EbayBrowseAdapter, is_ebay_configured
from holy_grail_pipeline import OpportunityCandidate, rank_opportunities
from listing_normalizer import normalize_listing


@dataclass(frozen=True)
class SourceScan:
    source: str
    query: str
    fetched: int
    opportunities: List[OpportunityCandidate]


def scan_ebay(query: str, *, limit: int = 25, min_score: float = 25.0) -> SourceScan:
    """Run the CRTC last-chance eBay hunt: <=24h, $100 primary, $150 hard max."""
    if not query.strip():
        return SourceScan("eBay", query, 0, [])
    from ebay_holy_grail import scan_ebay_last_chance
    result = scan_ebay_last_chance(
        [query], limit_per_query=limit, primary_ceiling=100.0,
        absolute_ceiling=150.0, hours=24, min_score=min_score,
    )
    return SourceScan("eBay", query, int(result["fetched"]), list(result["opportunities"]))


def scan_ebay_active(query: str, *, limit: int = 25, min_score: float = 25.0) -> SourceScan:
    """Legacy active-listing scan retained for the Market Comps workflow."""
    if not query.strip():
        return SourceScan("eBay", query, 0, [])
    comps = EbayBrowseAdapter().fetch_comps(query, limit=limit)
    raw = [{
        "source": "eBay", "source_listing_id": "", "url": comp.url,
        "title": comp.title, "description": "", "price": comp.price,
        "condition": comp.condition, "shipping": comp.shipping,
    } for comp in comps]
    normalized = [normalize_listing(item) for item in raw]
    return SourceScan("eBay", query, len(normalized), rank_opportunities(normalized, min_score=min_score))


def source_scan_status() -> Dict[str, Dict[str, Any]]:
    """Return source readiness without making a network request."""
    return {"ebay": {
        "key": "ebay", "name": "eBay",
        "status": "ready" if is_ebay_configured() else "needs_credentials",
        "evidence": "active",
    }}
