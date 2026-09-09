"""CRTC deal workspace helpers for turning Radar leads into purchase decisions."""
from typing import Any, Dict, Optional

from auction_costs import calculate_auction_cost, max_bid_for_target_all_in


def build_deal_workspace(listing: Dict[str, Any], market_value: Optional[float] = None, confidence: str = "UNKNOWN") -> Dict[str, Any]:
    """Build one transparent, UI-ready deal record without inventing evidence."""
    price = listing.get("price")
    value = market_value if market_value is not None else listing.get("estimated_value")
    source = str(listing.get("source") or "")
    is_auction = source.lower() in {"ctbids / estate auctions", "shopgoodwill", "hibid"} or listing.get("buyer_premium") is not None

    if price is None:
        return {"decision": "REVIEW", "reason": "No asking/current-bid price supplied.", "max_bid": None, "all_in": None, "market_value": value, "confidence": confidence}
    if value is None:
        return {"decision": "REVIEW", "reason": "Market-value evidence is required before a purchase decision.", "max_bid": None, "all_in": None, "market_value": None, "confidence": confidence}

    target_all_in = round(float(value) * 0.70, 2)
    if is_auction:
        cost = calculate_auction_cost(price, buyer_premium_pct=listing.get("buyer_premium"), shipping=listing.get("shipping"))
        max_bid = max_bid_for_target_all_in(target_all_in, buyer_premium_pct=listing.get("buyer_premium"), shipping=listing.get("shipping"))
        if max_bid is None:
            return {"decision": "REVIEW", "reason": "Auction buyer premium is unknown; CRTC will not claim a safe maximum bid.", "max_bid": None, "all_in": cost, "market_value": float(value), "confidence": confidence}
        decision = "BUY" if float(price) <= max_bid else "BORDERLINE" if float(price) <= float(value) * 0.85 else "PASS"
        reason = {"BUY": "Current bid is within the 70% all-in acquisition target.", "BORDERLINE": "Bid is below market value but above the 70% all-in target.", "PASS": "Bid is too high relative to market value after auction costs."}[decision]
        return {"decision": decision, "reason": reason, "max_bid": max_bid, "all_in": cost, "market_value": float(value), "confidence": confidence}

    max_buy = round(float(value) * 0.70, 2)
    decision = "BUY" if float(price) <= max_buy else "BORDERLINE" if float(price) <= float(value) * 0.85 else "PASS"
    return {"decision": decision, "reason": "Asking price compared with the 70% acquisition target.", "max_bid": max_buy, "all_in": {"all_in_cost": float(price), "complete": True}, "market_value": float(value), "confidence": confidence}
