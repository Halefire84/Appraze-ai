"""CRTC opportunity result contract.

Keeps three decisions separate: Radar lead quality, market-value confidence,
and acquisition decision. Radar is a discovery signal; it is never treated as
proof of resale value.

The acquisition decision itself is delegated to decision_policy.evaluate_deal()
-- the one canonical decision authority -- rather than reimplementing the
70% rule here independently of deal_workspace.py and auction_radar.py's own
copies of the same math (those used to disagree; see CRTC_HANDOFF.md).
"""
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from decision_policy import DECISION_BORDERLINE, DECISION_BUY, DECISION_PASS, DECISION_REVIEW, evaluate_deal

# This module's own historical decision vocabulary. build_opportunity() only
# calls evaluate_deal() with is_auction=False, require_shipping=False, so
# the canonical engine's richer vocabulary (STRONG BUY / AT CEILING /
# CONDITIONAL BUY) never actually surfaces here -- only these four ever
# will, which is why callers that pattern-match against DECISIONS still work.
DECISIONS = (DECISION_BUY, DECISION_PASS, DECISION_BORDERLINE, DECISION_REVIEW)


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

    canonical = None
    if decision is None or max_buy_price is None or not reason:
        # Non-auction acquisition cost must be all-in (item + fees + shipping
        # + tax), not just the asking price. shipping/tax/other_fees are only
        # ever known when the listing itself carries them (radar candidates
        # frequently don't yet), so they're passed through rather than
        # dropped -- previously this call never forwarded them at all, so a
        # listing with a real, known shipping or tax cost silently had it
        # excluded from the BUY verdict's all-in cost.
        shipping = listing.get("shipping")
        other_fees = listing.get("other_fees")
        tax = listing.get("tax")
        fees_total = None
        if other_fees is not None or tax is not None:
            fees_total = (other_fees or 0.0) + (tax or 0.0)
        canonical = evaluate_deal(
            price=price, market_value=value, is_auction=False,
            shipping=shipping, other_fees=fees_total, require_shipping=False,
        )

    if max_buy_price is None:
        max_buy_price = canonical.acquisition_target_all_in

    if decision is None:
        decision = canonical.decision

    if decision not in DECISIONS:
        raise ValueError(f"Unsupported CRTC decision: {decision}")

    if not reason:
        reason = canonical.reason

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
