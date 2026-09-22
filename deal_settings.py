"""
deal_settings.py — user-editable scoring knobs for CRTC deal math.

Every number in here is a *default* a reseller can override, never a fact.
Per the 2026-09-22 deal-math brief (simulation v2): resellers have their own
opinions on what counts as a deal, so nothing that feeds a BUY/PASS verdict
may be a hardcoded constant buried in the math modules. finance.py,
comps.py, decision_policy.py, and auction_costs.py all take a
DealMathSettings instance (or its individual fields) instead of baking
these numbers in.

Fee/shipping figures below are researched as of 2026-09-22 (see the brief
and ~/workspace/research_notes/reseller-deal-math-calibration-20260922-0326/
report.md). eBay and USPS both change these periodically -- re-verify
against the current published schedules before trusting them long-term.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. Category-aware eBay fee table (HIGHEST PRIORITY per brief)
# ---------------------------------------------------------------------------
CATEGORY_STANDARD = "standard"
CATEGORY_JEWELRY = "jewelry"
CATEGORY_BOOKS_MOVIES_MUSIC = "books_movies_music"
CATEGORY_TRADING_CARDS = "trading_cards_collectibles"

DEFAULT_CATEGORY_FEE_PCT: Dict[str, float] = {
    CATEGORY_STANDARD: 13.6,
    CATEGORY_JEWELRY: 15.0,
    CATEGORY_BOOKS_MOVIES_MUSIC: 15.3,
    CATEGORY_TRADING_CARDS: 13.25,
}
# Flat per-order fee, standard categories only, for orders over $10 (eBay's
# published structure at research time -- verify at implementation time).
DEFAULT_STANDARD_PER_ORDER_FEE = 0.40
DEFAULT_PER_ORDER_FEE_MIN_ORDER_VALUE = 10.0

# Promoted-listing ad rate is a separate, user-editable spend -- never
# folded into the base resale fee (brief item 1, explicit instruction).
DEFAULT_PROMOTED_LISTING_AD_PCT = 0.0

# ---------------------------------------------------------------------------
# 2. Weight-tiered shipping (USPS Ground Advantage commercial, researched
#    2026-09-22 -- re-verify current rates)
# ---------------------------------------------------------------------------
# (upper bound weight in lb, shipping cost). Looked up as "first tier whose
# upper bound >= item weight"; heavier than the top tier uses the top tier's
# rate rather than guessing.
DEFAULT_SHIPPING_WEIGHT_TIERS: List[Tuple[float, float]] = [
    (0.5, 5.45),    # ~8 oz
    (1.0, 7.46),    # ~1 lb
    (5.0, 11.00),   # 3-5 lb
    (10.0, 17.00),  # ~10 lb
]

PACKAGING_PADDED_POLY = "padded_poly"
PACKAGING_BOXED = "boxed"
DEFAULT_PACKAGING_COST: Dict[str, float] = {
    PACKAGING_PADDED_POLY: 0.15,
    PACKAGING_BOXED: 1.50,
}

# Sane category-based default weight (lb) used only when the item's actual
# weight is unknown.
DEFAULT_CATEGORY_WEIGHT_LB: Dict[str, float] = {
    CATEGORY_STANDARD: 1.0,
    CATEGORY_JEWELRY: 0.25,
    CATEGORY_BOOKS_MOVIES_MUSIC: 1.5,
    CATEGORY_TRADING_CARDS: 0.5,
}
DEFAULT_CATEGORY_PACKAGING: Dict[str, str] = {
    CATEGORY_STANDARD: PACKAGING_PADDED_POLY,
    CATEGORY_JEWELRY: PACKAGING_PADDED_POLY,
    CATEGORY_BOOKS_MOVIES_MUSIC: PACKAGING_BOXED,
    CATEGORY_TRADING_CARDS: PACKAGING_PADDED_POLY,
}

# ---------------------------------------------------------------------------
# 3. Auction buyer premium
# ---------------------------------------------------------------------------
DEFAULT_BUYER_PREMIUM_PCT = 13.0
DEFAULT_PER_LOT_FEE = 1.0

# ---------------------------------------------------------------------------
# 4. Comp outlier trimming + inconsistency signal
# ---------------------------------------------------------------------------
DEFAULT_OUTLIER_TRIM_MULTIPLE = 2.5  # trim comps priced above this x the median
# Category-aware noise expectations: collectibles are noisier than media
# (calibration report). Coefficient-of-variation above this threshold on the
# surviving comps trips the "comps disagree" signal.
DEFAULT_CATEGORY_CV_THRESHOLD: Dict[str, float] = {
    CATEGORY_STANDARD: 0.5,
    CATEGORY_JEWELRY: 0.5,
    CATEGORY_BOOKS_MOVIES_MUSIC: 0.35,
    CATEGORY_TRADING_CARDS: 0.6,
}
DEFAULT_CV_THRESHOLD_FALLBACK = 0.5

# ---------------------------------------------------------------------------
# 5. Thin-comp uncertainty haircut
# ---------------------------------------------------------------------------
DEFAULT_THIN_COMP_COUNT_THRESHOLD = 3  # fewer than this many surviving comps => thin
DEFAULT_THIN_COMP_HAIRCUT_PCT = 15.0

# ---------------------------------------------------------------------------
# 6. Hidden/missing-attribute uncertainty discount
# ---------------------------------------------------------------------------
DEFAULT_MISSING_ATTRIBUTE_DISCOUNT_PCT = 10.0
# The key value-driver attribute expected per category, purely to drive the
# "missing X -- verify before buying" prompt copy.
CATEGORY_KEY_ATTRIBUTE: Dict[str, str] = {
    CATEGORY_JEWELRY: "weight",
    "precious_metals": "weight",
    "furniture": "dimensions",
    "electronics": "model number",
}

# ---------------------------------------------------------------------------
# 7. Photo-presentation risk
# ---------------------------------------------------------------------------
PHOTO_CONFIDENCE_VERIFIED = "verified"            # scale reference / full context shown
PHOTO_CONFIDENCE_MACRO_NO_SCALE = "macro_no_scale"  # macro-only, no scale reference
PHOTO_CONFIDENCE_UNKNOWN = "unknown"
# Midpoint of the brief's observed 15-30% inflation range.
DEFAULT_PHOTO_RISK_DISCOUNT_PCT = 20.0

# ---------------------------------------------------------------------------
# 8. Threshold defaults
# ---------------------------------------------------------------------------
DEFAULT_MIN_PROFIT = 10.0
DEFAULT_MIN_ROI_PCT = 40.0
DEFAULT_MAX_BUY_COST: Optional[float] = None  # None = no cap; stays editable


@dataclass
class DealMathSettings:
    """Every scoring variable a reseller might want to retune, in one place."""

    category_fee_pct: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CATEGORY_FEE_PCT))
    standard_per_order_fee: float = DEFAULT_STANDARD_PER_ORDER_FEE
    per_order_fee_min_order_value: float = DEFAULT_PER_ORDER_FEE_MIN_ORDER_VALUE
    promoted_listing_ad_pct: float = DEFAULT_PROMOTED_LISTING_AD_PCT

    shipping_weight_tiers: List[Tuple[float, float]] = field(
        default_factory=lambda: list(DEFAULT_SHIPPING_WEIGHT_TIERS)
    )
    packaging_cost: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PACKAGING_COST))
    category_default_weight_lb: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_CATEGORY_WEIGHT_LB)
    )
    category_default_packaging: Dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_CATEGORY_PACKAGING)
    )

    buyer_premium_pct: float = DEFAULT_BUYER_PREMIUM_PCT
    per_lot_fee: float = DEFAULT_PER_LOT_FEE

    outlier_trim_multiple: float = DEFAULT_OUTLIER_TRIM_MULTIPLE
    category_cv_threshold: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_CATEGORY_CV_THRESHOLD)
    )

    thin_comp_count_threshold: int = DEFAULT_THIN_COMP_COUNT_THRESHOLD
    thin_comp_haircut_pct: float = DEFAULT_THIN_COMP_HAIRCUT_PCT

    missing_attribute_discount_pct: float = DEFAULT_MISSING_ATTRIBUTE_DISCOUNT_PCT

    photo_risk_discount_pct: float = DEFAULT_PHOTO_RISK_DISCOUNT_PCT

    min_profit: float = DEFAULT_MIN_PROFIT
    min_roi_pct: float = DEFAULT_MIN_ROI_PCT
    max_buy_cost: Optional[float] = DEFAULT_MAX_BUY_COST


def resolve_category(category: Optional[str]) -> str:
    if not category:
        return CATEGORY_STANDARD
    key = str(category).strip().lower().replace(" ", "_").replace("-", "_")
    return key if key in DEFAULT_CATEGORY_FEE_PCT else CATEGORY_STANDARD


def category_fee_pct(category: Optional[str], settings: Optional[DealMathSettings] = None) -> float:
    """Fee percentage for the item's category. Unknown categories fall back
    to the standard rate rather than silently using 0%."""
    settings = settings or DealMathSettings()
    key = resolve_category(category)
    return settings.category_fee_pct.get(key, settings.category_fee_pct[CATEGORY_STANDARD])


def category_fee_amount(order_value: float, category: Optional[str], settings: Optional[DealMathSettings] = None) -> float:
    """Total marketplace fee in dollars for one order: category % of the
    resale value, plus the standard per-order flat fee when the category is
    "standard" and the order clears the minimum order value."""
    settings = settings or DealMathSettings()
    key = resolve_category(category)
    pct_fee = order_value * category_fee_pct(key, settings) / 100.0
    flat_fee = 0.0
    if key == CATEGORY_STANDARD and order_value > settings.per_order_fee_min_order_value:
        flat_fee = settings.standard_per_order_fee
    return round(pct_fee + flat_fee, 2)


def estimate_shipping_cost(
    weight_lb: Optional[float],
    category: Optional[str] = None,
    packaging_type: Optional[str] = None,
    settings: Optional[DealMathSettings] = None,
) -> Tuple[float, float, float, str]:
    """Weight-tiered shipping estimate + packaging cost.

    Returns (shipping_total, shipping_tier_cost, packaging_cost, weight_used_lb_source)
    where the last element is "given" or "category_default" so callers can
    flag an estimate as assumed rather than measured.
    """
    settings = settings or DealMathSettings()
    key = resolve_category(category)

    if weight_lb is None or weight_lb <= 0:
        weight = settings.category_default_weight_lb.get(key, settings.category_default_weight_lb[CATEGORY_STANDARD])
        source = "category_default"
    else:
        weight = float(weight_lb)
        source = "given"

    tiers = sorted(settings.shipping_weight_tiers, key=lambda t: t[0])
    tier_cost = tiers[-1][1] if tiers else 0.0
    for upper_bound, cost in tiers:
        if weight <= upper_bound:
            tier_cost = cost
            break

    pack_type = packaging_type or settings.category_default_packaging.get(key, PACKAGING_PADDED_POLY)
    pack_cost = settings.packaging_cost.get(pack_type, settings.packaging_cost.get(PACKAGING_PADDED_POLY, 0.0))

    return round(tier_cost + pack_cost, 2), round(tier_cost, 2), round(pack_cost, 2), source


def passes_min_thresholds(
    profit: Optional[float] = None,
    roi_pct: Optional[float] = None,
    cost: Optional[float] = None,
    settings: Optional[DealMathSettings] = None,
) -> Tuple[bool, List[str]]:
    """Item 8 -- threshold defaults ($10 min profit / 40% min ROI / editable
    max buy cost, all user-editable via `settings`).

    A standalone, explicitly-invoked gate (rather than baked into
    decision_policy's 70%-acquisition-rule engine) so opportunity-radar /
    holy-grail-style consumers can filter candidate deals by these
    thresholds without changing the already-tested BUY/PASS acquisition
    math. Looser min-profit filters beat tighter ones on hit rate AND
    profit per the simulation ($10 > $20 > $40) -- default reflects that.
    """
    settings = settings or DealMathSettings()
    reasons: List[str] = []
    ok = True
    if profit is not None and profit < settings.min_profit:
        ok = False
        reasons.append(f"Projected profit ${profit:.2f} is below the ${settings.min_profit:.2f} minimum profit threshold.")
    if roi_pct is not None and roi_pct < settings.min_roi_pct:
        ok = False
        reasons.append(f"Projected ROI {roi_pct:.1f}% is below the {settings.min_roi_pct:.1f}% minimum ROI threshold.")
    if settings.max_buy_cost is not None and cost is not None and cost > settings.max_buy_cost:
        ok = False
        reasons.append(f"Buy cost ${cost:.2f} exceeds the ${settings.max_buy_cost:.2f} max buy cost cap.")
    return ok, reasons


def key_attribute_for_category(category: Optional[str]) -> Optional[str]:
    if not category:
        return None
    key = str(category).strip().lower().replace(" ", "_").replace("-", "_")
    return CATEGORY_KEY_ATTRIBUTE.get(key)
