"""CRTC deal workspace helpers — delegates to the canonical decision engine.

Previously reimplemented its own 70%-rule BUY/BORDERLINE/PASS logic
independently of auction_radar.py and crtc_opportunity.py's own separate
copies of the same rule -- three modules that could (and did) disagree
about what counted as a BUY. All three now call decision_policy.evaluate_deal()
/ build_deal_workspace_record(), the one canonical decision authority.
"""
from typing import Any, Dict, Optional

from decision_policy import build_deal_workspace_record
from telemetry import log_event


def build_deal_workspace(
    listing: Dict[str, Any],
    market_value: Optional[float] = None,
    confidence: str = "UNKNOWN",
) -> Dict[str, Any]:
    """Build one transparent, UI-ready deal record via the canonical engine.

    Every caller goes through this one function, so this is the single
    place a financial-decision event gets logged for operator visibility --
    matching telemetry.py's own documented usage example. Logging never
    blocks or fails this call: log_event() already catches everything and
    returns silently on any error."""
    record = build_deal_workspace_record(listing, market_value=market_value, confidence=confidence)
    log_event(
        "INFO",
        "decision",
        "deal_workspace",
        "evaluated deal",
        {
            "decision": record.get("decision"),
            "roi_tier": record.get("roi_tier"),
            "projected_roi_pct": record.get("projected_roi_pct"),
            "all_in_cost": record.get("all_in_cost"),
            "market_value": record.get("market_value"),
            "item": listing.get("title") or listing.get("item_name"),
            "source": listing.get("source"),
        },
    )
    return record
