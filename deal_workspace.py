"""CRTC deal workspace helpers — delegates to the canonical decision engine.

Previously reimplemented its own 70%-rule BUY/BORDERLINE/PASS logic
independently of auction_radar.py and crtc_opportunity.py's own separate
copies of the same rule -- three modules that could (and did) disagree
about what counted as a BUY. All three now call decision_policy.evaluate_deal()
/ build_deal_workspace_record(), the one canonical decision authority.
"""
from typing import Any, Dict, Optional

from decision_policy import build_deal_workspace_record


def build_deal_workspace(
    listing: Dict[str, Any],
    market_value: Optional[float] = None,
    confidence: str = "UNKNOWN",
) -> Dict[str, Any]:
    """Build one transparent, UI-ready deal record via the canonical engine."""
    return build_deal_workspace_record(listing, market_value=market_value, confidence=confidence)
