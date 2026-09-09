"""CRTC Radar -> market-evidence valuation bridge.

This module connects an already-normalized opportunity to the existing comps
engine. It does not introduce new valuation math and never converts active
asking prices into fake sold evidence.
"""
from typing import Any, Dict, Optional

from comps import Comp, summarize_comps
from crtc_opportunity import build_opportunity


def value_candidate(candidate: Any, comps: list[Comp]) -> Dict[str, Any]:
    """Enrich a Radar candidate with the canonical comps valuation.

    With no comps, the candidate remains REVIEW. With sold comps, the
    existing median-based estimate and confidence are used. Active-only comps
    remain low-confidence asking-price evidence.
    """
    summary = summarize_comps(comps)
    if summary is None:
        return build_opportunity(candidate).to_dict()

    return build_opportunity(
        candidate,
        market_value=summary.suggested_value,
        market_confidence=summary.confidence,
    ).to_dict()


def value_candidate_from_adapter(candidate: Any, adapter: Any, *, limit: int = 20) -> Dict[str, Any]:
    """Fetch comps through an existing adapter, then use the canonical bridge."""
    title = str(candidate.listing.get("title") or "").strip()
    if not title:
        return build_opportunity(candidate).to_dict()
    comps = adapter.fetch_comps(title, limit=limit)
    return value_candidate(candidate, comps)
