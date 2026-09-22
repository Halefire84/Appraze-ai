"""CRTC auction acquisition-cost math.

Keeps auction-specific cost inputs separate from market valuation. A bid is
not the same as the amount that ultimately leaves the buyer's pocket: buyer
premium, per-lot fees, and shipping/handling can materially change the deal.

Percentages are represented as percentage points (18 means 18%). Unknown
fees remain unknown rather than being silently invented.

buyer_premium_pct and per_lot_fee are settings-driven (brief item 3,
deal_settings.DealMathSettings.buyer_premium_pct / per_lot_fee) -- pass
`apply_default_fees=True` to fall back to those user-editable defaults
(13% / $1) when a caller omits the listing-specific values, instead of
leaving the cost UNKNOWN. Off by default so the existing "an omitted
premium must never silently become a safe max bid" behavior (see
decision_policy.py F-05 and tests/test_auction_costs.py) is unchanged
unless a caller opts in.
"""
from typing import Any, Dict, Optional

from number_normalize import parse_percent_points
from deal_settings import DealMathSettings


def _number(value: Any) -> Optional[float]:
    if value in (None, "", False):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace("$", "").replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def calculate_auction_cost(
    bid: float,
    *,
    buyer_premium_pct: Optional[float] = None,
    shipping: Optional[float] = None,
    other_fees: Optional[float] = None,
    per_lot_fee: Optional[float] = None,
    apply_default_fees: bool = False,
    settings: Optional[DealMathSettings] = None,
) -> Dict[str, Any]:
    """Return transparent all-in acquisition cost for an auction bid.

    per_lot_fee is a fixed per-lot charge, kept separate from `other_fees`
    (an open bucket for whatever else a caller already knows about) so the
    settings-driven default (brief item 3) can be reported on its own line.
    When apply_default_fees=True, an omitted buyer_premium_pct/per_lot_fee
    falls back to settings.buyer_premium_pct / settings.per_lot_fee.
    """
    settings = settings or DealMathSettings()
    if apply_default_fees:
        if buyer_premium_pct is None:
            buyer_premium_pct = settings.buyer_premium_pct
        if per_lot_fee is None:
            per_lot_fee = settings.per_lot_fee

    bid_value = max(0.0, float(bid))
    # Routes through the canonical percent parser so "18", "18%", and the
    # 0.18-fraction ambiguity all normalize to the same 18 percentage
    # points, instead of a bare float() cast that would treat 0.18 as
    # 0.18% -- a 100x unit error (see number_normalize.py / F-06, F-17).
    premium = parse_percent_points(buyer_premium_pct) if buyer_premium_pct is not None else None
    if premium is not None:
        premium = max(0.0, premium)
    ship = None if shipping is None else max(0.0, float(shipping))
    fees = None if other_fees is None else max(0.0, float(other_fees))
    lot_fee = None if per_lot_fee is None else max(0.0, float(per_lot_fee))

    premium_amount = bid_value * premium / 100 if premium is not None else None
    known_addons = (premium_amount or 0.0) + (ship or 0.0) + (fees or 0.0) + (lot_fee or 0.0)
    all_in_cost = bid_value + known_addons
    complete = premium is not None and ship is not None

    return {
        "bid": round(bid_value, 2),
        "buyer_premium_pct": premium,
        "buyer_premium_amount": round(premium_amount, 2) if premium_amount is not None else None,
        "shipping": ship,
        "other_fees": fees,
        "per_lot_fee": lot_fee,
        "known_addons": round(known_addons, 2),
        "all_in_cost": round(all_in_cost, 2),
        "complete": complete,
    }


def max_bid_for_target_all_in(
    max_all_in_cost: float,
    *,
    buyer_premium_pct: Optional[float] = None,
    shipping: Optional[float] = None,
    other_fees: Optional[float] = None,
    per_lot_fee: Optional[float] = None,
    apply_default_fees: bool = False,
    settings: Optional[DealMathSettings] = None,
) -> Optional[float]:
    """Invert all-in cost to a maximum bid; return None if premium is unknown."""
    settings = settings or DealMathSettings()
    if apply_default_fees:
        if buyer_premium_pct is None:
            buyer_premium_pct = settings.buyer_premium_pct
        if per_lot_fee is None:
            per_lot_fee = settings.per_lot_fee
    if buyer_premium_pct is None:
        return None
    premium = parse_percent_points(buyer_premium_pct)
    if premium is None:
        return None
    fixed = (
        max(0.0, float(shipping or 0.0))
        + max(0.0, float(other_fees or 0.0))
        + max(0.0, float(per_lot_fee or 0.0))
    )
    multiplier = 1.0 + max(0.0, premium) / 100
    return round(max(0.0, float(max_all_in_cost) - fixed) / multiplier, 2)
