"""Regression tests for the 2026-09-21 decision-engine audit (see
DEAL-MATH.md). Each test maps to a specific, sourced finding from that
audit -- not the earlier F-01..F-17 simulation set in
test_p0_regression.py, which stays separate.
"""
from __future__ import annotations

from decision_policy import evaluate_deal, DECISION_BUY, DECISION_REVIEW


# ---------------------------------------------------------------------------
# Finding: purchase-side sales tax was not an explicit, named cost
# component -- a caller had to silently fold it into other_fees or omit
# it entirely. Many auction houses charge tax on hammer price + premium
# unless the buyer has a resale exemption certificate on file.
# ---------------------------------------------------------------------------
def test_purchase_tax_is_tracked_as_its_own_component_when_supplied():
    result = evaluate_deal(
        price=100.0,
        market_value=200.0,
        is_auction=True,
        buyer_premium_pct=18.0,
        shipping=10.0,
        purchase_tax=9.0,
    )
    tax_components = [c for c in result.cost_components if c.name == "purchase_tax"]
    assert len(tax_components) == 1
    assert tax_components[0].amount == 9.0
    assert tax_components[0].state == "KNOWN"


def test_purchase_tax_increases_all_in_cost_and_lowers_projected_roi():
    without_tax = evaluate_deal(
        price=100.0, market_value=200.0, is_auction=True,
        buyer_premium_pct=18.0, shipping=10.0,
    )
    with_tax = evaluate_deal(
        price=100.0, market_value=200.0, is_auction=True,
        buyer_premium_pct=18.0, shipping=10.0, purchase_tax=9.0,
    )
    assert with_tax.all_in_cost == without_tax.all_in_cost + 9.0
    assert with_tax.projected_roi_pct < without_tax.projected_roi_pct


def test_omitting_purchase_tax_keeps_prior_behavior_exactly_unchanged():
    # Backward compatibility: every existing caller that never passes
    # purchase_tax must see byte-identical results to before this
    # parameter existed. NOT_APPLICABLE, not UNKNOWN -- it must not flip
    # an existing BUY into a REVIEW just because a new optional param
    # exists and wasn't supplied.
    result = evaluate_deal(
        price=50.0, market_value=100.0, is_auction=True,
        buyer_premium_pct=10.0, shipping=5.0,
    )
    tax_components = [c for c in result.cost_components if c.name == "purchase_tax"]
    assert len(tax_components) == 1
    assert tax_components[0].state == "NOT_APPLICABLE"
    assert tax_components[0].amount == 0.0
    assert result.decision == DECISION_BUY


def test_purchase_tax_flows_through_build_deal_workspace_record():
    from decision_policy import build_deal_workspace_record
    listing = {
        "source": "hibid",
        "price": 100.0,
        "buyer_premium_pct": 18.0,
        "shipping": 10.0,
        "purchase_tax": 9.0,
    }
    out = build_deal_workspace_record(listing, market_value=200.0)
    tax_components = [c for c in out["cost_components"] if c["name"] == "purchase_tax"]
    assert tax_components[0]["amount"] == 9.0
