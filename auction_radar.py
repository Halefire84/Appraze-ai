"""CRTC multi-auction Radar and valuation orchestration.

Acquisition stays outside this module. Callers provide records obtained from
an allowed public catalog, permitted feed/export, or user-provided file.
Market comps are also caller-supplied so this layer never scrapes or invents
auction data.

Acquisition decisions delegate to decision_policy.evaluate_deal() -- the one
canonical decision authority -- rather than the inline 70%-rule copy this
module used to carry independently of deal_workspace.py and
crtc_opportunity.py's own separate copies of the same math.
"""
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from auction_source_adapters import build_catalog_adapter
from decision_policy import evaluate_deal
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
            market_value = result.get("market_value")
            premium_pct = listing.get("buyer_premium_pct")
            if premium_pct is None:
                premium_pct = listing.get("buyer_premium")  # legacy key, percentage points
            decision = evaluate_deal(
                price=bid,
                market_value=market_value,
                is_auction=True,
                buyer_premium_pct=premium_pct,
                shipping=listing.get("shipping"),
                other_fees=listing.get("other_fees"),
                require_shipping=True,
            )
            # Preserve the calculate_auction_cost()-shaped dict the Auction
            # Hunt page reads (cost.get("all_in_cost")) rather than exposing
            # decision_policy's own richer cost_components shape here.
            cost = {
                "bid": round(float(bid), 2),
                "buyer_premium_pct": None,
                "buyer_premium_amount": None,
                "shipping": None,
                "other_fees": None,
                "known_addons": 0.0,
                "all_in_cost": decision.all_in_cost,
                "complete": decision.costs_complete,
            }
            for component in decision.cost_components:
                if component.name == "buyer_premium_pct":
                    cost["buyer_premium_pct"] = component.amount
                elif component.name == "buyer_premium":
                    cost["buyer_premium_amount"] = component.amount
                elif component.name == "shipping":
                    cost["shipping"] = component.amount
                elif component.name == "other_fees":
                    cost["other_fees"] = component.amount
            cost["known_addons"] = round(
                sum(v for v in (cost["buyer_premium_amount"], cost["shipping"], cost["other_fees"]) if v is not None),
                2,
            )
            meta["acquisition_cost"] = cost
            if market_value is not None:
                meta["target_all_in_cost"] = decision.acquisition_target_all_in
                meta["max_bid"] = decision.max_bid_or_price
                result["decision"] = decision.decision
                result["reason"] = decision.reason
        evidence[index] = meta
    return evidence


def summarize_auction_scan(source_key: str, records: Iterable[Dict[str, Any]], *, min_score: float = 25.0) -> Dict[str, Any]:
    """Return source-aware scan metadata plus ranked CRTC opportunities."""
    adapter = build_catalog_adapter(source_key)
    normalized = adapter.normalize_records(records)
    opportunities = rank_opportunities(normalized, min_score=min_score)
    return {"source": adapter.source_name, "source_key": source_key, "fetched": len(normalized), "qualified": len(opportunities), "opportunities": opportunities}
