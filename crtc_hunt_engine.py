"""CRTC unified hunting engine.

Turns a listing supplied by an approved adapter, permitted feed, export, or
user-provided input into one comparable opportunity record. The engine is
source-agnostic: source terms and access controls are handled by adapters.
"""
from typing import Any, Dict

from acquisition_hunter import score_acquisition
from holy_grail_pipeline import score_listing


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def analyze_listing(listing: Dict[str, Any], profile_key: str = "modern_computers") -> Dict[str, Any]:
    """Run both the Holy Grail information-failure brain and acquisition brain."""
    normalized = dict(listing)
    normalized["price"] = _number(normalized.get("price", normalized.get("current_bid")))
    normalized["current_bid"] = _number(normalized.get("current_bid", normalized.get("price")))

    holy = score_listing(normalized)
    acquisition = score_acquisition(normalized, profile_key)
    signal_dicts = holy.signals

    combined = round((float(holy.score) * 0.55) + (float(acquisition["score"]) * 0.45), 1)
    if combined >= 85:
        tier = "HOLY GRAIL"
    elif combined >= 70:
        tier = "STRONG BUY LEAD"
    elif combined >= 50:
        tier = "INVESTIGATE"
    else:
        tier = "WATCH / PASS"

    return {
        "listing": normalized,
        "holy_grail": {
            "score": holy.score,
            "tier": holy.tier,
            "signals": [s["code"] for s in signal_dicts],
            "reasons": [s["message"] for s in signal_dicts],
        },
        "acquisition": acquisition,
        "combined_score": combined,
        "tier": tier,
        "decision": acquisition["decision"],
    }
