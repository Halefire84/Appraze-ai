import unittest

from subscription_plans import PLANS, feature_enabled, get_plan


class TestSubscriptionPlans(unittest.TestCase):
    def test_appraiser_is_flagship(self):
        appraiser = get_plan("appraiser")
        self.assertEqual(appraiser.monthly_price, 59)
        self.assertTrue(appraiser.hunt_enabled)
        self.assertTrue(appraiser.alerts_enabled)
        self.assertTrue(appraiser.liquidation)
        self.assertTrue(appraiser.financial_intelligence)

    def test_analyst_sits_between_scout_and_appraiser(self):
        scout = get_plan("scout")
        analyst = get_plan("analyst")
        appraiser = get_plan("appraiser")
        self.assertGreater(analyst.monthly_price, scout.monthly_price)
        self.assertLess(analyst.monthly_price, appraiser.monthly_price)
        self.assertGreater(analyst.analyses_per_month, scout.analyses_per_month)
        self.assertLess(analyst.analyses_per_month, appraiser.analyses_per_month)
        # Analyst unlocks advanced sources but not the top-tier features yet.
        self.assertTrue(analyst.advanced_sources)
        self.assertFalse(analyst.liquidation)
        self.assertFalse(analyst.batch_analysis)

    def test_no_dot99_pricing_anywhere(self):
        # Deliberate brand choice -- round-dollar pricing reads as premium,
        # not discount-bin. See subscription_plans.py's module docstring.
        for plan in PLANS:
            self.assertEqual(plan.monthly_price, int(plan.monthly_price))

    def test_free_is_restricted(self):
        self.assertFalse(feature_enabled("free", "holy_grail_hunt"))
        self.assertFalse(feature_enabled("free", "alerts"))

    def test_pro_has_team_access(self):
        self.assertTrue(feature_enabled("pro", "team"))
        self.assertEqual(get_plan("pro").team_seats, 5)


if __name__ == "__main__":
    unittest.main()
