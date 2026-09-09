"""CRTC multi-auction Radar and valuation orchestration.

Acquisition stays outside this module. Callers provide records obtained from
an allowed public catalog, permitted feed/export, or user-provided file.
Market comps are also caller-supplied so this layer never scrapes or invents
auction data.
"""
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from auction_costs import calculate_auction_cost, max_bid_for_target_all_in
from auction_source_adapters import build_catalog_adapter
from holy_grail_pipeline import OpportunityCandidate, rank_opportunities
from valuation_bridge import value_candidate


def rank_auction_catalog(source_key: str, records: Iterable[Dict[str, Any]], *, min_score: float = 25.0) -> List[OpportunityCandidate]:
    """Normalize and rank an auction catalog with the canonical CRTC Radar."""
    adapter = build_catalog_adapter(source_key)
    normalized = adapter.normalize_records(records)
    return rank_opportunities(normalized, min_score=min_score)


def enrich_auction_opportunities(
    opportunities: Sequence[OpportunityCandidate],
    comps_by_index: Mapping[int, Sequence[Any]],
) -> Dict[int, Dict[str, Any]]:
    """Apply canonical valuation plus transparent auction acquisition math."""
    evidence: Dict[int, Dict[str, Any]] = {}
    for index, candidate in enumerate(opportunities):
        listing = candidate.listing
        comps = list(comps_by_index.get(index, ()))
        result = value_candidate(candidate, comps)
        meta: Dict[str, Any] = {
            "result": result,
            "count": len(comps),
            "sold_count": sum(1 for comp in comps if getattr(comp, "listing_type", "") == "sold"),
            "active_count": sum(1 for comp in comps if getattr(comp, "listing_type", "") == "active"),
        }
        bid = listing.get("price")
        if bid is not None:
            cost = calculate_auction_cost(
                bid,
                buyer_premium_pct=listing.get("buyer_premium"),
                shipping=listing.get("shipping"),
            )
            meta["acquisition_cost"] = cost
            market_value = result.get("market_value")
            if market_value is not None:
                target_all_in = round(float(market_value) * 0.70, 2)
                max_bid = max_bid_for_target_all_in(
                    target_all_in,
                    buyer_premium_pct=listing.get("buyer_premium"),
                    shipping=listing.get("shipping"),
                )
                meta["target_all_in_cost"] = target_all_in
                meta["max_bid"] = max_bid
                if max_bid is None:
                    result["decision"] = "REVIEW"
                    result["reason"] = "Buyer premium is unknown, so CRTC will not claim a safe maximum auction bid."
                elif float(bid) <= max_bid:
                    result["decision"] = "BUY"
                    result["reason"] = "Bid is at or below the 70% all-in acquisition target after known auction costs."
                elif float(bid) <= float(market_value) * 0.85:
                    result["decision"] = "BORDERLINE"
                    result["reason"] = "Bid is below estimated market value but exceeds the 70% all-in acquisition target."
                else:
                    result["decision"] = "PASS"
                    result["reason"] = "Bid is too high relative to estimated market value after auction costs."
        evidence[index] = meta
    return evidence


def summarize_auction_scan(source_key: str, records: Iterable[Dict[str, Any]], *, min_score: float = 25.0) -> Dict[str, Any]:
    """Return source-aware scan metadata plus ranked CRTC opportunities."""
    adapter = build_catalog_adapter(source_key)
    normalized = adapter.normalize_records(records)
    opportunities = rank_opportunities(normalized, min_score=min_score)
    return {"source": adapter.source_name, "source_key": source_key, "fetched": len(normalized), "qualified": len(opportunities), "opportunities": opportunities}
