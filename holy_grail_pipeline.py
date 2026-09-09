"""CRTC Holy Grail Finder pipeline.

Pure orchestration: normalized listings are scored by Opportunity Radar and
optionally enriched with existing market-comps evidence. Network acquisition
belongs to source adapters; this module never scrapes or bypasses controls.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List

from crtc_opportunity import build_opportunity
from listing_normalizer import normalize_listing
from opportunity_radar import analyze_listing


@dataclass
class OpportunityCandidate:
    listing: Dict[str, Any]
    score: float
    review: bool
    tier: str
    signals: List[Dict[str, Any]] = field(default_factory=list)


def _tier(score: float) -> str:
    if score >= 95:
        return "HOLY GRAIL"
    if score >= 85:
        return "EXTREME OPPORTUNITY"
    if score >= 70:
        return "STRONG BUY LEAD"
    if score >= 50:
        return "INVESTIGATE"
    return "WATCH"


def score_listing(raw_listing: Dict[str, Any]) -> OpportunityCandidate:
    """Normalize and score a raw listing using the canonical Radar contract."""
    listing = normalize_listing(raw_listing)
    listing["source_url"] = listing.get("url", "")
    result = analyze_listing(listing)
    score = float(result.opportunity_score)
    return OpportunityCandidate(
        listing=listing,
        score=score,
        review=bool(result.review_required),
        tier=_tier(score),
        signals=[
            {"code": signal.code, "severity": signal.severity,
             "score": signal.score, "message": signal.message}
            for signal in result.signals
        ],
    )


def rank_opportunities(
    raw_listings: List[Dict[str, Any]], min_score: float = 25.0
) -> List[OpportunityCandidate]:
    """Return qualifying opportunities in descending Radar score order."""
    candidates = [score_listing(item) for item in raw_listings]
    return sorted(
        (candidate for candidate in candidates if candidate.score >= min_score),
        key=lambda candidate: candidate.score,
        reverse=True,
    )


def opportunity_result(candidate: OpportunityCandidate, **kwargs: Any) -> Dict[str, Any]:
    """Return the dedicated CRTC result contract for UI/API consumers."""
    result = build_opportunity(candidate, **kwargs).to_dict()
    result["signals"] = candidate.signals
    return result


def opportunity_summary(candidate: OpportunityCandidate) -> Dict[str, Any]:
    """Backward-compatible summary for cards, exports, and dashboards."""
    result = opportunity_result(candidate)
    result["price"] = result["asking_price"]
    result["estimated_value"] = result["market_value"]
    result["score"] = result["radar_score"]
    result["tier"] = result["radar_tier"]
    result["review_required"] = candidate.review
    return result
