"""Permitted browser/search entry points for CRTC opportunity research.

These URLs are launch points, not scraping bypasses. They let CRTC hand a
normal search to a source's own public search page when no API adapter exists.
"""

from urllib.parse import quote_plus


SOURCE_SEARCH_TEMPLATES = {
    "ctbids": "https://www.ctbids.com/estate-sales",
    "shopgoodwill": "https://shopgoodwill.com/",
    "hibid": "https://hibid.com/",
    "proxibid": "https://www.proxibid.com/",
    "liveauctioneers": "https://www.liveauctioneers.com/",
    "invaluable": "https://www.invaluable.com/",
    "auctionzip": "https://www.auctionzip.com/",
    "ebth": "https://www.ebth.com/",
    "maxsold": "https://maxsold.com/",
    "gsa": "https://www.gsaauctions.gov/",
    "govdeals": "https://www.govdeals.com/",
    "publicsurplus": "https://www.publicsurplus.com/",
    "govplanet": "https://www.govplanet.com/",
    "propertyroom": "https://www.propertyroom.com/",
    "municibid": "https://municibid.com/",
    "purplewave": "https://www.purplewave.com/",
}


def public_search_url(key: str, query: str = "") -> str:
    """Return a source's public search/home URL without attempting access control bypass."""
    base = SOURCE_SEARCH_TEMPLATES.get(key, "")
    if not base:
        return ""
    if not query.strip():
        return base
    # A generic site homepage is safer than guessing an undocumented search
    # endpoint. The user can use the source's own search UI.
    return f"{base.rstrip('/')}/?q={quote_plus(query.strip())}"
