"""
Unit tests for comps.py - the pure market-comps valuation math. No
Streamlit/pandas/network dependency, same convention as test_finance.py:

    python3 -m unittest tests.test_comps -v
"""

import unittest

from comps import (
    ACTIVE,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    SOLD,
    Comp,
    evaluate_with_comps,
    summarize_comps,
)


def sold(price, **kwargs):
    return Comp(price=price, listing_type=SOLD, **kwargs)


def active(price, **kwargs):
    return Comp(price=price, listing_type=ACTIVE, **kwargs)


class TestSummarizeComps(unittest.TestCase):
    def test_empty_list_returns_none(self):
        self.assertIsNone(summarize_comps([]))

    def test_single_sold_comp(self):
        summary = summarize_comps([sold(100)])
        self.assertEqual(summary.count, 1)
        self.assertEqual(summary.sold_count, 1)
        self.assertEqual(summary.suggested_value, 100)
        self.assertEqual(summary.confidence, CONFIDENCE_LOW)

    def test_median_of_sold_comps_used_as_suggested_value(self):
        comps = [sold(90), sold(100), sold(110), active(500)]
        summary = summarize_comps(comps)
        self.assertEqual(summary.suggested_value, 100)  # median of sold only, active excluded
        self.assertEqual(summary.sold_count, 3)
        self.assertEqual(summary.active_count, 1)

    def test_falls_back_to_all_comps_when_no_sold(self):
        comps = [active(90), active(110)]
        summary = summarize_comps(comps)
        self.assertEqual(summary.suggested_value, 100)  # median of active, since no sold
        self.assertEqual(summary.confidence, CONFIDENCE_LOW)
        self.assertIn("asking prices only", summary.confidence_reason)

    def test_shipping_added_to_price(self):
        summary = summarize_comps([sold(100, shipping=10)])
        self.assertEqual(summary.low, 110)
        self.assertEqual(summary.high, 110)

    def test_high_confidence_with_many_consistent_sold_comps(self):
        comps = [sold(p) for p in [98, 99, 100, 101, 102, 100, 99, 101]]
        summary = summarize_comps(comps)
        self.assertEqual(summary.confidence, CONFIDENCE_HIGH)

    def test_medium_confidence_with_a_few_sold_comps(self):
        comps = [sold(p) for p in [95, 100, 105]]
        summary = summarize_comps(comps)
        self.assertEqual(summary.confidence, CONFIDENCE_MEDIUM)

    def test_low_confidence_with_only_one_or_two_sold_comps(self):
        comps = [sold(95), sold(105)]
        summary = summarize_comps(comps)
        self.assertEqual(summary.confidence, CONFIDENCE_LOW)

    def test_wide_price_spread_caps_confidence_even_with_many_comps(self):
        # Ten "sold comps" that are actually wildly different items/conditions
        # lumped under one search term shouldn't read as high confidence.
        comps = [sold(p) for p in [10, 500, 20, 480, 15, 510, 25, 490, 30, 470]]
        summary = summarize_comps(comps)
        self.assertEqual(summary.confidence, CONFIDENCE_LOW)
        self.assertIn("vary too widely", summary.confidence_reason)

    def test_low_high_median_mean_across_all_comps_regardless_of_type(self):
        comps = [sold(100), active(200)]
        summary = summarize_comps(comps)
        self.assertEqual(summary.low, 100)
        self.assertEqual(summary.high, 200)
        self.assertEqual(summary.median, 150)
        self.assertEqual(summary.mean, 150)


class TestEvaluateWithComps(unittest.TestCase):
    def test_no_comps_returns_none(self):
        self.assertIsNone(evaluate_with_comps([], cost=50))

    def test_combines_market_evidence_with_finance_math(self):
        comps = [sold(100), sold(105), sold(95)]
        verdict = evaluate_with_comps(comps, cost=50, fee_pct=13.0, premium_pct=18.0)
        self.assertIsNotNone(verdict)
        self.assertEqual(verdict.comps_summary.suggested_value, 100)
        # Cross-check against finance.calc_deal directly rather than
        # hardcoding numbers, so this test breaks if the two ever drift.
        from finance import calc_deal
        expected_deal = calc_deal(50, 100, fee_pct=13.0, premium_pct=18.0)
        self.assertEqual(verdict.deal.gross_profit, expected_deal.gross_profit)
        self.assertEqual(verdict.deal.verdict, expected_deal.verdict)

    def test_floor_cost_is_positive_and_below_suggested_value(self):
        comps = [sold(100), sold(100), sold(100)]
        verdict = evaluate_with_comps(comps, cost=50, target_roi_pct=40.0)
        self.assertGreater(verdict.floor_cost, 0)
        self.assertLess(verdict.floor_cost, verdict.comps_summary.suggested_value)

    def test_underwater_deal_still_returns_a_verdict_not_an_error(self):
        comps = [sold(20)]
        verdict = evaluate_with_comps(comps, cost=100)
        self.assertLess(verdict.deal.gross_profit, 0)
        self.assertEqual(verdict.deal.verdict, "PASS")

    def test_zero_cost_free_find(self):
        comps = [sold(50)]
        verdict = evaluate_with_comps(comps, cost=0)
        self.assertEqual(verdict.deal.verdict, "STRONG BUY")


if __name__ == "__main__":
    unittest.main()
