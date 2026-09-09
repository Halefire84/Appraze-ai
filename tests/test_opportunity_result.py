import unittest

import finance
from opportunity_result import build_opportunity_result


class OpportunityResultTests(unittest.TestCase):
    def test_verdict_and_max_buy_price_come_from_finance_engine(self):
        result = build_opportunity_result({
            "title": "Vintage sterlling silver watch",
            "description": "Old watch, marked 925",
            "price": 40,
            "estimated_value": 300,
        })
        expected = finance.calc_deal(cost=40, resale_value=300)
        self.assertEqual(result.verdict, expected.verdict)
        self.assertEqual(result.max_buy_price, round(finance.max_cost_for_target_roi(300), 2))

    def test_no_value_evidence_leaves_verdict_and_max_buy_unset(self):
        result = build_opportunity_result({"title": "Mystery box", "price": 40})
        self.assertIsNone(result.verdict)
        self.assertIsNone(result.max_buy_price)

    def test_no_price_still_yields_max_buy_price_but_no_verdict(self):
        result = build_opportunity_result({"title": "Unlisted price item", "estimated_value": 300})
        self.assertIsNone(result.verdict)
        self.assertEqual(result.max_buy_price, round(finance.max_cost_for_target_roi(300), 2))

    def test_explicit_verdict_and_max_buy_price_are_not_overridden(self):
        result = build_opportunity_result(
            {"title": "Item", "price": 40, "estimated_value": 300},
            verdict="BORDERLINE",
            max_buy_price=99.0,
        )
        self.assertEqual(result.verdict, "BORDERLINE")
        self.assertEqual(result.max_buy_price, 99.0)

    def test_verdict_is_independent_of_radar_score(self):
        # A listing with no anomaly signals at all (clean title/description,
        # no typos, no bulk/lot terms) should still get a finance-driven
        # verdict purely from price vs. value evidence.
        result = build_opportunity_result({
            "title": "Standard used office chair in good condition",
            "description": "A normal item with a complete, accurate description.",
            "price": 40,
            "estimated_value": 300,
        })
        self.assertEqual(result.verdict, finance.calc_deal(cost=40, resale_value=300).verdict)


if __name__ == "__main__":
    unittest.main()
