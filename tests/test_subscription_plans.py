import unittest

from subscription_plans import feature_enabled, get_plan


class TestSubscriptionPlans(unittest.TestCase):
    def test_appraiser_is_flagship(self):
        # Renamed from "hunter" ($49) 2026-09-21 -- ties directly to the
        # product name and reads as professional/credentialed rather than
        # the "hunting" theme it replaces. See COMPETITIVE-GAPS.md.
        appraiser = get_plan("appraiser")
        self.assertEqual(appraiser.monthly_price, 59)
        self.assertTrue(appraiser.hunt_enabled)
        self.assertTrue(appraiser.alerts_enabled)
        self.assertTrue(appraiser.liquidation)
        self.assertTrue(appraiser.financial_intelligence)

    def test_free_is_restricted(self):
        self.assertFalse(feature_enabled("free", "holy_grail_hunt"))
        self.assertFalse(feature_enabled("free", "alerts"))

    def test_pro_has_team_access(self):
        self.assertTrue(feature_enabled("pro", "team"))
        self.assertEqual(get_plan("pro").team_seats, 5)


if __name__ == "__main__":
    unittest.main()
