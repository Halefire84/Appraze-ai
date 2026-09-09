"""CRTC multi-auction Radar orchestration.

Acquisition stays outside this module. Callers provide records obtained from
an allowed public catalog, permitted feed/export, or user-provided file.
"""
from typing import Any, Dict, Iterable, List

from auction_source_adapters import build_catalog_adapter
from holy_grail_pipeline import OpportunityCandidate, rank_opportunities


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
