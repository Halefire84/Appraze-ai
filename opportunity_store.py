"""Small in-session CRTC opportunity store used by the Radar UI."""
from typing import Any, Dict, List


def save_opportunity(store: List[Dict[str, Any]], opportunity: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Save one opportunity by stable source/listing identity, newest version wins."""
    key = (str(opportunity.get("source", "")), str(opportunity.get("source_listing_id", "")), str(opportunity.get("url", "")))
    updated = [item for item in store if (str(item.get("source", "")), str(item.get("source_listing_id", "")), str(item.get("url", ""))) != key]
    updated.append(dict(opportunity))
    return updated


def remove_opportunity(store: List[Dict[str, Any]], index: int) -> List[Dict[str, Any]]:
    return [item for i, item in enumerate(store) if i != index]
