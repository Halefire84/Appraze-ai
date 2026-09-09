"""CRTC valuation bridge for permitted auction-catalog imports."""
from typing import Any, Dict, List

from holy_grail_pipeline import OpportunityCandidate
from opportunity_sources import enrich_ebay_opportunities


def value_auction_opportunities(
    opportunities: List[OpportunityCandidate],
    *,
    limit: int = 10,
    comps_limit: int = 12,
) -> Dict[int, Dict[str, Any]]:
    """Value the strongest auction leads using the existing comps engine.

    eBay is used only as the market-evidence source here. Sold evidence is
    used when the account has Marketplace Insights approval; otherwise the
    existing active-listing fallback is clearly labeled low-confidence.
    """
    return enrich_ebay_opportunities(
        opportunities,
        limit=limit,
        comps_limit=comps_limit,
    )
