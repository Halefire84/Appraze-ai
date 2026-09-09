"""CRTC listing normalization.

Converts source-specific marketplace/auction records into one stable
listing dictionary that Opportunity Radar can score. This module is pure
logic: it does not fetch websites, scrape pages, or bypass access controls.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence


_MISSING = object()


@dataclass(frozen=True)
class NormalizedListing:
    source: str = ""
    source_listing_id: str = ""
    url: str = ""
    title: str = ""
    description: str = ""
    category: str = ""
    price: Optional[float] = None
    auction_end: Optional[str] = None
    seller: str = ""
    location: str = ""
    shipping: Optional[float] = None
    buyer_premium: Optional[float] = None
    condition: str = ""
    lot_number: str = ""
    images: tuple = ()
    estimated_value: Optional[float] = None
    expected_keywords: tuple = ()

    def to_radar_dict(self) -> Dict[str, Any]:
        """Return only the common fields Opportunity Radar consumes, while
        retaining source metadata in the returned record for UI/drill-down."""
        result = asdict(self)
        result["images"] = list(self.images)
        result["expected_keywords"] = list(self.expected_keywords)
        return result


def _first(record: Mapping[str, Any], aliases: Sequence[str], default: Any = "") -> Any:
    for key in aliases:
        value = record.get(key, _MISSING)
        if value is not _MISSING and value not in (None, ""):
            return value
    return default


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _number(value: Any) -> Optional[float]:
    if value in (None, "", False):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def _images(value: Any) -> tuple:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(x.strip() for x in value.split(",") if x.strip())
    if isinstance(value, Iterable) and not isinstance(value, (bytes, dict)):
        return tuple(str(x).strip() for x in value if str(x).strip())
    return ()


def _expected_keywords(category: str, title: str, description: str) -> tuple:
    """Provide conservative category hints for broad source records.

    These are deliberately suggestions, not an automatic category verdict.
    More precise source/category taxonomies can supply their own keywords.
    """
    value = f"{category} {title} {description}".lower()
    groups = {
        "jewelry": ("jewelry", "ring", "necklace", "bracelet", "gold", "silver", "watch"),
        "watches": ("watch", "wristwatch", "rolex", "omega", "seiko", "citizen"),
        "furniture": ("furniture", "chair", "table", "dresser", "cabinet", "desk"),
        "collectibles": ("collectible", "figurine", "comic", "card", "toy", "memorabilia"),
        "musical instruments": ("guitar", "violin", "piano", "instrument", "amp", "drum"),
        "tools": ("tool", "drill", "saw", "welder", "compressor", "mower"),
        "cameras": ("camera", "lens", "nikon", "canon", "leica", "sony"),
    }
    for label, keywords in groups.items():
        if label in value:
            return tuple(keywords)
    return ()


def normalize_listing(record: Mapping[str, Any], *, source: str = "") -> Dict[str, Any]:
    """Normalize a source record into the CRTC common listing schema.

    Common aliases such as ``name``/``title``, ``asking_price``/``price`` and
    ``source_url``/``url`` are accepted so adapters remain small. Unknown
    fields are intentionally ignored rather than leaking source-specific
    assumptions into the Radar contract.
    """
    resolved_source = _text(source or _first(record, ("source", "marketplace", "site")))
    title = _text(_first(record, ("title", "name", "listing_title", "item_title")))
    description = _text(_first(record, ("description", "details", "item_description", "short_description")))
    category = _text(_first(record, ("category", "category_name", "department", "section")))
    expected = _first(record, ("expected_keywords", "category_keywords"), None)
    if expected is None:
        expected = _expected_keywords(category, title, description)
    elif isinstance(expected, str):
        expected = tuple(x.strip() for x in expected.split(",") if x.strip())
    else:
        expected = tuple(str(x).strip() for x in expected if str(x).strip())

    normalized = NormalizedListing(
        source=resolved_source,
        source_listing_id=_text(_first(record, ("source_listing_id", "listing_id", "item_id", "id"))),
        url=_text(_first(record, ("url", "source_url", "listing_url", "item_url", "itemWebUrl"))),
        title=title,
        description=description,
        category=category,
        price=_number(_first(record, ("price", "asking_price", "current_bid", "current_price", "amount"), None)),
        auction_end=_text(_first(record, ("auction_end", "end_time", "itemEndDate", "ends_at"), None)) or None,
        seller=_text(_first(record, ("seller", "seller_name", "auctioneer"))),
        location=_text(_first(record, ("location", "item_location", "pickup_location"))),
        shipping=_number(_first(record, ("shipping", "shipping_cost", "delivery_cost"), None)),
        buyer_premium=_number(_first(record, ("buyer_premium", "premium", "buyers_premium"), None)),
        condition=_text(_first(record, ("condition", "item_condition"))),
        lot_number=_text(_first(record, ("lot_number", "lot", "lot_id"))),
        images=_images(_first(record, ("images", "image_urls", "imageUrls", "photos"), None)),
        estimated_value=_number(_first(record, ("estimated_value", "market_value", "resale_value"), None)),
        expected_keywords=tuple(expected),
    )
    return normalized.to_radar_dict()


def normalize_listings(records: Iterable[Mapping[str, Any]], *, source: str = ""):
    """Normalize an iterable of source records while preserving input order."""
    return [normalize_listing(record, source=source) for record in records]
