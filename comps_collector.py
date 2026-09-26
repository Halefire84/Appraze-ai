"""
comps_collector.py — Appraze comps collector for the mobile apps.

The Android Analyze screen sends "what is it?" text; this collects market
comps and returns a suggested resale value with an explainable confidence
rating, so the user doesn't have to guess the resale number.

Reuses the existing, tested comps code UNCHANGED:
  * comps_adapters.EbayMarketplaceInsightsAdapter — eBay SOLD prices, only
    when eBay has approved this app for the Limited Release API;
  * comps_adapters.EbayBrowseAdapter — eBay ACTIVE listings (asking
    prices), the fallback, rated lower confidence by comps.py;
  * comps.summarize_comps — median value + confidence rules.

The only glue here: comps_adapters reads EBAY_CLIENT_ID/EBAY_CLIENT_SECRET
from Streamlit secrets, which don't exist in this FastAPI service, so the
credential lookup is pointed at environment variables at runtime
(_use_env_ebay_credentials). eBay keys stay on the server — never in the app.

Marketplace data is UNTRUSTED: listing titles are returned as plain text
for display only and are never interpreted as instructions.

ENVIRONMENT
    EBAY_CLIENT_ID / EBAY_CLIENT_SECRET   eBay developer app keys (production).
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

import comps
import comps_adapters
from pos_connect import RateLimiter

logger = logging.getLogger("comps_collector")

MIN_QUERY_LEN = 2
MAX_QUERY_LEN = 100
MAX_COMPS_RETURNED = 10
FETCH_LIMIT = 30
CACHE_TTL_S = 3600.0
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

# (limit, window seconds). eBay's Browse quota is shared by every user, so
# lookups are rate-limited per IP and capped globally per day, and repeat
# queries are served from a 1-hour cache.
LIMIT_PER_IP_MINUTE = (10, 60.0)
LIMIT_PER_IP_DAY = (200, 86400.0)
LIMIT_GLOBAL_DAY = (4000, 86400.0)


class CompsError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _env_ebay_credentials() -> tuple:
    client_id = os.environ.get("EBAY_CLIENT_ID", "").strip()
    client_secret = os.environ.get("EBAY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise comps_adapters.EbayAuthError("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET are not set on the server.")
    return client_id, client_secret


def _use_env_ebay_credentials() -> None:
    comps_adapters._ebay_client_credentials = _env_ebay_credentials


def validate_query(value: Any) -> str:
    if not isinstance(value, str):
        raise CompsError(400, "Describe the item (brand, model, size).")
    q = " ".join(_CONTROL_CHARS_RE.sub(" ", value).split())
    if len(q) < MIN_QUERY_LEN:
        raise CompsError(400, "Describe the item (brand, model, size).")
    if len(q) > MAX_QUERY_LEN:
        raise CompsError(400, f"Keep the description under {MAX_QUERY_LEN} characters.")
    return q


def _comp_json(c: comps.Comp) -> Dict[str, Any]:
    return {
        "title": (c.title or "")[:200],
        "price": round(c.price, 2),
        "shipping": round(c.shipping or 0.0, 2),
        "listing_type": c.listing_type,
        "condition": c.condition or "",
        "listing_date": c.listing_date,
        "url": c.url if (c.url or "").startswith("https://") else "",
        "source": c.source,
    }


class CompsCollector:
    def __init__(self, sold_adapter=None, active_adapter=None, clock=time.time):
        self.sold_adapter = sold_adapter or comps_adapters.EbayMarketplaceInsightsAdapter()
        self.active_adapter = active_adapter or comps_adapters.EbayBrowseAdapter()
        self._clock = clock
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._sold_approved: Optional[bool] = None

    def _fetch(self, query: str) -> Tuple[List[comps.Comp], str]:
        """Sold comps when eBay has approved Marketplace Insights, else active listings."""
        if self._sold_approved is not False:
            try:
                sold = self.sold_adapter.fetch_comps(query, limit=FETCH_LIMIT)
                self._sold_approved = True
                if sold:
                    return sold, "ebay_sold"
            except comps_adapters.EbayInsightsNotApprovedError:
                self._sold_approved = False
            except comps_adapters.EbayAuthError:
                raise
            except requests.RequestException as e:
                logger.warning("Sold-comps lookup failed, falling back to active: %s", type(e).__name__)
        return self.active_adapter.fetch_comps(query, limit=FETCH_LIMIT), "ebay_active"

    def collect(self, raw_query: Any) -> Dict[str, Any]:
        query = validate_query(raw_query)
        key = query.lower()
        now = self._clock()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < CACHE_TTL_S:
                return {**hit[1], "cached": True}
        try:
            found, basis = self._fetch(query)
        except comps_adapters.EbayAuthError:
            raise CompsError(503, "Comps lookup isn't set up on the server yet.")
        except requests.RequestException as e:
            logger.warning("Comps lookup failed for query: %s", type(e).__name__)
            raise CompsError(502, "Couldn't reach eBay. Try again.")
        summary = comps.summarize_comps(found)
        collected_at = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()
        if summary is None:
            result = {
                "query": query, "found": False, "basis": basis,
                "message": "No comparable listings found. Try fewer or different words.",
                "collected_at": collected_at, "comps": [],
            }
        else:
            ranked = sorted(found, key=lambda c: (c.listing_type != comps.SOLD, c.price))
            result = {
                "query": query,
                "found": True,
                "basis": basis,
                "suggested_value": round(summary.suggested_value, 2),
                "confidence": summary.confidence,
                "confidence_reason": summary.confidence_reason,
                "count": summary.count,
                "sold_count": summary.sold_count,
                "active_count": summary.active_count,
                "low": round(summary.low, 2),
                "high": round(summary.high, 2),
                "median": round(summary.median, 2),
                "collected_at": collected_at,
                "comps": [_comp_json(c) for c in ranked[:MAX_COMPS_RETURNED]],
            }
        with self._lock:
            self._cache[key] = (now, result)
        logger.info("Comps collected: basis=%s count=%s", basis, len(found))
        return {**result, "cached": False}


_limiter = RateLimiter()
_collector: Optional[CompsCollector] = None
_collector_lock = threading.Lock()


def get_collector() -> CompsCollector:
    global _collector
    with _collector_lock:
        if _collector is None:
            _use_env_ebay_credentials()
            _collector = CompsCollector()
        return _collector


def set_collector(collector: Optional[CompsCollector], limiter: Optional[RateLimiter] = None) -> None:
    """Test hook."""
    global _collector, _limiter
    with _collector_lock:
        _collector = collector
    if limiter is not None:
        _limiter = limiter


router = APIRouter()


@router.post("/comps/search")
async def comps_search(request: Request):
    ip = request.client.host if request.client else "unknown"
    try:
        for bucket, key, (limit, window) in (("comps_ip_min", ip, LIMIT_PER_IP_MINUTE),
                                             ("comps_ip_day", ip, LIMIT_PER_IP_DAY),
                                             ("comps_global", "all", LIMIT_GLOBAL_DAY)):
            if not _limiter.allow(bucket, key, limit, window):
                raise CompsError(429, "Too many lookups. Wait a minute and try again.")
        try:
            body = await request.json()
        except Exception:
            raise CompsError(400, "Request body must be JSON.")
        if not isinstance(body, dict):
            raise CompsError(400, "Request body must be a JSON object.")
        result = await run_in_threadpool(get_collector().collect, body.get("query"))
        return {"ok": True, **result}
    except CompsError as e:
        return JSONResponse(status_code=e.status, content={"ok": False, "error": e.message})
