"""Legitimate acquisition-to-Radar bridges for CRTC.

Adapters return raw source records; this module converts them into the
canonical listing contract and scores them. No scraping, CAPTCHA solving,
or anti-bot bypass is performed here.
"""
from dataclasses import dataclass
from typing import Any, Dict, List

from comps_adapters import EbayAuthError, EbayBrowseAdapter
from holy_grail_pipeline import OpportunityCandidate, rank_opportunities
from listing_normalizer import normalize_listing


@dataclass(frozen=True)
class SourceScan:
    source: str
    query: str
    fetched: int
    opportunities: List[OpportunityCandidate]


def scan_ebay(query: str, *, limit: int = 25, min_score: float = 25.0) -> SourceScan:
    """Search eBay active listings through the official Browse API, then rank them.

    Active asking prices are not sold comps and are never presented as sold evidence.
    """
    if not query.strip():
        return SourceScan("eBay", query, 0, [])
    comps = EbayBrowseAdapter().fetch_comps(query, limit=limit)
    raw = [
        {
            "source": "eBay",
            "source_listing_id": "",
            "url": comp.url,
            "title": comp.title,
            "description": "",
            "price": comp.price,
            "condition": comp.condition,
            "shipping": comp.shipping,
        }
        for comp in comps
    ]
    normalized = [normalize_listing(item) for item in raw]
    return SourceScan("eBay", query, len(normalized), rank_opportunities(normalized, min_score=min_score))


def source_scan_status() -> Dict[str, Dict[str, Any]]:
    """Machine-readable source readiness for the UI and future adapters."""
    try:
        EbayBrowseAdapter().fetch_comps("test", limit=1)
        ebay = {"key": "ebay", "name": "eBay", "status": "ready", "evidence": "active"}
    except EbayAuthError:
        ebay = {"key": "ebay", "name": "eBay", "status": "needs_credentials", "evidence": "active"}
    except Exception as exc:
        ebay = {"key": "ebay", "name": "eBay", "status": "error", "evidence": "active", "error": str(exc)}
    return {"ebay": ebay}
