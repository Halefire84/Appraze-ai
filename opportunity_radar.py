"""
CRTC Opportunity Radar
======================

Broad, deterministic detection of potentially mispriced, misidentified,
misclassified, overlooked, or unusually large resale opportunities.

The Holy Grail strategy is category-agnostic: precious metals are only one
lane. The radar also looks for bulk electronics, tools, collectibles,
industrial equipment, media, furniture, cameras, instruments, branded goods,
parts lots, and generic/miscellaneous lots where value may be hidden.

Signals are leads, not proof. A high score means "investigate this," not
"buy this." The system deliberately avoids scraping or bypassing anti-bot
controls; legitimate marketplace adapters feed normalized listings here.
"""

from dataclasses import dataclass, field
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

RULE_VERSION = "HG-2.0"


@dataclass(frozen=True)
class RadarSignal:
    code: str
    severity: str
    score: float
    message: str


@dataclass(frozen=True)
class RadarResult:
    opportunity_score: float
    signals: Tuple[RadarSignal, ...] = field(default_factory=tuple)
    review_required: bool = False


_COMMON_TYPOS = {
    "reciever": "receiver", "seperate": "separate", "occured": "occurred",
    "teh": "the", "definately": "definitely", "untill": "until",
    "wierd": "weird", "heigth": "height", "lenght": "length", "widht": "width",
    "authenticatd": "authenticated", "authenitc": "authentic", "vintange": "vintage",
    "antqiue": "antique", "porcelainl": "porcelain", "sterlling": "sterling",
    "sterlng": "sterling", "brasss": "brass", "midcentry": "midcentury",
    "midcenturyy": "midcentury", "gibsonn": "gibson", "martinny": "martin",
    "nikonn": "nikon", "cannonn": "canon", "tiffanyy": "tiffany",
    "rolexx": "rolex", "sonyss": "sony", "playstion": "playstation",
    "nintedo": "nintendo", "xboxx": "xbox", "macbookk": "macbook",
}

_CATEGORY_TERMS = {
    "jewelry": {"jewelry", "jewellery", "ring", "necklace", "bracelet", "earring", "gold", "silver", "watch"},
    "watches": {"watch", "wristwatch", "rolex", "omega", "seiko", "citizen"},
    "furniture": {"furniture", "chair", "table", "dresser", "cabinet", "desk", "sofa", "bed", "chest"},
    "collectibles": {"collectible", "figurine", "comic", "card", "toy", "memorabilia", "antique"},
    "musical instruments": {"guitar", "violin", "piano", "instrument", "amp", "drum", "keyboard"},
    "tools": {"tool", "drill", "saw", "welder", "compressor", "mower", "wrench"},
    "cameras": {"camera", "lens", "nikon", "canon", "leica", "sony"},
    "electronics": {"electronics", "computer", "laptop", "desktop", "monitor", "receiver", "stereo", "audio", "speaker", "console", "tablet", "phone", "printer"},
    "computers": {"computer", "laptop", "desktop", "macbook", "thinkpad", "surface", "server", "workstation"},
    "video games": {"game", "gaming", "console", "playstation", "xbox", "nintendo", "switch", "nes", "snes"},
    "industrial": {"industrial", "machine", "pump", "motor", "generator", "compressor", "cnc", "lathe", "equipment"},
}

_GENERIC_LOT_TERMS = {
    "lot", "lots", "bundle", "bundled", "bulk", "assorted", "misc", "miscellaneous",
    "mixed", "collection", "estate", "box", "boxlot", "joblot", "group", "case",
    "pallet", "skid", "bin", "warehouse", "liquidation", "clearance", "surplus",
    "overstock", "inventory", "contents", "everything", "all", "various",
}

_HIDDEN_VALUE_TERMS = {
    "unidentified", "unknown", "unmarked", "untested", "not tested", "as-is", "asis",
    "no idea", "dont know", "don't know", "not sure", "unknown maker", "maker unknown",
    "old stuff", "stuff", "miscellaneous", "misc", "see photos", "pictured",
    "found in", "from estate", "estate find", "cleanout", "storage unit", "left behind",
}

_HIGH_VALUE_BRANDS = {
    "apple", "sony", "canon", "nikon", "leica", "hasselblad", "tiffany", "cartier",
    "rolex", "omega", "gibson", "martin", "fender", "moog", "harman kardon", "marantz",
    "mcintosh", "pioneer", "denon", "bosch", "festool", "milwaukee", "snap-on", "dewalt",
    "fluke", "keysight", "agilent", "tektronix", "hewlett packard", "hp", "ibm", "lenovo",
    "thinkpad", "playstation", "nintendo", "xbox", "lego", "hermes", "chanel", "gucci",
}


