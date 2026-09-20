"""
number_normalize.py — Canonical financial / numeric parser for CRTC.

Single place that turns messy marketplace strings into typed values.
Distinguishes dollars vs percentage points vs fractional percentages.
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional, Tuple

_CURRENCY_RE = re.compile(
    r"^\s*(?:USD|US\$|\$)?\s*([+-]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[+-]?\d+(?:\.\d+)?)\s*(?:USD|dollars?)?\s*$",
    re.IGNORECASE,
)
_PCT_RE = re.compile(
    r"^\s*([+-]?\d+(?:\.\d+)?)\s*%\s*$",
    re.IGNORECASE,
)


def parse_money(value: Any) -> Optional[float]:
    """Parse a dollar amount. Returns None for unknown / invalid / negative."""
    if value is None or value is False or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f) or f < 0:
            return None
        return f
    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "tbd", "n/a", "na"}:
        return None
    m = _CURRENCY_RE.match(s)
    if not m:
        # last-chance strip
        cleaned = s.replace("$", "").replace(",", "").replace("USD", "").replace("usd", "").strip()
        try:
            f = float(cleaned)
        except ValueError:
            return None
        if math.isnan(f) or math.isinf(f) or f < 0:
            return None
        return f
    f = float(m.group(1).replace(",", ""))
    if math.isnan(f) or math.isinf(f) or f < 0:
        return None
    return f


def parse_percent_points(value: Any, *, treat_fraction_as_pct: bool = True) -> Optional[float]:
    """
    Parse a percentage expressed in percentage points.

    "18", "18%", "18 %" → 18.0
    0.18 with treat_fraction_as_pct=True → 18.0  (common auction feed ambiguity)
    0.18 with treat_fraction_as_pct=False → 0.18

    Returns None for unknown / invalid.
    """
    if value is None or value is False or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f) or f < 0:
            return None
        if treat_fraction_as_pct and 0 < f < 1:
            return f * 100.0
        return f
    s = str(value).strip().strip("'\"")
    if not s or s.lower() in {"nan", "none", "null", "tbd"}:
        return None
    m = _PCT_RE.match(s)
    if m:
        f = float(m.group(1))
        if f < 0:
            return None
        return f
    cleaned = s.replace("%", "").replace(",", "").strip()
    try:
        f = float(cleaned)
    except ValueError:
        return None
    if math.isnan(f) or math.isinf(f) or f < 0:
        return None
    if treat_fraction_as_pct and 0 < f < 1:
        return f * 100.0
    return f


def parse_number(value: Any) -> Optional[float]:
    """Generic non-negative finite float, or None."""
    if value is None or value is False or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        f = float(str(value).replace(",", "").replace("$", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f
