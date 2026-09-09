"""CRTC bridge from canonical flip records to cross-list listing drafts.

The bridge is intentionally marketplace-neutral: it prepares one master listing
payload. Marketplace adapters remain responsible for approved API publishing.
"""
from typing import Any, Dict


def build_master_listing(flip: Dict[str, Any]) -> Dict[str, Any]:
    """Create a cross-list-ready master listing from a tracked flip."""
    status = str(flip.get("status") or "").upper()
    if status not in {"PURCHASED", "LISTED"}:
        raise ValueError("Only PURCHASED or LISTED flips can enter listing workflow")
    title = str(flip.get("item_name") or "Untitled item").strip()
    if not title:
        raise ValueError("A listing title is required")
    list_price = float(flip.get("list_price") or 0)
    if list_price <= 0:
        raise ValueError("A positive list price is required before listing")
    return {
        "sku": str(flip.get("sku") or flip.get("source_listing_id") or "CRTC-ITEM"),
        "title": title,
        "description": str(flip.get("description") or flip.get("notes") or ""),
        "category": str(flip.get("category") or ""),
        "price": round(list_price, 2),
        "cost": round(float(flip.get("cost_basis") or 0), 2),
        "quantity": int(flip.get("quantity") or 1),
        "condition": str(flip.get("condition") or "Used"),
        "photos": list(flip.get("photos") or []),
        "source": str(flip.get("source") or ""),
        "source_listing_id": str(flip.get("source_listing_id") or ""),
        "source_url": str(flip.get("source_url") or ""),
        "status": "MASTER_READY",
    }
