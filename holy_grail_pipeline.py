"""CRTC Holy Grail Finder pipeline.

Pure orchestration: normalized listings are scored by Opportunity Radar and
optionally enriched with existing market-comps evidence. Network acquisition
belongs to source adapters; this module never scrapes or bypasses controls.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from listing_normalizer import normalize_listing
from opportunity_result import build_opportunity_result


@dataclass
class OpportunityCandidate:
    listing: Dict[str, Any]
    score: float
    review: bool
    tier: str
    signals: List[Dict[str, Any]] = field(default_factory=list)
    verdict: Optional[str] = None
    max_buy_price: Optional[float] = None


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
    # Keep the historical alias used by exports/tests while `url` remains the
    # canonical normalized field for new code.
    listing["source_url"] = listing.get("url", "")
    opportunity = build_opportunity_result(listing)
    result = opportunity.radar
    score = float(result.opportunity_score)
    return OpportunityCandidate(
        listing=listing,
        score=score,
        review=bool(result.review_required),
        tier=_tier(score),
        signals=[
            {
                "code": signal.code,
                "severity": signal.severity,
                "score": signal.score,
                "message": signal.message,
            }
            for signal in result.signals
        ],
        verdict=opportunity.verdict,
        max_buy_price=opportunity.max_buy_price,
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


def opportunity_summary(candidate: OpportunityCandidate) -> Dict[str, Any]:
    """Return a UI/API-safe summary for cards, exports, and future dashboards."""
    return {
        "source": candidate.listing.get("source"),
        "title": candidate.listing.get("title"),
        "url": candidate.listing.get("source_url") or candidate.listing.get("url"),
        "price": candidate.listing.get("price"),
        "estimated_value": candidate.listing.get("estimated_value"),
        "score": candidate.score,
        "tier": candidate.tier,
        "review_required": candidate.review,
        "signals": candidate.signals,
        "verdict": candidate.verdict,
        "max_buy_price": candidate.max_buy_price,
    }
