"""Feature flag and per-marketplace metadata for the cross-listing scaffold.

Every behavior in this package is gated by ``crosslisting_enabled()``
(env var ``APPRAZE_CROSSLIST``, default OFF) and labeled "Coming Soon".
No credentials are real anywhere in this repo.
"""

from __future__ import annotations

import os

# Environment variable that gates ALL cross-listing behavior. Default OFF.
CROSSLIST_ENV_VAR = "APPRAZE_CROSSLIST"

# eBay API constants for official Sell API wiring (sandbox-first).
# OAuth scopes required for the sandbox end-to-end publish proof:
# sell.inventory (write), sell.inventory.readonly (read), sell.account (policies).
EBAY_SANDBOX_BASE_URL = "https://api.sandbox.ebay.com"
EBAY_PRODUCTION_BASE_URL = "https://api.ebay.com"
EBAY_API_SCOPES = [
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",
    "https://api.ebay.com/oauth/api_scope/sell.account",
]

# Placeholder Etsy API constants for future official-API wiring — TODO only.
ETSY_API_BASE_URL = "https://openapi.etsy.com/v3"
ETSY_API_SCOPES = ["listings_w", "shops_w"]


def crosslisting_enabled() -> bool:
    """Return True only when the operator explicitly enables cross-listing."""
    return os.environ.get(CROSSLIST_ENV_VAR, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


# Display metadata per marketplace. ``mode`` is one of:
#   official_api      — scaffolded against the official public API (eBay, Etsy)
#   partner_api_stub  — stub only, awaiting partner-API approval (Depop)
#   assisted          — assisted publishing framework only; the human clicks
#                       the final publish button. NO private APIs, ever.
MARKETPLACES = {
    "ebay": {
        "label": "eBay",
        "mode": "official_api",
        "status": "coming_soon",
        "notes": "Official eBay Sell API (Inventory + Sell APIs). OAuth via ebay_sell.py (sandbox).",
    },
    "etsy": {
        "label": "Etsy",
        "mode": "official_api",
        "status": "coming_soon",
        "notes": "Official Etsy Open API v3 listings endpoints. API key + shop ID TODO.",
    },
    "depop": {
        "label": "Depop",
        "mode": "partner_api_stub",
        "status": "coming_soon",
        "notes": "Stub only — awaiting partner-API approval. No API calls of any kind.",
    },
    "poshmark": {
        "label": "Poshmark",
        "mode": "assisted",
        "status": "coming_soon",
        "notes": (
            "Assisted publishing only: complete listing payload plus a"
            " prefill / open-in-browser helper; the human clicks publish."
            " No private APIs, ever."
        ),
    },
    "mercari": {
        "label": "Mercari",
        "mode": "assisted",
        "status": "coming_soon",
        "notes": (
            "Assisted publishing only: complete listing payload plus a"
            " prefill / open-in-browser helper; the human clicks publish."
            " No private APIs, ever."
        ),
    },
    "facebook": {
        "label": "Facebook Marketplace",
        "mode": "assisted",
        "status": "coming_soon",
        "notes": (
            "Assisted publishing only: complete listing payload plus a"
            " prefill / open-in-browser helper; the human clicks publish."
            " No private APIs, ever."
        ),
    },
}
