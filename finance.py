"""
finance.py — pure, testable financial math for Appraze.

Deliberately has zero dependency on Streamlit or pandas so it can be
unit-tested in isolation and imported safely from anywhere. This is where
all money-math logic should live going forward — the Streamlit UI code in
app.py should call into these functions rather than re-deriving the same
math inline in multiple tabs (that duplication is exactly what caused the
Deal Dashboard and Profit Calculator verdict scales to drift out of sync
with each other earlier in this project).

The block below `RESTORED CANONICAL DEAL/MELT ENGINE` reinstates the
symbols the CRTC valuation pipeline (comps.py and everything built on it)
depends on. A prior edit replaced this file's API without noticing those
callers, breaking Opportunity Radar / Auction Hunt / Holy Grail Finder at
import time. Nothing above this block was changed — app.py's Dashboard,
Profit Calculator, Inventory, and Melt Calculator tabs keep working exactly
as they do today.
"""

from dataclasses import dataclass

TROY_OZ_PER_GRAM = 1 / 31.1035

GOLD_PURITY = {
    "24k (.999 fine)": 0.999, "22k": 0.9167, "21k": 0.875, "18k": 0.75,
    "14k": 0.5833, "12k": 0.5, "10k": 0.4167, "9k": 0.375,
}
SILVER_PURITY = {
    "Sterling / 925": 0.925, "Coin Silver / 900": 0.900, "Fine Silver / 999": 0.999,
    # Backwards-compatible alias for the pre-rewrite label — same 92.5%
    # sterling purity, not a second calculation. Kept out of app.py's own
    # dict construction order above so the live UI's default/first option
    # is unaffected; callers keyed to the old label still resolve correctly.
    "Sterling (.925)": 0.925,
}


def compute_verdict(roi_pct):
    """Cooper River Trading Co.'s real 5-tier deal verdict scale, based on ROI %.
    Returns (label, css_badge_class)."""
    if roi_pct >= 60:
        return "STRONG BUY", "badge-strongbuy"
    elif roi_pct >= 40:
        return "BUY", "badge-buy"
    elif roi_pct >= 20:
        return "AT CEILING", "badge-ceiling"
    elif roi_pct >= 5:
        return "BORDERLINE", "badge-borderline"
    else:
        return "PASS", "badge-passverdict"


def deal_roi(cost, resale_value):
    """Gross profit and ROI % for a simple cost/resale pair (used by the Deal
    Dashboard table). Returns (gross_profit, roi_pct). Never divides by zero."""
    cost = cost or 0
    resale_value = resale_value or 0
    gross_profit = resale_value - cost
    roi_pct = (gross_profit / cost * 100) if cost > 0 else 0
    return gross_profit, roi_pct


def profit_calc(purchase_cost, expected_resale, fee_pct, premium_pct):
    """The standalone Profit Calculator's math: buyer's premium on the way in,
    platform fees on the way out. Returns (true_cost, net_resale, gross_profit, roi_pct)."""
    true_cost = purchase_cost * (1 + premium_pct / 100)
    net_resale = expected_resale * (1 - fee_pct / 100)
    gross_profit = net_resale - true_cost
    roi_pct = (gross_profit / true_cost * 100) if true_cost > 0 else 0
    return true_cost, net_resale, gross_profit, roi_pct


def inventory_margin(cost_basis, list_price, fee_pct=13.0):
    """Inventory tab math: gross profit, fee-adjusted net profit, and net margin %.
    Returns (gross_profit, net_profit, net_margin_pct). Default fee_pct added for
    the canonical engine's callers below; app.py always passes fee_pct explicitly,
    so this default changes nothing for it."""
    gross_profit = list_price - cost_basis
    net_profit = list_price - cost_basis - (list_price * fee_pct / 100)
    net_margin_pct = (net_profit / list_price * 100) if list_price > 0 else 0
    return gross_profit, net_profit, net_margin_pct


def melt_value(spot_price_per_troy_oz, weight, weight_unit, purity):
    """Raw melt value of a gold/silver item. weight_unit is 'Grams' or 'Troy oz'.
    Returns (melt_value, ceiling_80). Never raises on zero/negative inputs."""
    if weight_unit == "Troy oz":
        weight_troy_oz = weight
    else:
        weight_troy_oz = weight * TROY_OZ_PER_GRAM
    value = spot_price_per_troy_oz * weight_troy_oz * purity
    ceiling_80 = value * 0.80
    return value, ceiling_80


def max_bid_after_premium(ceiling_80, premium_pct):
    """The actual max bid to stay within the 80% ceiling once a buyer's
    premium is added at purchase. Premium can never make this divide by zero
    since (1 + premium_pct/100) is always >= 1 for premium_pct >= 0."""
    return ceiling_80 / (1 + premium_pct / 100)


def sales_tax(subtotal, tax_rate_pct):
    """POS checkout math: tax amount and grand total on a cart subtotal.
    South Carolina's base state rate is 6% (verified 2026); local county
    add-ons can push the combined rate up to 9% depending on delivery
    address, so this is deliberately a plain input, not a hardcoded constant.
    Returns (tax_amount, total)."""
    tax_amount = subtotal * (tax_rate_pct / 100)
    total = subtotal + tax_amount
    return tax_amount, total


