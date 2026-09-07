"""
Unit tests for finance.py - the pure money-math module behind every tab's
numbers. No Streamlit/pandas/network dependency, so these run anywhere:

    python3 -m unittest tests.test_finance -v
"""

import unittest

from finance import (
    GOLD_PURITY,
    LOW_MARGIN_PCT_THRESHOLD,
    LOW_MARGIN_PROFIT_THRESHOLD,
    MELT_CEILING_PCT,
    SILVER_PURITY,
    TROY_OZ_PER_GRAM,
    calc_deal,
    calc_melt,
    five_tier_verdict,
    format_roi,
    inventory_health,
    inventory_margin,
    max_cost_for_target_roi,
    sales_tax,
)


class TestFiveTierVerdict(unittest.TestCase):
    def test_strong_buy_at_and_above_60(self):
        self.assertEqual(five_tier_verdict(60)[0], "STRONG BUY")
        self.assertEqual(five_tier_verdict(100)[0], "STRONG BUY")
        self.assertEqual(five_tier_verdict(60)[1], "strong_buy")

    def test_buy_between_40_and_60(self):
        self.assertEqual(five_tier_verdict(40)[0], "BUY")
        self.assertEqual(five_tier_verdict(59.99)[0], "BUY")

    def test_at_ceiling_between_20_and_40(self):
        self.assertEqual(five_tier_verdict(20)[0], "AT CEILING")
        self.assertEqual(five_tier_verdict(39.99)[0], "AT CEILING")

    def test_borderline_between_5_and_20(self):
        self.assertEqual(five_tier_verdict(5)[0], "BORDERLINE")
        self.assertEqual(five_tier_verdict(19.99)[0], "BORDERLINE")

    def test_pass_below_5(self):
        self.assertEqual(five_tier_verdict(4.99)[0], "PASS")
        self.assertEqual(five_tier_verdict(0)[0], "PASS")
        self.assertEqual(five_tier_verdict(-50)[0], "PASS")

    def test_tiers_are_distinct(self):
        tiers = {five_tier_verdict(roi)[1] for roi in [75, 45, 25, 10, -10]}
        self.assertEqual(tiers, {"strong_buy", "buy", "at_ceiling", "borderline", "pass"})


class TestCalcDeal(unittest.TestCase):
    def test_normal_case_with_fees_and_premium(self):
        result = calc_deal(100, 250, fee_pct=13.0, premium_pct=18.0)
        self.assertAlmostEqual(result.true_cost, 118.0)
        self.assertAlmostEqual(result.net_resale, 217.5)
        self.assertAlmostEqual(result.gross_profit, 99.5)
        self.assertAlmostEqual(result.roi_pct, 99.5 / 118.0 * 100)

    def test_zero_fees_and_premium(self):
        result = calc_deal(100, 200, fee_pct=0, premium_pct=0)
        self.assertEqual(result.true_cost, 100)
        self.assertEqual(result.net_resale, 200)
        self.assertEqual(result.gross_profit, 100)
        self.assertEqual(result.roi_pct, 100.0)

    def test_free_find_is_infinite_roi_and_strong_buy(self):
        result = calc_deal(0, 100)
        self.assertEqual(result.roi_pct, float("inf"))
        self.assertEqual(result.verdict, "STRONG BUY")

    def test_zero_cost_zero_resale_never_divides_by_zero(self):
        result = calc_deal(0, 0)
        self.assertEqual(result.gross_profit, 0)
        self.assertEqual(result.roi_pct, 0.0)
        self.assertEqual(result.verdict, "PASS")

    def test_loss_scenario(self):
        result = calc_deal(100, 0)
        self.assertLess(result.gross_profit, 0)
        self.assertEqual(result.verdict, "PASS")

    def test_full_fee_wipes_out_resale_value(self):
        result = calc_deal(50, 100, fee_pct=100, premium_pct=0)
        self.assertEqual(result.net_resale, 0)
        self.assertEqual(result.gross_profit, -50)

    def test_verdict_scale_strong_buy(self):
        result = calc_deal(100, 400)
        self.assertEqual(result.verdict, "STRONG BUY")
        self.assertEqual(result.verdict_tier, "strong_buy")

    def test_verdict_scale_pass(self):
        result = calc_deal(100, 104)
        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.verdict_tier, "pass")


