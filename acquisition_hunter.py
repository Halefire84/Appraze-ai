"""CRTC acquisition intelligence for liquidation, surplus, and electronics lots.

This module is intentionally source-agnostic. It does not scrape or bypass
auction controls; it evaluates listings supplied by an approved adapter,
public/permitted feed, export, or user-provided input.
"""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class AcquisitionProfile:
    key: str
    name: str
    categories: tuple
    min_cpu_generation: Optional[int] = None
    preferred_condition: tuple = ()
    risk_penalties: Dict[str, float] = None

    def __post_init__(self):
        if self.risk_penalties is None:
            object.__setattr__(self, "risk_penalties", {})


PROFILES = {
    "modern_computers": AcquisitionProfile(
        "modern_computers", "Modern Computers & Laptops",
        ("laptop", "desktop", "computer", "workstation"), min_cpu_generation=8,
        preferred_condition=("tested", "working", "refurbished"),
        risk_penalties={"locked": 35, "unknown_condition": 18, "missing_charger": 5},
    ),
    "phones_tablets": AcquisitionProfile(
        "phones_tablets", "Phones & Tablets",
        ("phone", "smartphone", "iphone", "ipad", "tablet"),
        preferred_condition=("tested", "working"),
        risk_penalties={"activation_lock": 50, "mdm_lock": 45, "unknown_condition": 20},
    ),
    "amazon_returns": AcquisitionProfile(
        "amazon_returns", "Amazon / Retail Returns",
        ("customer return", "returns", "overstock", "warehouse damaged", "liquidation"),
        preferred_condition=("manifested", "tested", "new"),
        risk_penalties={"unmanifested": 30, "unknown_condition": 20, "freight": 15},
    ),
    "government_surplus": AcquisitionProfile(
        "government_surplus", "Government Surplus",
        ("government surplus", "municipal", "school", "county", "state", "federal"),
        preferred_condition=("tested", "working"),
        risk_penalties={"unknown_condition": 18, "pickup_only": 10, "freight": 15},
    ),
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def estimate_max_bid(listing: Dict[str, Any], *, target_margin: float = 0.30) -> Dict[str, float]:
    """Calculate a conservative maximum acquisition bid from supplied estimates.

    expected_resale is the expected gross resale value of recoverable inventory.
    recovery_rate accounts for dead/repair/salvage units. Costs include fees,
    freight, tax, and expected repairs/accessories.
    """
    expected_resale = _number(listing.get("expected_resale"))
    recovery_rate = max(0.0, min(1.0, _number(listing.get("recovery_rate"), 0.75)))
    fixed_costs = sum(_number(listing.get(key)) for key in (
        "buyer_premium", "tax", "freight", "repair_cost", "accessory_cost", "other_costs"
    ))
    effective_resale = expected_resale * recovery_rate
    max_total_acquisition = max(0.0, effective_resale * (1.0 - target_margin) - fixed_costs)
    current_bid = _number(listing.get("current_bid"))
    return {
        "effective_resale": round(effective_resale, 2),
        "fixed_costs": round(fixed_costs, 2),
        "max_total_acquisition": round(max_total_acquisition, 2),
        "headroom": round(max_total_acquisition - current_bid, 2),
    }


def score_acquisition(listing: Dict[str, Any], profile_key: str = "modern_computers") -> Dict[str, Any]:
    """Score an acquisition candidate without pretending unknowns are known."""
    profile = PROFILES.get(profile_key, PROFILES["modern_computers"])
    text = " ".join(str(listing.get(k, "")) for k in ("title", "description", "category")).lower()
    score = 50.0
    signals: List[str] = []

    if any(term in text for term in profile.categories):
        score += 10
        signals.append("profile_match")
    if listing.get("manifested") is True:
        score += 8
        signals.append("manifested")
    if str(listing.get("condition", "")).lower() in profile.preferred_condition:
        score += 8
        signals.append("known_condition")
    if listing.get("tested") is True:
        score += 10
        signals.append("tested")

    for key, penalty in profile.risk_penalties.items():
        if listing.get(key) is True:
            score -= penalty
            signals.append(key)

    cpu_generation = listing.get("cpu_generation")
    if profile.min_cpu_generation and cpu_generation is not None:
        try:
            if int(cpu_generation) >= profile.min_cpu_generation:
                score += 8
                signals.append("modern_cpu")
            else:
                score -= 20
                signals.append("obsolete_cpu")
        except (TypeError, ValueError):
            signals.append("cpu_generation_unknown")

    economics = estimate_max_bid(listing)
    if economics["headroom"] > 0:
        score += 10
        signals.append("bid_headroom")
    else:
        score -= 20
        signals.append("bid_too_high")

    return {
        "score": round(max(0.0, min(100.0, score)), 1),
        "signals": signals,
        "economics": economics,
        "profile": profile.key,
        "decision": "BUY_CANDIDATE" if score >= 70 and economics["headroom"] >= 0 else "INVESTIGATE" if score >= 50 else "PASS",
    }


def rank_acquisitions(listings: Iterable[Dict[str, Any]], profile_key: str) -> List[Dict[str, Any]]:
    ranked = []
    for listing in listings:
        result = score_acquisition(listing, profile_key)
        ranked.append({**listing, "crtc": result})
    return sorted(ranked, key=lambda item: item["crtc"]["score"], reverse=True)
