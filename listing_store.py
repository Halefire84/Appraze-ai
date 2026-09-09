"""CRTC persistent listing lifecycle helpers.

Listings are stored separately from flip inventory so one master item can
have multiple marketplace drafts. Publishing remains an integration concern.
"""
from typing import Any, Dict, Iterable, List

LISTING_STATUSES = ("DRAFT", "READY_TO_PUBLISH", "ACTIVE", "SOLD", "DEACTIVATED")

ALLOWED_TRANSITIONS = {
    "DRAFT": {"DRAFT", "READY_TO_PUBLISH", "DEACTIVATED"},
    "READY_TO_PUBLISH": {"READY_TO_PUBLISH", "ACTIVE", "DEACTIVATED"},
    "ACTIVE": {"ACTIVE", "SOLD", "DEACTIVATED"},
    "SOLD": {"SOLD"},
    "DEACTIVATED": {"DEACTIVATED"},
}


def listing_key(listing: Dict[str, Any]) -> str:
    return "|".join(str(listing.get(k, "")) for k in ("sku", "marketplace"))


def upsert_listing(listings: Iterable[Dict[str, Any]], listing: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Insert or replace one marketplace listing by stable SKU+marketplace."""
    item = dict(listing)
    item["status"] = str(item.get("status", "DRAFT")).upper()
    if item["status"] not in LISTING_STATUSES:
        raise ValueError(f"Unsupported listing status: {item['status']}")
    key = listing_key(item)
    result = [dict(row) for row in listings if listing_key(row) != key]
    result.append(item)
    return result


def transition_listing(listing: Dict[str, Any], status: str, *, external_id: str = None) -> Dict[str, Any]:
    """Return a validated marketplace listing transition without mutating input."""
    current_status = str(listing.get("status", "DRAFT")).upper()
    next_status = str(status).upper()
    if current_status not in LISTING_STATUSES:
        raise ValueError(f"Unsupported current listing status: {current_status}")
    if next_status not in LISTING_STATUSES:
        raise ValueError(f"Unsupported listing status: {next_status}")
    if next_status not in ALLOWED_TRANSITIONS[current_status]:
        raise ValueError(f"Invalid listing transition: {current_status} -> {next_status}")
    item = dict(listing)
    item["status"] = next_status
    if external_id is not None:
        item["external_id"] = external_id
    return item


def mark_item_sold(listings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mark every non-sold marketplace listing for deactivation after a sale."""
    result = []
    for row in listings:
        item = dict(row)
        if item.get("status") not in {"SOLD", "DEACTIVATED"}:
            item["status"] = "SOLD"
        result.append(item)
    return result
