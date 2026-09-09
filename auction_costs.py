"""CRTC auction acquisition-cost math.

Keeps auction-specific cost inputs separate from market valuation. A bid is
not the same as the amount that ultimately leaves the buyer's pocket: buyer
premium and shipping/handling can materially change the deal.

Percentages are represented as percentage points (18 means 18%). Unknown
fees remain unknown rather than being silently invented.
"""
from typing import Any, Dict, Optional


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
) -> Dict[str, Any]:
    """Return transparent all-in acquisition cost for an auction bid."""
    bid_value = max(0.0, float(bid))
    premium = None if buyer_premium_pct is None else max(0.0, float(buyer_premium_pct))
    ship = None if shipping is None else max(0.0, float(shipping))
    fees = None if other_fees is None else max(0.0, float(other_fees))

    premium_amount = bid_value * premium / 100 if premium is not None else None
    known_addons = (premium_amount or 0.0) + (ship or 0.0) + (fees or 0.0)
    all_in_cost = bid_value + known_addons
    complete = premium is not None and ship is not None

    return {
        "bid": round(bid_value, 2),
        "buyer_premium_pct": premium,
        "buyer_premium_amount": round(premium_amount, 2) if premium_amount is not None else None,
        "shipping": ship,
        "other_fees": fees,
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
) -> Optional[float]:
    """Invert all-in cost to a maximum bid; return None if premium is unknown."""
    if buyer_premium_pct is None:
        return None
    fixed = max(0.0, float(shipping or 0.0)) + max(0.0, float(other_fees or 0.0))
    multiplier = 1.0 + max(0.0, float(buyer_premium_pct)) / 100
    return round(max(0.0, float(max_all_in_cost) - fixed) / multiplier, 2)
