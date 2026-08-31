"""
Unit tests for finance.py - the pure money-math module behind every tab's
numbers. No Streamlit/pandas/network dependency, so these run anywhere:

    python3 -m unittest tests.test_finance -v
"""

import unittest

from finance import (
    GOLD_PURITY,
    SILVER_PURITY,
    TROY_OZ_PER_GRAM,
    compute_verdict,
    deal_roi,
    inventory_margin,
    max_bid_after_premium,
    melt_value,
    profit_calc,
    sales_tax,
)


class TestComputeVerdict(unittest.TestCase):
    def test_strong_buy_at_and_above_60(self):
        self.assertEqual(compute_verdict(60)[0], "STRONG BUY")
        self.assertEqual(compute_verdict(100)[0], "STRONG BUY")

    def test_buy_between_40_and_60(self):
        self.assertEqual(compute_verdict(40)[0], "BUY")
        self.assertEqual(compute_verdict(59.99)[0], "BUY")

    def test_at_ceiling_between_20_and_40(self):
        self.assertEqual(compute_verdict(20)[0], "AT CEILING")
        self.assertEqual(compute_verdict(39.99)[0], "AT CEILING")

    def test_borderline_between_5_and_20(self):
        self.assertEqual(compute_verdict(5)[0], "BORDERLINE")
        self.assertEqual(compute_verdict(19.99)[0], "BORDERLINE")

    def test_pass_below_5(self):
        self.assertEqual(compute_verdict(4.99)[0], "PASS")
        self.assertEqual(compute_verdict(0)[0], "PASS")
        self.assertEqual(compute_verdict(-50)[0], "PASS")

    def test_badge_classes_are_distinct_and_paired_correctly(self):
        expected = {
            "STRONG BUY": "badge-strongbuy",
            "BUY": "badge-buy",
            "AT CEILING": "badge-ceiling",
            "BORDERLINE": "badge-borderline",
            "PASS": "badge-passverdict",
        }
        for roi, (label, badge) in [
            (75, compute_verdict(75)),
            (45, compute_verdict(45)),
            (25, compute_verdict(25)),
            (10, compute_verdict(10)),
            (-10, compute_verdict(-10)),
        ]:
            self.assertEqual(badge, expected[label])


class TestDealRoi(unittest.TestCase):
    def test_normal_profit(self):
        profit, roi = deal_roi(100, 250)
        self.assertEqual(profit, 150)
        self.assertEqual(roi, 150.0)

    def test_loss(self):
        profit, roi = deal_roi(200, 150)
        self.assertEqual(profit, -50)
        self.assertEqual(roi, -25.0)

    def test_zero_cost_never_divides_by_zero(self):
        profit, roi = deal_roi(0, 100)
        self.assertEqual(profit, 100)
        self.assertEqual(roi, 0)

    def test_none_inputs_treated_as_zero(self):
        profit, roi = deal_roi(None, None)
        self.assertEqual(profit, 0)
        self.assertEqual(roi, 0)

    def test_break_even(self):
        profit, roi = deal_roi(100, 100)
        self.assertEqual(profit, 0)
        self.assertEqual(roi, 0.0)


class TestProfitCalc(unittest.TestCase):
    def test_normal_case_with_fees_and_premium(self):
        true_cost, net_resale, gross_profit, roi = profit_calc(100, 250, fee_pct=13.0, premium_pct=18.0)
        self.assertAlmostEqual(true_cost, 118.0)
        self.assertAlmostEqual(net_resale, 217.5)
        self.assertAlmostEqual(gross_profit, 99.5)
        self.assertAlmostEqual(roi, 99.5 / 118.0 * 100)

    def test_zero_fees_and_premium(self):
        true_cost, net_resale, gross_profit, roi = profit_calc(100, 200, fee_pct=0, premium_pct=0)
        self.assertEqual(true_cost, 100)
        self.assertEqual(net_resale, 200)
        self.assertEqual(gross_profit, 100)
        self.assertEqual(roi, 100.0)

    def test_zero_purchase_cost_never_divides_by_zero(self):
        true_cost, net_resale, gross_profit, roi = profit_calc(0, 100, fee_pct=10, premium_pct=0)
        self.assertEqual(true_cost, 0)
        self.assertEqual(roi, 0)

    def test_full_fee_wipes_out_resale_value(self):
        true_cost, net_resale, gross_profit, roi = profit_calc(50, 100, fee_pct=100, premium_pct=0)
        self.assertEqual(net_resale, 0)
        self.assertEqual(gross_profit, -50)


