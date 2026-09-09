"""CRTC valuation bridge for permitted auction-catalog imports."""
from typing import Any, Dict, List

from auction_costs import calculate_auction_cost, max_bid_for_target_all_in
from holy_grail_pipeline import OpportunityCandidate
from opportunity_sources import enrich_ebay_opportunities


def value_auction_opportunities(
    opportunities: List[OpportunityCandidate],
    *,
    limit: int = 10,
    comps_limit: int = 12,
) -> Dict[int, Dict[str, Any]]:
    """Value auction leads and expose transparent all-in acquisition costs.

    Market value still comes from the existing comps engine. Auction cost
    inputs come from each normalized listing. No fee is invented when the
    catalog did not provide it; an incomplete cost model remains REVIEW.
    """
    evidence = enrich_ebay_opportunities(
        opportunities,
        limit=limit,
        comps_limit=comps_limit,
    )

    for index, candidate in enumerate(opportunities[:max(0, int(limit))]):
        listing = candidate.listing
        meta = evidence.setdefault(index, {})
        bid = listing.get("price")
        if bid is None:
            meta["acquisition_cost"] = None
            continue

        cost = calculate_auction_cost(
            bid,
            buyer_premium_pct=listing.get("buyer_premium"),
            shipping=listing.get("shipping"),
        )
        meta["acquisition_cost"] = cost

        result = meta.get("result")
        if result and result.get("market_value") is not None:
            target_all_in = float(result["market_value"]) * 0.70
            max_bid = max_bid_for_target_all_in(
                target_all_in,
                buyer_premium_pct=listing.get("buyer_premium"),
                shipping=listing.get("shipping"),
            )
            meta["target_all_in_cost"] = round(target_all_in, 2)
            meta["max_bid"] = max_bid
            if max_bid is None:
                result["decision"] = "REVIEW"
                result["reason"] = "Buyer premium is unknown, so CRTC will not claim a safe maximum auction bid."
            elif float(bid) <= max_bid:
                result["decision"] = "BUY"
                result["reason"] = "Bid is at or below the 70% all-in acquisition target after known auction costs."
            elif float(bid) <= float(result["market_value"]) * 0.85:
                result["decision"] = "BORDERLINE"
                result["reason"] = "Bid is below estimated market value but exceeds the 70% all-in acquisition target."
            else:
                result["decision"] = "PASS"
                result["reason"] = "Bid is too high relative to estimated market value after auction costs."

    return evidence