# ---------------------------------------------------------------------------
# RESTORED CANONICAL DEAL/MELT ENGINE
# ---------------------------------------------------------------------------
# comps.py (and everything built on it: comps_adapters, opportunity_sources,
# valuation_bridge, auction_radar, crtc_holy_grail, ebay_holy_grail,
# ebay_image_scan, plus the pages that import them) depends on this exact
# API. It is copied verbatim from the finance.py version these callers were
# written and tested against (git commit d093b60) rather than re-derived,
# so the math is provably the same math the existing test suite
# (tests/test_finance.py, tests/test_smoke.py) already verifies.

DEFAULT_FEE_PCT = 13.0        # marketplace / payment-processing resale fee
DEFAULT_PREMIUM_PCT = 18.0    # buyer's premium at purchase (CTBids default)

DEFAULT_INVENTORY_FEE_PCT = 13.0
LOW_MARGIN_PCT_THRESHOLD = 20.0
LOW_MARGIN_PROFIT_THRESHOLD = 15.0

MELT_CEILING_PCT = 80.0  # never pay/bid above 80% of true melt value


@dataclass
class DealResult:
    true_cost: float          # cost after buyer's premium
    net_resale: float         # resale value after platform fees
    gross_profit: float
    roi_pct: float
    verdict: str
    verdict_tier: str          # "strong_buy" | "buy" | "at_ceiling" | "borderline" | "pass"


@dataclass
class MeltResult:
    troy_oz_total: float
    pure_troy_oz: float
    melt_value: float
    ceiling_price: float   # 80% of melt — max recommended bid/pay


def five_tier_verdict(roi_pct):
    """CRTC's five-tier verdict scale, keyed off ROI%."""
    roi_pct = round(roi_pct, 6)  # guard against float precision landing just under a tier boundary
    if roi_pct >= 60:
        return "STRONG BUY", "strong_buy"
    elif roi_pct >= 40:
        return "BUY", "buy"
    elif roi_pct >= 20:
        return "AT CEILING", "at_ceiling"
    elif roi_pct >= 5:
        return "BORDERLINE", "borderline"
    else:
        return "PASS", "pass"


def format_roi(roi_pct):
    """Display-friendly ROI string — handles the free-item (infinite ROI) case."""
    if roi_pct == float("inf"):
        return "∞ (free find)"
    return f"{roi_pct:,.1f}%"


def calc_deal(cost, resale_value, fee_pct=DEFAULT_FEE_PCT, premium_pct=DEFAULT_PREMIUM_PCT):
    """
    Core deterministic profit calculation the CRTC valuation pipeline runs
    every candidate through via comps.evaluate_with_comps().

    cost:          hammer price / purchase price BEFORE buyer's premium
    resale_value:  expected sale price BEFORE platform fees
    fee_pct:       platform resale fee, e.g. eBay/Mercari ~13%
    premium_pct:   buyer's premium at purchase, e.g. CTBids 18%
    """
    true_cost = cost * (1 + premium_pct / 100)
    net_resale = resale_value * (1 - fee_pct / 100)
    gross_profit = net_resale - true_cost

    if true_cost > 0:
        roi_pct = gross_profit / true_cost * 100
    elif gross_profit > 0:
        # Free/curbside find (cost = $0) with real resale value — pure upside,
        # not "0% ROI". Treat as effectively unbounded so it lands Strong Buy.
        roi_pct = float("inf")
    else:
        roi_pct = 0.0

    verdict, tier = five_tier_verdict(roi_pct)
    return DealResult(true_cost, net_resale, gross_profit, roi_pct, verdict, tier)


def max_cost_for_target_roi(resale_value, target_roi_pct=40.0, fee_pct=DEFAULT_FEE_PCT, premium_pct=DEFAULT_PREMIUM_PCT):
    """
    'Floor cost' — the maximum purchase/bid price (BEFORE premium) that still
    hits target_roi_pct. Default target is 40%, the CRTC "Buy" tier floor.

    Inverse of calc_deal(): given a resale value, solve for the cost that
    produces exactly the target ROI.
    """
    net_resale = resale_value * (1 - fee_pct / 100)
    if target_roi_pct <= -100:
        return 0.0
    true_cost = net_resale / (1 + target_roi_pct / 100)
    max_cost = true_cost / (1 + premium_pct / 100)
    return max(0.0, max_cost)


def calc_melt(weight_grams, purity_fraction, spot_price_per_oz):
    """
    weight_grams:      total weight of the item, in grams
    purity_fraction:   e.g. 0.585 for 14k gold, 0.925 for sterling silver
    spot_price_per_oz: current spot price, $ per troy ounce
    """
    troy_oz_total = weight_grams * TROY_OZ_PER_GRAM
    pure_troy_oz = troy_oz_total * purity_fraction
    melt_val = pure_troy_oz * spot_price_per_oz
    ceiling_price = melt_val * (MELT_CEILING_PCT / 100)
    return MeltResult(troy_oz_total, pure_troy_oz, melt_val, ceiling_price)


def inventory_health(net_margin_pct, net_profit):
    """CRTC inventory health flag: "LOW MARGIN" below 20% margin OR below
    $15 net profit, otherwise "HEALTHY"."""
    if net_margin_pct < LOW_MARGIN_PCT_THRESHOLD or net_profit < LOW_MARGIN_PROFIT_THRESHOLD:
        return "LOW MARGIN"
    return "HEALTHY"
