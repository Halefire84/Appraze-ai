"""
Appraze Opportunity Radar
=========================

Deterministic, dependency-free detection of potentially underpriced or
misrepresented marketplace listings. This is the foundation for the CRTC
"holy grail finds" workflow: typo listings, weak/mismatched titles and
descriptions, suspicious categories, and other listings worth human review.

This module intentionally does NOT scrape sites or bypass anti-bot controls.
Marketplace adapters can feed normalized listing dictionaries into
`analyze_listing()` later.
"""

from dataclasses import dataclass, field
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


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
    "midcenturyy": "midcentury",
}

_CATEGORY_TERMS = {
    "jewelry": {"jewelry", "jewellery", "ring", "necklace", "bracelet", "earring", "gold", "silver", "watch"},
    "watches": {"watch", "wristwatch", "rolex", "omega", "seiko", "citizen"},
    "furniture": {"furniture", "chair", "table", "dresser", "cabinet", "desk", "sofa", "bed", "chest"},
    "collectibles": {"collectible", "figurine", "comic", "card", "toy", "memorabilia", "antique"},
    "musical instruments": {"guitar", "violin", "piano", "instrument", "amp", "drum", "keyboard"},
    "tools": {"tool", "drill", "saw", "welder", "compressor", "mower", "wrench"},
    "cameras": {"camera", "lens", "nikon", "canon", "leica", "sony"},
}


def _text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokens(value: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", value.lower())


def detect_typos(title: str, description: str = "") -> List[RadarSignal]:
    text = " ".join((_text(title), _text(description))).lower()
    found: List[RadarSignal] = []
    for typo, correction in _COMMON_TYPOS.items():
        if re.search(rf"\b{re.escape(typo)}\b", text):
            found.append(RadarSignal("title_description_typo", "high", 24, f"Possible spelling error: '{typo}' → '{correction}'."))
    return found


def detect_title_quality(title: str) -> List[RadarSignal]:
    value = _text(title)
    tokens = _tokens(value)
    signals: List[RadarSignal] = []
    if len(tokens) <= 2:
        signals.append(RadarSignal("weak_title", "warning", 12, "Very short listing title may be poorly indexed."))
    if len(value) >= 90:
        signals.append(RadarSignal("overlong_title", "info", 5, "Very long title may contain noisy or poorly structured keywords."))
    if value and value == value.lower() and len(tokens) >= 3:
        signals.append(RadarSignal("all_lowercase_title", "info", 6, "All-lowercase title may indicate an informal or rushed listing."))
    if re.search(r"\b(?:need|must)\s*(?:gone|sell|sold)\b", value, re.I):
        signals.append(RadarSignal("distress_language", "warning", 14, "Seller language suggests urgency; review for a potential pricing opportunity."))
    return signals


def detect_title_description_mismatch(title: str, description: str) -> List[RadarSignal]:
    title_tokens = set(_tokens(_text(title)))
    desc_tokens = set(_tokens(_text(description)))
    if not title_tokens or not desc_tokens or len(desc_tokens) < 5:
        return []
    overlap = len(title_tokens & desc_tokens) / max(1, len(title_tokens))
    if overlap < 0.20:
        return [RadarSignal("title_description_mismatch", "high", 20, "Title and description share unusually little vocabulary; possible wrong title or description.")]
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
            return [RadarSignal("possible_misclassification", "high", 28, f"Listing text appears inconsistent with the supplied category '{_text(category)}'.")]
        return []
    if expected:
        hits = sum(1 for keyword in expected if keyword in haystack)
        if hits == 0:
            return [RadarSignal("possible_misclassification", "high", 28, f"Listing text does not match the supplied category '{_text(category)}'.")]
    return []


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

    price = listing.get("price")
    estimated_value = listing.get("estimated_value")
    try:
        if price is not None and estimated_value is not None and float(price) > 0:
            gap = (float(estimated_value) - float(price)) / float(price)
            if gap >= 2.0:
                signals.append(RadarSignal("extreme_value_gap", "high", 35, "Estimated value is at least 3× asking price."))
            elif gap >= 1.0:
                signals.append(RadarSignal("strong_value_gap", "warning", 22, "Estimated value is at least 2× asking price."))
            elif gap >= 0.50:
                signals.append(RadarSignal("value_gap", "info", 10, "Estimated value is meaningfully above asking price."))
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
