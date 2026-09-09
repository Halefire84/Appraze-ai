"""eBay Browse search-by-image adapter for CRTC.

Uses eBay's documented Browse API searchByImage endpoint. It requires the
same application credentials as the normal Browse adapter and does not use
an eBay username/password, cookies, CAPTCHA solving, or browser bypassing.
"""

import base64
from typing import List

import requests

from comps import ACTIVE, Comp
from comps_adapters import _get_ebay_access_token


SEARCH_BY_IMAGE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search_by_image"


def search_ebay_by_image(image_bytes: bytes, mime_type: str = "image/jpeg", limit: int = 25) -> List[Comp]:
    if not image_bytes:
        return []
    token = _get_ebay_access_token()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload = {"image": encoded}
    resp = requests.post(
        SEARCH_BY_IMAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        },
        json=payload,
        params={"limit": min(max(int(limit), 1), 50)},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    results: List[Comp] = []
    for item in data.get("itemSummaries", []) or []:
        price_info = item.get("price") or {}
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
            condition=item.get("condition", ""),
            shipping=0.0,
            listing_date=None,
            title=item.get("title", ""),
            url=item.get("itemWebUrl", ""),
        ))
    return results
