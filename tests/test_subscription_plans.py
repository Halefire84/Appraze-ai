import unittest

from subscription_plans import feature_enabled, get_plan


class TestSubscriptionPlans(unittest.TestCase):
    def test_hunter_is_flagship(self):
        hunter = get_plan("hunter")
        self.assertEqual(hunter.monthly_price, 49)
        self.assertTrue(hunter.hunt_enabled)
        self.assertTrue(hunter.alerts_enabled)
        self.assertTrue(hunter.liquidation)
        self.assertTrue(hunter.financial_intelligence)

    def test_free_is_restricted(self):
        self.assertFalse(feature_enabled("free", "holy_grail_hunt"))
        self.assertFalse(feature_enabled("free", "alerts"))

    def test_pro_has_team_access(self):
        self.assertTrue(feature_enabled("pro", "team"))
        self.assertEqual(get_plan("pro").team_seats, 5)


if __name__ == "__main__":
    unittest.main()
