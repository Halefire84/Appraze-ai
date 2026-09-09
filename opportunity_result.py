"""CRTC canonical opportunity result contract.

Keeps three decisions separate: anomaly lead strength (Radar), market-value
confidence (comps/valuation), and purchase verdict (CRTC). A Radar hit is never
silently promoted to BUY.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import finance
from opportunity_radar import RadarResult, analyze_listing


@dataclass(frozen=True)
class OpportunityResult:
    listing: dict
    radar: RadarResult
    market_value: Optional[float] = None
    market_confidence: str = "unknown"
    verdict: Optional[str] = None
    max_buy_price: Optional[float] = None
    rationale: Tuple[str, ...] = ()


def _positive_number(value: object) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def build_opportunity_result(
    listing: dict,
    *,
    market_value: Optional[float] = None,
    market_confidence: str = "unknown",
    verdict: Optional[str] = None,
    max_buy_price: Optional[float] = None,
) -> OpportunityResult:
    """Build a result without conflating missing/zero valuation evidence.

    The purchase verdict and max-buy price are never derived from the Radar
    score. When they aren't supplied by the caller, they are computed from
    price + value evidence alone via finance.py (the same deterministic
    engine used across the rest of CRTC) so this module never duplicates
    that math.
    """
    evidence_value = market_value if market_value is not None else listing.get("estimated_value")
    radar = analyze_listing({**listing, "estimated_value": evidence_value})

    asking_price = _positive_number(listing.get("price"))
    resale_value = _positive_number(evidence_value)
    if resale_value is not None:
        if verdict is None and asking_price is not None:
            deal = finance.calc_deal(cost=asking_price, resale_value=resale_value)
            verdict = deal.verdict
        if max_buy_price is None:
            max_buy_price = round(finance.max_cost_for_target_roi(resale_value), 2)

    rationale = tuple(signal.message for signal in radar.signals)
    return OpportunityResult(
        listing=dict(listing),
        radar=radar,
        market_value=market_value,
        market_confidence=market_confidence,
        verdict=verdict,
        max_buy_price=max_buy_price,
        rationale=rationale,
    )
