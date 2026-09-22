"""
Cooper River Trading Co. — Appraze Market Comps Engine
=======================================================
Pure logic for turning a handful of comparable listings (sold or active,
from any source) into a defensible resale-value estimate with an
explainable confidence rating — then handing that estimate to finance.py
so the buy/pass verdict is still one deterministic calculation, not two
disagreeing numbers.

Deliberately free of network/Streamlit/pandas code, same as finance.py:
this module only does math over a list of Comp objects. Anything that
actually FETCHES comps (manual entry, a pasted CSV, a live eBay lookup)
lives in comps_adapters.py and hands its results to summarize_comps()
here — the adapter architecture the roadmap calls for, without forcing
every future source (sold listings, current listings, historical pricing)
through the same fragile scraper.

Roadmap this exists for:
    FIND -> IDENTIFY -> VALUE -> DECIDE -> BUY -> TRACK -> LIST -> SELL -> MEASURE PROFIT
This module is the "VALUE" step's evidence layer: MARKET EVIDENCE (this
file) + APPRAZE FINANCIAL MATH (finance.py) -> DECIDE (evaluate_with_comps
below, which calls straight into finance.calc_deal rather than
re-implementing profit/ROI math a second time).
"""

import statistics
from dataclasses import dataclass, field
from typing import List, Optional

from finance import DealResult, DEFAULT_FEE_PCT, DEFAULT_PREMIUM_PCT, calc_deal, max_cost_for_target_roi
from deal_settings import (
    DealMathSettings,
    DEFAULT_CV_THRESHOLD_FALLBACK,
    resolve_category,
)

# A "sold" comp is evidence of what a buyer actually paid. An "active" comp
# is only an asking price — real signal, but weaker, since sellers ask
# whatever they want and plenty of listings never sell at that price.
SOLD = "sold"
ACTIVE = "active"
LISTING_TYPES = (SOLD, ACTIVE)

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

# Coefficient of variation (stdev / mean) above this suggests the comps
# aren't really comparable to each other (different items/conditions
# lumped together under one search), so confidence is capped regardless
# of sample size.
HIGH_SPREAD_CV_THRESHOLD = 0.5


@dataclass
class Comp:
    """One comparable listing, from any source."""
    price: float
    source: str = ""                 # e.g. "eBay", "HiBid", "Manual"
    listing_type: str = SOLD         # "sold" | "active"
    condition: str = ""              # e.g. "Used - Good", "New"
    shipping: float = 0.0
    listing_date: Optional[str] = None  # ISO date string, if known
    title: str = ""
    url: str = ""


@dataclass
class CompsSummary:
    count: int
    sold_count: int
    active_count: int
    low: float
    high: float
    median: float
    mean: float
    suggested_value: float
    confidence: str
    confidence_reason: str
    # --- outlier trimming / thin-comp / inconsistency additions ---
    trimmed_outlier_count: int = 0
    raw_suggested_value: float = 0.0        # value before the thin-comp haircut
    thin_comps: bool = False
    haircut_pct: float = 0.0
    inconsistent: bool = False
    warnings: List[str] = field(default_factory=list)


def _price_with_shipping(comp: Comp) -> float:
    return comp.price + (comp.shipping or 0.0)


def _trim_outliers(comps: List[Comp], multiple: float) -> tuple:
    """Drop comps priced above `multiple`x the median of all comps (by
    price+shipping). Returns (surviving_comps, trimmed_count). Never trims
    below 1 surviving comp."""
    if len(comps) < 2:
        return comps, 0
    prices = [_price_with_shipping(c) for c in comps]
    med = statistics.median(prices)
    if med <= 0:
        return comps, 0
    threshold = med * multiple
    survivors = [c for c, p in zip(comps, prices) if p <= threshold]
    if not survivors:
        return comps, 0
    return survivors, len(comps) - len(survivors)


