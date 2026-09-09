"""CRTC opportunity result contract.

Keeps three decisions separate: anomaly lead strength (Radar), market-value
confidence (comps/valuation), and purchase verdict (CRTC). A Radar hit is never
silently promoted to BUY.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

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


def build_opportunity_result(listing: dict, *, market_value: Optional[float] = None,
                             market_confidence: str = "unknown",
                             verdict: Optional[str] = None,
                             max_buy_price: Optional[float] = None) -> OpportunityResult:
    radar = analyze_listing({**listing, "estimated_value": market_value or listing.get("estimated_value")})
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