class TestInventoryMargin(unittest.TestCase):
    def test_normal_case(self):
        gross, net, margin_pct = inventory_margin(cost_basis=40, list_price=120, fee_pct=13)
        self.assertEqual(gross, 80)
        self.assertAlmostEqual(net, 120 - 40 - 15.6)
        self.assertAlmostEqual(margin_pct, (120 - 40 - 15.6) / 120 * 100)

    def test_zero_list_price_never_divides_by_zero(self):
        gross, net, margin_pct = inventory_margin(cost_basis=10, list_price=0, fee_pct=13)
        self.assertEqual(margin_pct, 0)

    def test_zero_fee(self):
        gross, net, margin_pct = inventory_margin(cost_basis=40, list_price=120, fee_pct=0)
        self.assertEqual(gross, 80)
        self.assertEqual(net, 80)
        self.assertAlmostEqual(margin_pct, 80 / 120 * 100)


class TestMeltValue(unittest.TestCase):
    def test_troy_oz_direct(self):
        value, ceiling = melt_value(spot_price_per_troy_oz=2000, weight=1, weight_unit="Troy oz", purity=1.0)
        self.assertEqual(value, 2000)
        self.assertEqual(ceiling, 1600)

    def test_grams_converted_to_troy_oz(self):
        value, ceiling = melt_value(spot_price_per_troy_oz=2000, weight=31.1035, weight_unit="Grams", purity=1.0)
        self.assertAlmostEqual(value, 2000, places=4)
        self.assertAlmostEqual(ceiling, 1600, places=4)

    def test_purity_scales_value_linearly(self):
        full, _ = melt_value(2000, 10, "Grams", purity=1.0)
        half, _ = melt_value(2000, 10, "Grams", purity=0.5)
        self.assertAlmostEqual(half, full / 2)

    def test_zero_weight(self):
        value, ceiling = melt_value(2000, 0, "Grams", 0.5833)
        self.assertEqual(value, 0)
        self.assertEqual(ceiling, 0)

    def test_gold_purity_table_has_expected_karats(self):
        self.assertIn("24k (.999 fine)", GOLD_PURITY)
        self.assertIn("14k", GOLD_PURITY)
        self.assertEqual(GOLD_PURITY["24k (.999 fine)"], 0.999)

    def test_silver_purity_table_has_sterling(self):
        self.assertIn("Sterling / 925", SILVER_PURITY)
        self.assertEqual(SILVER_PURITY["Sterling / 925"], 0.925)

    def test_troy_oz_per_gram_constant_is_correct(self):
        self.assertAlmostEqual(TROY_OZ_PER_GRAM, 1 / 31.1035)


class TestMaxBidAfterPremium(unittest.TestCase):
    def test_zero_premium_returns_ceiling_unchanged(self):
        self.assertEqual(max_bid_after_premium(1000, 0), 1000)

    def test_positive_premium_reduces_max_bid(self):
        result = max_bid_after_premium(1000, 18)
        self.assertAlmostEqual(result, 1000 / 1.18)
        self.assertLess(result, 1000)

    def test_never_divides_by_zero_for_any_nonnegative_premium(self):
        # (1 + premium_pct/100) >= 1 whenever premium_pct >= 0
        for premium in [0, 5, 18, 25, 100]:
            result = max_bid_after_premium(500, premium)
            self.assertGreater(result, 0)
            self.assertLessEqual(result, 500)


class TestSalesTax(unittest.TestCase):
    def test_normal_case(self):
        tax, total = sales_tax(100, 6.0)
        self.assertEqual(tax, 6.0)
        self.assertEqual(total, 106.0)

    def test_zero_tax_rate(self):
        tax, total = sales_tax(100, 0)
        self.assertEqual(tax, 0)
        self.assertEqual(total, 100)

    def test_zero_subtotal(self):
        tax, total = sales_tax(0, 9.0)
        self.assertEqual(tax, 0)
        self.assertEqual(total, 0)

    def test_max_combined_charleston_rate(self):
        tax, total = sales_tax(50, 9.0)
        self.assertAlmostEqual(tax, 4.5)
        self.assertAlmostEqual(total, 54.5)


if __name__ == "__main__":
    unittest.main()
