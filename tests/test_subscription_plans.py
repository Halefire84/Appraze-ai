import unittest

from subscription_plans import feature_enabled, get_plan


class TestSubscriptionPlans(unittest.TestCase):
    def test_pro_is_flagship(self):
        pro = get_plan("pro")
        self.assertEqual(pro.monthly_price, 50)
        self.assertTrue(pro.hunt_enabled)
        self.assertTrue(pro.alerts_enabled)
        self.assertTrue(pro.liquidation)
        self.assertTrue(pro.batch_analysis)
        self.assertTrue(pro.priority)
        self.assertFalse(pro.financial_intelligence)

    def test_free_is_restricted(self):
        self.assertFalse(feature_enabled("free", "holy_grail_hunt"))
        self.assertFalse(feature_enabled("free", "alerts"))

    def test_business_has_team_access(self):
        self.assertTrue(feature_enabled("business", "team"))
        self.assertEqual(get_plan("business").team_seats, 3)

    def test_enterprise_has_team_access(self):
        self.assertTrue(feature_enabled("enterprise", "team"))
        self.assertEqual(get_plan("enterprise").team_seats, 10)
        self.assertEqual(get_plan("enterprise").monthly_price, 200)


if __name__ == "__main__":
    unittest.main()