class TestMaxCostForTargetRoi(unittest.TestCase):
    def test_max_cost_hits_target_roi_exactly(self):
        max_cost = max_cost_for_target_roi(300, target_roi_pct=40.0, fee_pct=13.0, premium_pct=18.0)
        result = calc_deal(max_cost, 300, fee_pct=13.0, premium_pct=18.0)
        self.assertAlmostEqual(result.roi_pct, 40.0, places=4)

    def test_max_cost_is_less_than_resale_value(self):
        max_cost = max_cost_for_target_roi(300, target_roi_pct=40.0)
        self.assertGreater(max_cost, 0)
        self.assertLess(max_cost, 300)

    def test_impossible_target_roi_floors_at_zero(self):
        self.assertEqual(max_cost_for_target_roi(300, target_roi_pct=-150), 0.0)


class TestCalcMelt(unittest.TestCase):
    def test_troy_oz_per_gram_constant_is_correct(self):
        self.assertAlmostEqual(TROY_OZ_PER_GRAM, 1 / 31.1034768)

    def test_normal_melt_and_80_percent_ceiling(self):
        melt = calc_melt(weight_grams=10, purity_fraction=0.585, spot_price_per_oz=2000)
        self.assertGreater(melt.melt_value, 0)
        self.assertAlmostEqual(melt.ceiling_price / melt.melt_value, MELT_CEILING_PCT / 100, places=6)

    def test_zero_weight_is_zero_value(self):
        melt = calc_melt(0, 0.585, 2000)
        self.assertEqual(melt.melt_value, 0)
        self.assertEqual(melt.ceiling_price, 0)

    def test_zero_spot_price_is_zero_value(self):
        melt = calc_melt(10, 0.585, 0)
        self.assertEqual(melt.melt_value, 0)
        self.assertEqual(melt.ceiling_price, 0)

    def test_purity_scales_value_linearly(self):
        full = calc_melt(10, 1.0, 2000)
        half = calc_melt(10, 0.5, 2000)
        self.assertAlmostEqual(half.melt_value, full.melt_value / 2)

    def test_gold_purity_table_has_expected_karats(self):
        self.assertIn("24k (.999 fine)", GOLD_PURITY)
        self.assertIn("14k", GOLD_PURITY)
        self.assertEqual(GOLD_PURITY["24k (.999 fine)"], 0.999)

    def test_silver_purity_table_has_sterling(self):
        self.assertIn("Sterling (.925)", SILVER_PURITY)
        self.assertEqual(SILVER_PURITY["Sterling (.925)"], 0.925)


class TestFormatRoi(unittest.TestCase):
    def test_normal_roi(self):
        self.assertEqual(format_roi(45.5), "45.5%")

    def test_infinite_roi(self):
        self.assertIn("∞", format_roi(float("inf")))


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

    def test_default_fee_pct_is_13(self):
        _, net_default, _ = inventory_margin(cost_basis=40, list_price=120)
        _, net_explicit, _ = inventory_margin(cost_basis=40, list_price=120, fee_pct=13.0)
        self.assertAlmostEqual(net_default, net_explicit)

    def test_negative_margin_on_underwater_item(self):
        gross, net, margin_pct = inventory_margin(cost_basis=100, list_price=50, fee_pct=13)
        self.assertLess(gross, 0)
        self.assertLess(net, 0)
        self.assertLess(margin_pct, 0)


class TestInventoryHealth(unittest.TestCase):
    def test_healthy_above_both_thresholds(self):
        self.assertEqual(inventory_health(net_margin_pct=25, net_profit=20), "HEALTHY")

    def test_low_margin_below_pct_threshold(self):
        self.assertEqual(inventory_health(net_margin_pct=LOW_MARGIN_PCT_THRESHOLD - 0.01, net_profit=100), "LOW MARGIN")

    def test_low_margin_below_profit_threshold(self):
        self.assertEqual(inventory_health(net_margin_pct=50, net_profit=LOW_MARGIN_PROFIT_THRESHOLD - 0.01), "LOW MARGIN")

    def test_boundary_values_are_healthy(self):
        self.assertEqual(inventory_health(net_margin_pct=LOW_MARGIN_PCT_THRESHOLD, net_profit=LOW_MARGIN_PROFIT_THRESHOLD), "HEALTHY")


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
