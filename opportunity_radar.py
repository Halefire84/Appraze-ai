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
    severity: str  # info | warning | high
    score: float
    message: str


@dataclass(frozen=True)
class RadarResult:
    opportunity_score: float
    signals: Tuple[RadarSignal, ...] = field(default_factory=tuple)
    review_required: bool = False


_COMMON_TYPOS = {
    "reciever": "receiver",
    "seperate": "separate",
    "occured": "occurred",
    "teh": "the",
    "definately": "definitely",
    "untill": "until",
    "wierd": "weird",
    "heigth": "height",
    "lenght": "length",
    "widht": "width",
    "authenticatd": "authenticated",
    "authenitc": "authentic",
    "vintange": "vintage",
    "antqiue": "antique",
    "porcelainl": "porcelain",
    "sterlling": "sterling",
    "sterlng": "sterling",
    "brasss": "brass",
    "midcentry": "midcentury",
    "midcenturyy": "midcentury",
}


def _text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _tokens(value: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", value.lower())


def detect_typos(title: str, description: str = "") -> List[RadarSignal]:
    """Return signals for common high-value spelling mistakes."""
    text = " ".join((_text(title), _text(description))).lower()
    found: List[RadarSignal] = []
    for typo, correction in _COMMON_TYPOS.items():
        if re.search(rf"\b{re.escape(typo)}\b", text):
            found.append(
                RadarSignal(
                    code="title_description_typo",
                    severity="high",
                    score=24,
                    message=f"Possible spelling error: '{typo}' → '{correction}'.",
                )
            )
    return found


def detect_title_quality(title: str) -> List[RadarSignal]:
    """Detect titles that are unusually weak for marketplace discovery."""
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
    """Flag listings whose title and description share very little vocabulary."""
    title_tokens = set(_tokens(_text(title)))
    desc_tokens = set(_tokens(_text(description)))
    if not title_tokens or not desc_tokens or len(desc_tokens) < 5:
        return []
    overlap = len(title_tokens & desc_tokens) / max(1, len(title_tokens))
    if overlap < 0.20:
        return [RadarSignal(
            "title_description_mismatch",
            "high",
            20,
            "Title and description share unusually little vocabulary; possible wrong title or description.",
        )]
    return []


def detect_category_mismatch(
    category: Optional[str],
    expected_keywords: Optional[Sequence[str]],
    title: str,
    description: str = "",
) -> List[RadarSignal]:
    """Flag a category when listing text strongly contradicts its expected keywords."""
    if not category or not expected_keywords:
        return []
    haystack = set(_tokens(" ".join((_text(title), _text(description)))))
    expected = {_text(k).lower() for k in expected_keywords if _text(k)}
    if not expected:
        return []
    hits = sum(1 for keyword in expected if keyword in haystack)
    if hits == 0:
        return [RadarSignal(
            "possible_misclassification",
            "high",
            28,
            f"Listing text does not match the supplied category '{_text(category)}'.",
        )]
    return []


def analyze_listing(listing: Dict[str, object]) -> RadarResult:
    """Analyze one normalized listing dictionary.

    Supported keys: title, description, category, expected_keywords, price,
    estimated_value. Estimated value is optional; when supplied, a large
    value gap increases the opportunity score but never creates a BUY verdict.
    """
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
    # Multiple independent signals are more useful than one noisy signal.
    if len(signals) >= 3:
        score = min(100.0, score + 8)
    if len(signals) >= 5:
        score = min(100.0, score + 7)

    return RadarResult(
        opportunity_score=round(score, 1),
        signals=tuple(signals),
        review_required=score >= 25,
    )


def rank_listings(listings: Iterable[Dict[str, object]]) -> List[Tuple[Dict[str, object], RadarResult]]:
    """Return listings ranked from strongest radar signal to weakest."""
    ranked = [(listing, analyze_listing(listing)) for listing in listings]
    return sorted(ranked, key=lambda item: item[1].opportunity_score, reverse=True)
