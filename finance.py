"""
finance.py — pure, testable financial math for Appraze.

Deliberately has zero dependency on Streamlit or pandas so it can be
unit-tested in isolation and imported safely from anywhere. This is where
all money-math logic should live going forward — the Streamlit UI code in
app.py should call into these functions rather than re-deriving the same
math inline in multiple tabs (that duplication is exactly what caused the
Deal Dashboard and Profit Calculator verdict scales to drift out of sync
with each other earlier in this project).
"""

TROY_OZ_PER_GRAM = 1 / 31.1035

GOLD_PURITY = {
    "24k (.999 fine)": 0.999, "22k": 0.9167, "21k": 0.875, "18k": 0.75,
    "14k": 0.5833, "12k": 0.5, "10k": 0.4167, "9k": 0.375,
}
SILVER_PURITY = {
    "Sterling / 925": 0.925, "Coin Silver / 900": 0.900, "Fine Silver / 999": 0.999,
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


def inventory_margin(cost_basis, list_price, fee_pct):
    """Inventory tab math: gross profit, fee-adjusted net profit, and net margin %.
    Returns (gross_profit, net_profit, net_margin_pct)."""
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
