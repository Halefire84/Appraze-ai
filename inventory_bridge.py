"""CRTC bridge from an approved BUY decision into an inventory-ready record.

This module does not create a second inventory database. It produces a normalized
payload that an existing inventory workflow can consume when that workflow is
connected.
"""
from typing import Any, Dict


def build_inventory_intake(listing: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    """Create an inventory-ready intake payload only for an explicit BUY decision."""
    if str(decision.get("decision", "")).upper() != "BUY":
        raise ValueError("Only an explicit BUY decision can be converted to inventory intake")

    cost = decision.get("all_in") or {}
    acquisition_cost = cost.get("all_in_cost")
    if acquisition_cost is None:
        acquisition_cost = listing.get("price")

    return {
        "item_name": str(listing.get("title") or "Untitled item"),
        "source": str(listing.get("source") or ""),
        "source_listing_id": str(listing.get("source_listing_id") or ""),
        "source_url": str(listing.get("url") or ""),
        "cost_basis": round(float(acquisition_cost), 2) if acquisition_cost is not None else None,
        "market_value": decision.get("market_value"),
        "radar_score": listing.get("radar_score"),
        "decision": "BUY",
        "status": "PURCHASE_PENDING",
        "notes": "Created from a CRTC BUY decision; verify physical item and final receipt before marking acquired.",
    }
