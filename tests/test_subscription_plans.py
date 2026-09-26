import unittest

from subscription_plans import PLANS, feature_enabled, get_plan


class TestSubscriptionPlans(unittest.TestCase):
    def test_old_plan_names_are_gone(self):
        # Full pricing replacement 2026-09-22 -- none of the retired plan
        # keys/names should resolve to anything real.
        for retired_key in ("scout", "hunter", "analyst", "appraiser", "operator"):
            self.assertEqual(get_plan(retired_key).key, "free")  # unknown key falls back to Free
        names = {p.name.lower() for p in PLANS}
        for retired_name in ("scout", "hunter", "analyst", "appraiser", "operator"):
            self.assertNotIn(retired_name, names)

    def test_free_is_heavily_limited(self):
        free = get_plan("free")
        self.assertEqual(free.monthly_price, 0)
        self.assertEqual(free.analyses_per_month, 5)
        self.assertFalse(feature_enabled("free", "holy_grail_hunt"))
        self.assertFalse(feature_enabled("free", "alerts"))
        self.assertFalse(feature_enabled("free", "inventory_tracking"))
        self.assertIsNone(free.prepay_3mo)
        self.assertIsNone(free.prepay_6mo)

    def test_starter_pricing_and_features(self):
        starter = get_plan("starter")
        self.assertEqual(starter.monthly_price, 25)
        self.assertEqual(starter.analyses_per_month, 50)
        self.assertTrue(starter.hunt_enabled)
        self.assertTrue(starter.alerts_enabled)
        self.assertTrue(starter.inventory_tracking)
        self.assertFalse(starter.advanced_sources)
        self.assertFalse(starter.financial_intelligence)
        self.assertEqual(starter.prepay_3mo, 50)
        self.assertEqual(starter.prepay_6mo, 100)

    def test_pro_is_starter_plus_advanced_sources_and_batch(self):
        pro = get_plan("pro")
        self.assertEqual(pro.monthly_price, 50)
        self.assertEqual(pro.analyses_per_month, 250)
        # everything Starter has
        self.assertTrue(pro.hunt_enabled)
        self.assertTrue(pro.alerts_enabled)
        self.assertTrue(pro.inventory_tracking)
        # plus Pro's own additions
        self.assertTrue(pro.advanced_sources)
        self.assertTrue(pro.liquidation)
        self.assertTrue(pro.batch_analysis)
        self.assertTrue(pro.priority)
        self.assertFalse(pro.financial_intelligence)  # Business+ only
        self.assertEqual(pro.prepay_3mo, 100)
        self.assertEqual(pro.prepay_6mo, 200)

    def test_business_is_pro_plus_team_and_financial_intelligence(self):
        business = get_plan("business")
        self.assertEqual(business.monthly_price, 100)
        self.assertEqual(business.analyses_per_month, 1000)
        self.assertTrue(business.advanced_sources)
        self.assertTrue(business.batch_analysis)
        self.assertTrue(business.financial_intelligence)
        self.assertEqual(business.team_seats, 3)
        self.assertTrue(feature_enabled("business", "team"))
        self.assertEqual(business.prepay_3mo, 200)
        self.assertEqual(business.prepay_6mo, 400)

    def test_enterprise_is_business_plus_more_seats(self):
        enterprise = get_plan("enterprise")
        self.assertEqual(enterprise.monthly_price, 200)
        self.assertEqual(enterprise.analyses_per_month, 5000)
        self.assertTrue(enterprise.financial_intelligence)
        self.assertEqual(enterprise.team_seats, 10)
        self.assertEqual(enterprise.prepay_3mo, 400)
        self.assertEqual(enterprise.prepay_6mo, 800)

    def test_prepay_is_roughly_thirty_percent_off(self):
        for plan in PLANS:
            if plan.prepay_3mo is None:
                continue
            three_month_full_price = plan.monthly_price * 3
            six_month_full_price = plan.monthly_price * 6
            discount_3mo = 1 - (plan.prepay_3mo / three_month_full_price)
            discount_6mo = 1 - (plan.prepay_6mo / six_month_full_price)
            self.assertAlmostEqual(discount_3mo, 1 / 3, delta=0.05, msg=plan.key)
            self.assertAlmostEqual(discount_6mo, 1 / 3, delta=0.05, msg=plan.key)

    def test_all_prices_are_round_numbers(self):
        # No ".99" endings anywhere in the new lineup, monthly or prepay.
        for plan in PLANS:
            self.assertEqual(plan.monthly_price, int(plan.monthly_price))
            if plan.prepay_3mo is not None:
                self.assertEqual(plan.prepay_3mo, int(plan.prepay_3mo))
                self.assertEqual(plan.prepay_6mo, int(plan.prepay_6mo))


if __name__ == "__main__":
    unittest.main()
