"""
Cooper River Trading Co. — Shared Business Math Module
--------------------------------------------------------
Deterministic finance/valuation rules used across every Appraze tab.

Deliberately free of Streamlit/UI code so it stays a single source of
truth: the AI Analyzer, the Profit Calculator, and the Melt Calculator
all call into these same functions rather than each re-implementing
the math (and drifting out of sync with each other).

Core business rules encoded here:
  - Five-tier verdict scale (Strong Buy / Buy / At Ceiling / Borderline / Pass)
  - CTBids buyer's premium default (18%)
  - Standard platform resale fee (13%)
  - Precious metals 80%-of-melt ceiling rule
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# CORE DEAL MATH
# ---------------------------------------------------------------------------

DEFAULT_FEE_PCT = 13.0        # marketplace / payment-processing resale fee
DEFAULT_PREMIUM_PCT = 18.0    # buyer's premium at purchase (CTBids default)


@dataclass
class DealResult:
    true_cost: float          # cost after buyer's premium
    net_resale: float         # resale value after platform fees
    gross_profit: float
    roi_pct: float
    verdict: str
    verdict_tier: str          # "strong_buy" | "buy" | "at_ceiling" | "borderline" | "pass"


def five_tier_verdict(roi_pct: float) -> tuple[str, str]:
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


def format_roi(roi_pct: float) -> str:
    """Display-friendly ROI string — handles the free-item (infinite ROI) case."""
    if roi_pct == float("inf"):
        return "∞ (free find)"
    return f"{roi_pct:,.1f}%"


def calc_deal(
    cost: float,
    resale_value: float,
    fee_pct: float = DEFAULT_FEE_PCT,
    premium_pct: float = DEFAULT_PREMIUM_PCT,
) -> DealResult:
    """
    Core deterministic profit calculation used everywhere in Appraze.

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


def max_cost_for_target_roi(
    resale_value: float,
    target_roi_pct: float = 40.0,
    fee_pct: float = DEFAULT_FEE_PCT,
    premium_pct: float = DEFAULT_PREMIUM_PCT,
) -> float:
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


# ---------------------------------------------------------------------------
# PRECIOUS METALS / MELT VALUE
# ---------------------------------------------------------------------------

GOLD_PURITY = {
    "24k (.999 fine)": 0.999,
    "22k": 0.9167,
    "21k": 0.8750,
    "18k": 0.7500,
    "14k": 0.5850,
    "12k": 0.5000,
    "10k": 0.4170,
    "9k": 0.3750,
}

SILVER_PURITY = {
    "Fine Silver (.999)": 0.999,
    "Sterling (.925)": 0.925,
    "Coin Silver (.900)": 0.900,
}

TROY_OZ_PER_GRAM = 1 / 31.1034768
MELT_CEILING_PCT = 80.0  # never pay/bid above 80% of true melt value


@dataclass
class MeltResult:
    troy_oz_total: float
    pure_troy_oz: float
    melt_value: float
    ceiling_price: float   # 80% of melt — max recommended bid/pay


def calc_melt(weight_grams: float, purity_fraction: float, spot_price_per_oz: float) -> MeltResult:
    """
    weight_grams:      total weight of the item, in grams
    purity_fraction:   e.g. 0.585 for 14k gold, 0.925 for sterling silver
    spot_price_per_oz: current spot price, $ per troy ounce
    """
    troy_oz_total = weight_grams * TROY_OZ_PER_GRAM
    pure_troy_oz = troy_oz_total * purity_fraction
    melt_value = pure_troy_oz * spot_price_per_oz
    ceiling_price = melt_value * (MELT_CEILING_PCT / 100)
    return MeltResult(troy_oz_total, pure_troy_oz, melt_value, ceiling_price)
