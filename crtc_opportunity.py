"""CRTC opportunity result contract.

Keeps three decisions separate: Radar lead quality, market-value confidence,
and acquisition decision. Radar is a discovery signal; it is never treated as
proof of resale value.
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


DECISIONS = ("BUY", "PASS", "BORDERLINE", "REVIEW")


@dataclass(frozen=True)
class CRTCOpportunity:
    source: str
    title: str
    url: str
    asking_price: Optional[float]
    radar_score: float
    radar_tier: str
    market_value: Optional[float]
    market_confidence: str
    decision: str
    max_buy_price: Optional[float]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_opportunity(candidate: Any, *, market_value: Optional[float] = None,
                      market_confidence: str = "UNKNOWN",
                      max_buy_price: Optional[float] = None,
                      decision: Optional[str] = None,
                      reason: str = "") -> CRTCOpportunity:
    """Build the product-facing result from an existing Radar candidate.

    If valuation evidence is absent, the result stays REVIEW rather than
    inventing a BUY/PASS decision. When a market value is supplied, the
    default maximum acquisition price is 70% of that value unless explicitly
    provided.
    """
    listing = candidate.listing
    price = listing.get("price")
    value = market_value if market_value is not None else listing.get("estimated_value")
    if max_buy_price is None and value is not None:
        max_buy_price = round(float(value) * 0.70, 2)

    if decision is None:
        if price is None or value is None:
            decision = "REVIEW"
        elif float(price) <= float(max_buy_price):
            decision = "BUY"
        elif float(price) <= float(value) * 0.85:
            decision = "BORDERLINE"
        else:
            decision = "PASS"

    if decision not in DECISIONS:
        raise ValueError(f"Unsupported CRTC decision: {decision}")

    if not reason:
        if decision == "BUY":
            reason = "Asking price is at or below the 70% acquisition target."
        elif decision == "BORDERLINE":
            reason = "Price is below estimated market value but above the 70% target."
        elif decision == "PASS":
            reason = "Asking price is too high relative to the available market value."
        else:
            reason = "More market-value evidence is required before a purchase decision."

    return CRTCOpportunity(
        source=str(listing.get("source") or ""),
        title=str(listing.get("title") or ""),
        url=str(listing.get("source_url") or listing.get("url") or ""),
        asking_price=float(price) if price is not None else None,
        radar_score=float(candidate.score),
        radar_tier=str(candidate.tier),
        market_value=float(value) if value is not None else None,
        market_confidence=str(market_confidence).upper(),
        decision=decision,
        max_buy_price=max_buy_price,
        reason=reason,
    )
