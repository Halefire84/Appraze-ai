"""Regression tests for decision_policy.evaluate_deal()'s financial input
boundary: NaN / Infinity / negative / boolean / malformed inputs must never
produce a BUY-family decision (BUY, STRONG BUY, AT CEILING, CONDITIONAL BUY).

tests/test_p0_regression.py already covers NaN/Inf/negative price and
market_value directly. This file covers the cost-component inputs
(buyer_premium_pct, shipping, other_fees) and boolean-as-number, which were
not previously exercised through evaluate_deal().
"""
import math
import unittest

from decision_policy import (
    DECISION_BORDERLINE,
    DECISION_BUY,
    DECISION_CONDITIONAL_BUY,
    DECISION_PASS,
    DECISION_REVIEW,
    DECISION_STRONG_BUY,
    evaluate_deal,
)

_BUY_FAMILY = {DECISION_BUY, DECISION_STRONG_BUY, DECISION_CONDITIONAL_BUY}


class TestNegativeCostComponentsNeverReduceAllInCost(unittest.TestCase):
    """A negative premium/shipping/fee must not silently shrink all_in cost
    below price -- that would manufacture a favorable decision out of
    malformed input, the same class of bug as an unvalidated negative price."""

    def test_negative_buyer_premium_pct_does_not_produce_buy(self):
        d = evaluate_deal(
            price=140.0, market_value=200.0, is_auction=True,
            buyer_premium_pct=-50.0, shipping=5.0, require_shipping=True,
        )
        self.assertNotIn(d.decision, _BUY_FAMILY)
        self.assertTrue(any("negative" in w.lower() for w in d.warnings))

    def test_negative_shipping_does_not_produce_buy(self):
        d = evaluate_deal(
            price=140.0, market_value=200.0, is_auction=True,
            buyer_premium_pct=18.0, shipping=-25.0, require_shipping=True,
        )
        self.assertNotIn(d.decision, _BUY_FAMILY)
        self.assertTrue(any("negative" in w.lower() for w in d.warnings))

    def test_negative_other_fees_does_not_produce_buy(self):
        # other_fees only gates the decision boundary on auction listings
        # (max_bid_or_price subtracts fixed = shipping + other_fees there);
        # for non-auction listings only price vs. target_all_in matters, so
        # this must be an auction case to actually exercise the boundary.
        d = evaluate_deal(
            price=120.0, market_value=100.0, is_auction=True,
            buyer_premium_pct=0.0, shipping=0.0, other_fees=-100.0,
            require_shipping=True,
        )
        self.assertNotIn(d.decision, _BUY_FAMILY)
        self.assertTrue(any("negative" in w.lower() for w in d.warnings))

    def test_all_in_cost_never_drops_below_price_from_negative_inputs(self):
        d = evaluate_deal(
            price=100.0, market_value=500.0, is_auction=True,
            buyer_premium_pct=-90.0, shipping=-40.0, require_shipping=True,
        )
        if d.all_in_cost is not None:
            self.assertGreaterEqual(d.all_in_cost, 100.0)


class TestBooleanAsNumberNeverBuys(unittest.TestCase):
    def test_boolean_price_is_never_buy(self):
        d = evaluate_deal(price=True, market_value=100.0, is_auction=False, require_shipping=False)
        self.assertNotIn(d.decision, _BUY_FAMILY)

    def test_boolean_market_value_is_never_buy(self):
        d = evaluate_deal(price=50.0, market_value=False, is_auction=False, require_shipping=False)
        self.assertNotIn(d.decision, _BUY_FAMILY)

    def test_boolean_buyer_premium_is_never_buy(self):
        d = evaluate_deal(
            price=50.0, market_value=200.0, is_auction=True,
            buyer_premium_pct=True, shipping=5.0, require_shipping=True,
        )
        self.assertNotIn(d.decision, _BUY_FAMILY)


class TestOverflowAndZeroEdgeCases(unittest.TestCase):
    def test_huge_price_does_not_crash_and_is_not_buy(self):
        d = evaluate_deal(price=1e18, market_value=100.0, is_auction=False, require_shipping=False)
        self.assertNotIn(d.decision, _BUY_FAMILY)

    def test_huge_market_value_does_not_crash(self):
        d = evaluate_deal(price=100.0, market_value=1e18, is_auction=False, require_shipping=False)
        self.assertIsNotNone(d.decision)
        self.assertTrue(math.isfinite(d.acquisition_target_all_in))

    def test_zero_price_zero_value_does_not_crash(self):
        d = evaluate_deal(price=0.0, market_value=0.0, is_auction=False, require_shipping=False)
        self.assertNotIn(d.decision, {DECISION_BUY, DECISION_STRONG_BUY})


class TestNonAuctionMaxPriceNeverNegative(unittest.TestCase):
    """The non-auction branch must clamp max_bid_or_price at zero like the
    auction branch does -- a max buy price can never go negative, even when
    known costs exceed the 70% acquisition target."""

    def test_non_auction_max_price_clamped_at_zero_when_costs_exceed_target(self):
        # 70% of $50 market value = $35 target, but $50 shipping + $10 fees
        # = $60 known costs exceed it: unclamped this yields -$25.
        d = evaluate_deal(
            price=10.0, market_value=50.0, is_auction=False,
            shipping=50.0, other_fees=10.0, require_shipping=True,
        )
        self.assertIsNotNone(d.max_bid_or_price)
        self.assertEqual(d.max_bid_or_price, 0.0)
        self.assertGreaterEqual(d.max_bid_or_price, 0.0)


if __name__ == "__main__":
    unittest.main()
