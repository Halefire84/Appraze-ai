"""eBay Browse search-by-image adapter for CRTC.

Uses eBay's documented Browse API searchByImage endpoint. It requires the
same application credentials as the normal Browse adapter and does not use
an eBay username/password, cookies, CAPTCHA solving, or browser bypassing.

Hardened for production: a bad or hostile image upload, a slow/unreachable
eBay endpoint, or a malformed eBay response must never crash the caller's
listing/analysis flow -- each failure mode raises one specific, catchable
EbayImageSearchError (or the existing EbayAuthError from comps_adapters)
with a message safe to show a user, and per-item parsing problems are
skipped rather than aborting the whole batch.
"""

import json
from typing import List

import requests

from comps import ACTIVE, Comp
from comps_adapters import EbayAuthError, _get_ebay_access_token


SEARCH_BY_IMAGE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search_by_image"

# eBay's own upload guidance caps search-by-image payloads well under this;
# 10 MB is a generous ceiling that still protects the process from an
# accidental (or hostile) multi-hundred-MB upload being base64-encoded and
# held in memory.
MAX_IMAGE_BYTES = 10 * 1024 * 1024

_SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Minimal magic-byte signatures, just enough to catch "this isn't actually
# an image" (a text file, an HTML error page, a truncated upload) without
# adding an image-processing dependency for a single sanity check.
_MAGIC_BYTES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),  # followed by size + "WEBP"; checked separately below
}

MAX_REASONABLE_RESULTS = 50


class EbayImageSearchError(Exception):
    """Raised for any input validation or eBay response problem that isn't
    a plain missing-credentials case (that stays EbayAuthError, imported
    from comps_adapters, so callers already handling that exception don't
    need a second except clause for auth)."""
    pass


def _looks_like_declared_type(image_bytes: bytes, mime_type: str) -> bool:
    if mime_type == "image/webp":
        return image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP"
    signatures = _MAGIC_BYTES.get(mime_type)
    if not signatures:
        return True  # unknown-but-allowed type: nothing to check against
    return any(image_bytes.startswith(sig) for sig in signatures)


def _dedupe_comps(comps: List[Comp]) -> List[Comp]:
    seen = set()
    unique: List[Comp] = []
    for comp in comps:
        key = (comp.url, comp.title, comp.price)
        if key in seen:
            continue
        seen.add(key)
        unique.append(comp)
    return unique


def search_ebay_by_image(image_bytes: bytes, mime_type: str = "image/jpeg", limit: int = 25) -> List[Comp]:
    """Search eBay active listings by uploaded image.

    Raises:
        EbayImageSearchError: bad input, or eBay returned something this
            adapter can't safely use (bad token, HTTP error, malformed
            JSON).
        EbayAuthError: EBAY_CLIENT_ID/EBAY_CLIENT_SECRET aren't configured
            (raised by comps_adapters._get_ebay_access_token; not caught
            here so callers already handling that exception elsewhere in
            the app keep working unchanged).
    """
    if not image_bytes:
        return []  # nothing to search — not an error, just a no-op

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise EbayImageSearchError(
            f"Image is too large ({len(image_bytes)} bytes); maximum is {MAX_IMAGE_BYTES} bytes."
        )

    normalized_mime = (mime_type or "").lower().strip()
    if normalized_mime not in _SUPPORTED_MIME_TYPES:
        raise EbayImageSearchError(f"Unsupported image type: {mime_type!r}")

    if not _looks_like_declared_type(image_bytes, normalized_mime):
        raise EbayImageSearchError("Image data doesn't match its declared type; the file may be corrupt.")

    bounded_limit = min(max(int(limit), 1), MAX_REASONABLE_RESULTS)

    try:
        import base64
        encoded = base64.b64encode(image_bytes).decode("ascii")
    except Exception as e:
        raise EbayImageSearchError(f"Could not encode image for upload: {e}")

    token = _get_ebay_access_token()  # raises EbayAuthError if not configured

    try:
        resp = requests.post(
            SEARCH_BY_IMAGE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            json={"image": encoded},
            params={"limit": bounded_limit},
            timeout=30,
        )
    except requests.exceptions.Timeout:
        raise EbayImageSearchError("eBay image search timed out.")
    except requests.exceptions.ConnectionError:
        raise EbayImageSearchError("Could not connect to eBay's image search API.")
    except requests.exceptions.RequestException as e:
        raise EbayImageSearchError(f"eBay image search request failed: {e}")

    if resp.status_code == 401:
        raise EbayImageSearchError("eBay rejected the access token (expired or invalid); retry.")
    if 400 <= resp.status_code < 500:
        raise EbayImageSearchError(f"eBay rejected the image search request (HTTP {resp.status_code}).")
    if resp.status_code >= 500:
        raise EbayImageSearchError(f"eBay's image search API is unavailable (HTTP {resp.status_code}).")

    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        raise EbayImageSearchError("eBay returned a response that wasn't valid JSON.")

    if not isinstance(data, dict):
        raise EbayImageSearchError("eBay returned an unexpected response shape.")

    results: List[Comp] = []
    for item in (data.get("itemSummaries") or [])[: MAX_REASONABLE_RESULTS]:
        if not isinstance(item, dict):
            continue
        price_info = item.get("price") or {}
        if not isinstance(price_info, dict):
            continue
        try:
            price = float(price_info.get("value", 0) or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        results.append(Comp(
            price=price,
            source="eBay image search",
            listing_type=ACTIVE,
            condition=item.get("condition", "") or "",
            shipping=0.0,
            listing_date=None,
            title=item.get("title", "") or "",
            url=item.get("itemWebUrl", "") or "",
        ))

    return _dedupe_comps(results)[:bounded_limit]
