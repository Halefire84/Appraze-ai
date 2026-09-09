"""Legitimate acquisition-to-Radar bridges for CRTC."""
from dataclasses import dataclass
from typing import Any, Dict, List

from comps_adapters import (
    EbayBrowseAdapter,
    EbayMarketplaceInsightsAdapter,
    EbayInsightsNotApprovedError,
    is_ebay_configured,
    is_marketplace_insights_configured,
)
from holy_grail_pipeline import OpportunityCandidate, rank_opportunities
from listing_normalizer import normalize_listing
from valuation_bridge import value_candidate


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


def enrich_ebay_opportunities(opportunities: List[OpportunityCandidate], *, limit: int = 10, comps_limit: int = 12) -> Dict[int, Dict[str, Any]]:
    """Attach real market evidence to the highest-ranked Radar leads.

    Sold evidence is used when eBay Marketplace Insights is approved. When
    it is not approved, CRTC falls back to official active-listing comps and
    keeps their confidence low. No sold prices are fabricated or inferred.
    """
    evidence: Dict[int, Dict[str, Any]] = {}
    selected = opportunities[:max(0, int(limit))]
    use_sold = is_marketplace_insights_configured()
    sold_adapter = EbayMarketplaceInsightsAdapter() if use_sold else None
    active_adapter = EbayBrowseAdapter()

    for index, candidate in enumerate(selected):
        title = str(candidate.listing.get("title") or "").strip()
        if not title:
            evidence[index] = {"result": value_candidate(candidate, []), "evidence_type": "none", "count": 0}
            continue
        try:
            if sold_adapter is not None:
                comps = sold_adapter.fetch_comps(title, limit=comps_limit)
                evidence_type = "sold"
            else:
                comps = active_adapter.fetch_comps(title, limit=comps_limit)
                evidence_type = "active"
        except EbayInsightsNotApprovedError:
            comps = active_adapter.fetch_comps(title, limit=comps_limit)
            evidence_type = "active"
        result = value_candidate(candidate, comps)
        evidence[index] = {
            "result": result,
            "evidence_type": evidence_type if comps else "none",
            "count": len(comps),
            "sold_count": sum(1 for comp in comps if comp.listing_type == "sold"),
            "active_count": sum(1 for comp in comps if comp.listing_type == "active"),
        }
    return evidence


def source_scan_status() -> Dict[str, Dict[str, Any]]:
    """Return source readiness without making a network request."""
    return {"ebay": {
        "key": "ebay", "name": "eBay",
        "status": "ready" if is_ebay_configured() else "needs_credentials",
        "evidence": "sold+active" if is_marketplace_insights_configured() else "active",
    }}
