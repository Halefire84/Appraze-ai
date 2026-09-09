"""CRTC multi-auction Radar and valuation orchestration.

Acquisition stays outside this module. Callers provide records obtained from
an allowed public catalog, permitted feed/export, or user-provided file.
Market comps are also caller-supplied so this layer never scrapes or invents
auction data.
"""
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from auction_source_adapters import build_catalog_adapter
from holy_grail_pipeline import OpportunityCandidate, rank_opportunities
from valuation_bridge import value_candidate


def rank_auction_catalog(
    source_key: str,
    records: Iterable[Dict[str, Any]],
    *,
    min_score: float = 25.0,
) -> List[OpportunityCandidate]:
    """Normalize and rank an auction catalog with the canonical CRTC Radar."""
    adapter = build_catalog_adapter(source_key)
    normalized = adapter.normalize_records(records)
    return rank_opportunities(normalized, min_score=min_score)


def enrich_auction_opportunities(
    opportunities: Sequence[OpportunityCandidate],
    comps_by_index: Mapping[int, Sequence[Any]],
) -> Dict[int, Dict[str, Any]]:
    """Apply the canonical valuation/decision contract to auction leads.

    Comps must be supplied by an allowed adapter, CSV import, or manual entry.
    Missing comps deliberately produce REVIEW; active-only comps retain the
    existing low-confidence behavior in ``valuation_bridge``.
    """
    evidence: Dict[int, Dict[str, Any]] = {}
    for index, candidate in enumerate(opportunities):
        comps = list(comps_by_index.get(index, ()))
        result = value_candidate(candidate, comps)
        evidence[index] = {
            "result": result,
            "count": len(comps),
            "sold_count": sum(1 for comp in comps if getattr(comp, "listing_type", "") == "sold"),
            "active_count": sum(1 for comp in comps if getattr(comp, "listing_type", "") == "active"),
        }
    return evidence


def summarize_auction_scan(
    source_key: str,
    records: Iterable[Dict[str, Any]],
    *,
    min_score: float = 25.0,
) -> Dict[str, Any]:
    """Return source-aware scan metadata plus ranked CRTC opportunities."""
    adapter = build_catalog_adapter(source_key)
    normalized = adapter.normalize_records(records)
    opportunities = rank_opportunities(normalized, min_score=min_score)
    return {
        "source": adapter.source_name,
        "source_key": source_key,
        "fetched": len(normalized),
        "qualified": len(opportunities),
        "opportunities": opportunities,
    }
