"""Official eBay Browse API last-chance scanner for CRTC."""
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List

import requests

from comps_adapters import _get_ebay_access_token
from holy_grail_pipeline import rank_opportunities
from listing_normalizer import normalize_listing

SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
DEFAULT_QUERIES = (
    "14k gold ring", "14k gold jewelry", "18k gold ring", "18k gold jewelry",
    "24k gold", "gold scrap jewelry", "white gold ring", "vintage gold jewelry",
    "sterling silver ring", "vintage watch", "old receiver", "vintage camera",
    "vintage tools", "old guitar", "untested electronics", "misc electronics",
    "estate jewelry", "jewelry lot", "box of tools", "vintage computer",
)


def _parse_end(value: object):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _fetch(query: str, limit: int) -> List[Dict[str, object]]:
    token = _get_ebay_access_token()
    response = requests.get(
        SEARCH_URL,
        headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"},
        params={"q": query, "limit": min(max(int(limit), 1), 200), "sort": "endingSoonest", "filter": "price:[0..150]"},
        timeout=25,
    )
    response.raise_for_status()
    return response.json().get("itemSummaries", []) or []


def scan_ebay_last_chance(
    queries: Iterable[str] = DEFAULT_QUERIES,
    *,
    limit_per_query: int = 50,
    primary_ceiling: float = 100.0,
    absolute_ceiling: float = 150.0,
    hours: int = 24,
    min_score: float = 25.0,
) -> Dict[str, object]:
    """Broad eBay last-chance hunt with automatic $100 -> $125 -> $150 fallback."""
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=max(1, int(hours)))
    records: Dict[str, Dict[str, object]] = {}
    errors: List[str] = []
    query_list = [str(q).strip() for q in queries if str(q).strip()]

    for query in query_list:
        try:
            for item in _fetch(query, limit_per_query):
                item_id = str(item.get("itemId") or item.get("legacyItemId") or item.get("itemWebUrl") or "")
                if not item_id:
                    continue
                try:
                    price_value = float((item.get("price") or {}).get("value", 0) or 0)
                except (TypeError, ValueError):
                    continue
                if price_value <= 0 or price_value > absolute_ceiling:
                    continue
                end_dt = _parse_end(item.get("itemEndDate"))
                if end_dt is None or end_dt <= now or end_dt > cutoff:
                    continue
                records[item_id] = {
                    "source": "eBay", "source_listing_id": item_id,
                    "url": item.get("itemWebUrl", ""), "title": item.get("title", ""),
                    "description": item.get("shortDescription", "") or "",
                    "price": price_value, "auction_end": end_dt.isoformat(),
                    "condition": item.get("condition", ""),
                    "location": ((item.get("itemLocation") or {}).get("city") or ""),
                }
        except Exception as exc:
            errors.append(f"{query}: {exc}")

    ranked = rank_opportunities([normalize_listing(item) for item in records.values()], min_score=min_score)

    def under(candidate, ceiling):
        price = candidate.listing.get("price")
        return price is not None and float(price) <= ceiling

    primary = [c for c in ranked if under(c, primary_ceiling)]
    fallback_125 = [c for c in ranked if under(c, 125) and not under(c, primary_ceiling)]
    fallback_150 = [c for c in ranked if under(c, absolute_ceiling) and not under(c, 125)]
    if primary:
        selected, selected_ceiling = primary, primary_ceiling
    elif fallback_125:
        selected, selected_ceiling = fallback_125, 125.0
    else:
        selected, selected_ceiling = fallback_150, absolute_ceiling

    return {
        "source": "eBay", "queries": query_list, "fetched": len(records),
        "opportunities": selected, "primary_count": len(primary),
        "fallback_125_count": len(fallback_125), "fallback_150_count": len(fallback_150),
        "selected_ceiling": selected_ceiling, "hours": hours,
        "errors": errors, "scanned_at": now.isoformat(),
    }