def summarize_comps(
    comps: List[Comp],
    *,
    category: Optional[str] = None,
    settings: Optional[DealMathSettings] = None,
) -> Optional[CompsSummary]:
    """
    Turns a list of Comp objects into distribution stats + a single
    suggested resale value + an explainable confidence rating. Returns
    None for an empty list — callers should treat "no comps" as "no
    market evidence available" rather than a zero-value estimate.

    suggested_value prefers the median of SOLD comps (actual transaction
    evidence). If there are no sold comps, it falls back to the median of
    whatever's available (active listings only) with confidence capped at
    "low" — an asking-price-only estimate is a starting point, not proof.

    Before that median is taken, comps priced above
    settings.outlier_trim_multiple x the median are trimmed (brief item 4).
    If the surviving comps still disagree wildly (category-aware CV
    threshold), `inconsistent` is set and a "comps disagree" warning is
    added rather than silently averaging chaos. Fewer than
    settings.thin_comp_count_threshold surviving comps applies a
    thin_comp_haircut_pct haircut to the estimate (brief item 5).
    """
    if not comps:
        return None

    settings = settings or DealMathSettings()
    warnings: List[str] = []

    trimmed, trimmed_count = _trim_outliers(comps, settings.outlier_trim_multiple)
    if trimmed_count:
        warnings.append(
            f"Trimmed {trimmed_count} comp(s) priced over {settings.outlier_trim_multiple:g}x the median as outliers."
        )

    all_prices = [_price_with_shipping(c) for c in trimmed]
    sold = [c for c in trimmed if c.listing_type == SOLD]
    active = [c for c in trimmed if c.listing_type == ACTIVE]

    sold_prices = [_price_with_shipping(c) for c in sold]
    basis_prices = sold_prices if sold_prices else all_prices
    raw_suggested_value = statistics.median(basis_prices)

    mean_price = statistics.mean(all_prices)
    cv = (statistics.pstdev(all_prices) / mean_price) if mean_price and len(all_prices) > 1 else 0.0

    cv_threshold = settings.category_cv_threshold.get(
        resolve_category(category), DEFAULT_CV_THRESHOLD_FALLBACK
    )
    inconsistent = len(all_prices) > 1 and cv > cv_threshold
    if inconsistent:
        warnings.append(
            f"Comps disagree — high uncertainty (spread {cv:.0%} of the mean, over the {cv_threshold:.0%} threshold for this category)."
        )

    confidence, reason = _rate_confidence(
        total_count=len(trimmed),
        sold_count=len(sold),
        coefficient_of_variation=cv,
    )
    if inconsistent and confidence != CONFIDENCE_LOW:
        confidence, reason = CONFIDENCE_LOW, warnings[-1]

    thin_comps = len(trimmed) < settings.thin_comp_count_threshold
    haircut_pct = settings.thin_comp_haircut_pct if thin_comps else 0.0
    suggested_value = raw_suggested_value * (1 - haircut_pct / 100.0)
    if thin_comps:
        warnings.append(
            f"Thin comps — only {len(trimmed)} surviving comp(s); applied a {haircut_pct:g}% uncertainty haircut."
        )

    return CompsSummary(
        count=len(trimmed),
        sold_count=len(sold),
        active_count=len(active),
        low=min(all_prices),
        high=max(all_prices),
        median=statistics.median(all_prices),
        mean=mean_price,
        suggested_value=suggested_value,
        confidence=confidence,
        confidence_reason=reason,
        trimmed_outlier_count=trimmed_count,
        raw_suggested_value=raw_suggested_value,
        thin_comps=thin_comps,
        haircut_pct=haircut_pct,
        inconsistent=inconsistent,
        warnings=warnings,
    )


def _rate_confidence(total_count: int, sold_count: int, coefficient_of_variation: float) -> tuple:
    if sold_count == 0:
        return CONFIDENCE_LOW, "No sold comps — based on asking prices only, which is an upper bound, not proof of value."

    if coefficient_of_variation > HIGH_SPREAD_CV_THRESHOLD:
        return CONFIDENCE_LOW, f"Prices vary too widely to be confident these are truly comparable items (spread {coefficient_of_variation:.0%} of the mean)."

    if sold_count >= 8:
        return CONFIDENCE_HIGH, f"{sold_count} sold comps with consistent pricing."
    if sold_count >= 3:
        return CONFIDENCE_MEDIUM, f"{sold_count} sold comps — a reasonable sample, more would help."
    return CONFIDENCE_LOW, f"Only {sold_count} sold comp(s) — thin evidence, treat the estimate as rough."


@dataclass
class MarketVerdict:
    """MARKET EVIDENCE (comps_summary) + APPRAZE FINANCIAL MATH (deal,
    floor_cost — both computed by finance.py, never re-implemented here)
    combined into one decision."""
    comps_summary: CompsSummary
    deal: DealResult
    floor_cost: float


def evaluate_with_comps(
    comps: List[Comp],
    cost: float,
    fee_pct: float = DEFAULT_FEE_PCT,
    premium_pct: float = DEFAULT_PREMIUM_PCT,
    target_roi_pct: float = 40.0,
    category: Optional[str] = None,
    settings: Optional[DealMathSettings] = None,
) -> Optional[MarketVerdict]:
    """
    The VALUE + DECIDE steps of the roadmap in one call: summarizes the
    comps (with outlier trimming + thin-comp haircut applied, see
    summarize_comps) into a suggested resale value, then hands that
    straight to finance.calc_deal / finance.max_cost_for_target_roi — the
    exact same verdict math used everywhere else in Appraze, just fed real
    market evidence instead of a manually typed guess. Returns None if
    there are no comps to evaluate.
    """
    summary = summarize_comps(comps, category=category, settings=settings)
    if summary is None:
        return None

    deal = calc_deal(cost, summary.suggested_value, fee_pct=fee_pct, premium_pct=premium_pct)
    floor_cost = max_cost_for_target_roi(summary.suggested_value, target_roi_pct=target_roi_pct, fee_pct=fee_pct, premium_pct=premium_pct)
    return MarketVerdict(comps_summary=summary, deal=deal, floor_cost=floor_cost)