def _text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokens(value: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", value.lower())


def _number(value: object) -> Optional[float]:
    try:
        return float(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _signal(code: str, severity: str, score: float, message: str) -> RadarSignal:
    return RadarSignal(code, severity, score, message)


def detect_typos(title: str, description: str = "") -> List[RadarSignal]:
    text = " ".join((_text(title), _text(description))).lower()
    found: List[RadarSignal] = []
    for typo, correction in _COMMON_TYPOS.items():
        if re.search(rf"\b{re.escape(typo)}\b", text):
            found.append(_signal("title_description_typo", "high", 25, f"Possible spelling error: '{typo}' → '{correction}'."))
    return found


def detect_title_quality(title: str) -> List[RadarSignal]:
    value = _text(title)
    tokens = _tokens(value)
    signals: List[RadarSignal] = []
    if len(tokens) <= 2:
        signals.append(_signal("weak_title", "warning", 12, "Very short listing title may be poorly indexed."))
    if len(value) >= 90:
        signals.append(_signal("overlong_title", "info", 5, "Very long title may contain noisy or poorly structured keywords."))
    if value and value == value.lower() and len(tokens) >= 3:
        signals.append(_signal("all_lowercase_title", "info", 6, "All-lowercase title may indicate an informal or rushed listing."))
    if re.search(r"\b(?:need|must)\s*(?:gone|sell|sold)\b", value, re.I):
        signals.append(_signal("distress_language", "warning", 14, "Seller language suggests urgency; review for a potential pricing opportunity."))
    return signals


def detect_title_description_mismatch(title: str, description: str) -> List[RadarSignal]:
    title_tokens = set(_tokens(_text(title)))
    desc_tokens = set(_tokens(_text(description)))
    if not title_tokens or not desc_tokens or len(desc_tokens) < 5:
        return []
    overlap = len(title_tokens & desc_tokens) / max(1, len(title_tokens))
    if overlap < 0.20:
        return [_signal("title_description_mismatch", "high", 20, "Title and description share unusually little vocabulary; possible wrong title or description.")]
    return []


def detect_category_mismatch(
    category: Optional[str],
    expected_keywords: Optional[Sequence[str]],
    title: str,
    description: str = "",
) -> List[RadarSignal]:
    """Flag text that conflicts with the supplied marketplace category."""
    if not category:
        return []
    haystack = set(_tokens(" ".join((_text(title), _text(description)))))
    expected = {_text(k).lower() for k in (expected_keywords or ()) if _text(k)}
    category_key = _text(category).lower()
    category_terms = _CATEGORY_TERMS.get(category_key)
    if category_terms:
        category_hits = haystack & category_terms
        if not category_hits and (not expected or haystack & expected):
            return [_signal("possible_misclassification", "high", 28, f"Listing text appears inconsistent with the supplied category '{_text(category)}'.")]
        return []
    if expected:
        hits = sum(1 for keyword in expected if keyword in haystack)
        if hits == 0:
            return [_signal("possible_misclassification", "high", 28, f"Listing text does not match the supplied category '{_text(category)}'.")]
    return []


def detect_bulk_lot_signals(listing: Dict[str, object], title: str, description: str) -> List[RadarSignal]:
    """Surface lots where value can be hidden in quantity, brands, or generic wording."""
    text = " ".join((title, description)).lower()
    tokens = set(_tokens(text))
    signals: List[RadarSignal] = []
    lot_terms = tokens & _GENERIC_LOT_TERMS
    quantity = _number(listing.get("quantity"))
    if quantity is None:
        match = re.search(r"\b(\d{1,5})\s*(?:pcs?|pieces?|units?|items?|sets?|pairs?|laptops?|phones?|computers?|games?|tools?)\b", text)
        quantity = float(match.group(1)) if match else None
    if quantity is not None and quantity >= 5:
        score = 14 if quantity < 20 else 20 if quantity < 50 else 27
        signals.append(_signal("bulk_quantity", "high" if quantity >= 50 else "warning", score, f"Bulk quantity detected ({int(quantity) if quantity.is_integer() else quantity:g}); individual-unit value may be hidden."))
    if lot_terms:
        signals.append(_signal("generic_lot_wording", "warning", 8, "Generic/bulk lot wording may reduce search visibility and hide valuable individual items."))
    if "pallet" in tokens or "skid" in tokens or "warehouse" in tokens or "liquidation" in tokens:
        signals.append(_signal("liquidation_lot", "warning", 10, "Liquidation/surplus wording indicates a bulk sourcing opportunity that warrants per-unit analysis."))
    return signals


def detect_hidden_value_signals(title: str, description: str) -> List[RadarSignal]:
    text = " ".join((_text(title), _text(description))).lower()
    signals: List[RadarSignal] = []
    matched = [term for term in _HIDDEN_VALUE_TERMS if term in text]
    if matched:
        signals.append(_signal("seller_uncertainty", "warning", 10, "Seller appears uncertain about identity, maker, condition, or value; verify independently."))
    if re.search(r"\b(?:untested|not tested|as[- ]?is|for parts|parts only|repair)\b", text):
        signals.append(_signal("condition_uncertainty", "warning", 6, "Condition is uncertain or the item is sold as-is/for repair; value may exist but risk is elevated."))
    if re.search(r"\b(?:see photos|see pictures|pictured|photo shows)\b", text) and len(_tokens(_text(description))) < 12:
        signals.append(_signal("photo_dependent_listing", "info", 7, "Description is thin and relies on photos; visual inspection may reveal information the title misses."))
    return signals


def detect_brand_model_leakage(title: str, description: str) -> List[RadarSignal]:
    title_l = _text(title).lower()
    desc_l = _text(description).lower()
    signals: List[RadarSignal] = []
    brands_in_desc = [brand for brand in _HIGH_VALUE_BRANDS if re.search(rf"\b{re.escape(brand)}\b", desc_l)]
    brands_missing_title = [brand for brand in brands_in_desc if not re.search(rf"\b{re.escape(brand)}\b", title_l)]
    if brands_missing_title:
        signals.append(_signal("brand_hidden_in_description", "high", 18, "Potentially valuable brand appears in the description but not the title; listing may be poorly indexed."))
    model_like = re.findall(r"\b(?:model|mod|pn|p/n|part|ref|reference|style|type)\s*[#:.-]?\s*[a-z0-9][a-z0-9._/-]{2,}\b", desc_l, re.I)
    if model_like and not re.search(r"\b(?:model|mod|pn|p/n|part|ref|reference|style|type)\b", title_l, re.I):
        signals.append(_signal("model_number_hidden", "high", 15, "A model/part/reference identifier appears only in the description; searchable identity may be suppressed."))
    return signals


def detect_precious_material_signals(title: str, description: str) -> List[RadarSignal]:
    text = " ".join((_text(title), _text(description))).lower()
    if not re.search(r"\b(?:10k|14k|18k|22k|24k|9k|375|417|585|750|916|999|925|sterling|coin silver|platinum|950|palladium)\b", text):
        return []
    if not re.search(r"\b(?:gold|silver|sterling|platinum|palladium|jewelry|jewellery|ring|necklace|bracelet|earring|chain|watch)\b", text):
        return [_signal("precious_material_mismatch", "high", 18, "Precious-metal fineness terminology appears without matching jewelry/material context; verify for a possible categorization or description error.")]
    return [_signal("precious_material_present", "info", 5, "Precious-metal/material marker detected; calculate intrinsic value separately from collector value.")]


def analyze_listing(listing: Dict[str, object]) -> RadarResult:
    title = _text(listing.get("title"))
    description = _text(listing.get("description"))
    category = _text(listing.get("category")) or None
    expected_keywords = listing.get("expected_keywords")
    signals: List[RadarSignal] = []
    signals.extend(detect_typos(title, description))
    signals.extend(detect_title_quality(title))
    signals.extend(detect_title_description_mismatch(title, description))
    if isinstance(expected_keywords, (list, tuple, set)):
        signals.extend(detect_category_mismatch(category, expected_keywords, title, description))
    signals.extend(detect_bulk_lot_signals(listing, title, description))
    signals.extend(detect_hidden_value_signals(title, description))
    signals.extend(detect_brand_model_leakage(title, description))
    signals.extend(detect_precious_material_signals(title, description))

    price = _number(listing.get("price"))
    estimated_value = _number(listing.get("estimated_value"))
    quantity = _number(listing.get("quantity"))
    if quantity and quantity > 1 and price is not None and price > 0:
        unit_price = price / quantity
        if unit_price <= 5:
            signals.append(_signal("low_unit_cost", "high", 16, f"Low implied acquisition cost per unit (${unit_price:,.2f}); verify quantity, condition, and resale demand."))
        elif unit_price <= 15:
            signals.append(_signal("attractive_unit_cost", "warning", 9, f"Potentially attractive unit cost (${unit_price:,.2f}); compare against realistic sold comps."))

    try:
        if price is not None and estimated_value is not None and price > 0:
            gap = (estimated_value - price) / price
            if gap >= 5.0:
                signals.append(_signal("extreme_value_gap", "critical", 45, "Estimated value is at least 6× asking price; independently verify identity and comps."))
            elif gap >= 2.0:
                signals.append(_signal("extreme_value_gap", "high", 35, "Estimated value is at least 3× asking price."))
            elif gap >= 1.0:
                signals.append(_signal("strong_value_gap", "warning", 22, "Estimated value is at least 2× asking price."))
            elif gap >= 0.50:
                signals.append(_signal("value_gap", "info", 10, "Estimated value is meaningfully above asking price."))
    except (TypeError, ValueError, ZeroDivisionError):
        pass

    score = min(100.0, sum(signal.score for signal in signals))
    if len(signals) >= 3:
        score = min(100.0, score + 8)
    if len(signals) >= 5:
        score = min(100.0, score + 7)
    return RadarResult(round(score, 1), tuple(signals), score >= 25)


def rank_listings(listings: Iterable[Dict[str, object]]) -> List[Tuple[Dict[str, object], RadarResult]]:
    ranked = [(listing, analyze_listing(listing)) for listing in listings]
    return sorted(ranked, key=lambda item: item[1].opportunity_score, reverse=True)
