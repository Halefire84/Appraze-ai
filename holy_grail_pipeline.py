"""CRTC Holy Grail Finder pipeline.

Pure orchestration: normalized listings are scored by Opportunity Radar and
optionally enriched with existing market-comps evidence. Network acquisition
belongs to source adapters; this module never scrapes or bypasses controls.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
    listing = normalize_listing(raw_listing)
    result = analyze_listing(listing)
    score = float(result.score)
    return OpportunityCandidate(
        listing=listing,
        score=score,
        review=bool(result.review),
        tier=_tier(score),
        signals=[{"kind": s.kind, "message": s.message, "weight": s.weight} for s in result.signals],
    )


def rank_opportunities(raw_listings: List[Dict[str, Any]], min_score: float = 25.0) -> List[OpportunityCandidate]:
    candidates = [score_listing(item) for item in raw_listings]
    return sorted((c for c in candidates if c.score >= min_score), key=lambda c: c.score, reverse=True)
