import unittest

from acquisition_hunter import estimate_max_bid, score_acquisition


class TestAcquisitionHunter(unittest.TestCase):
    def test_modern_laptop_profile(self):
        result = score_acquisition({
            "title": "Lot of Dell Latitude laptops",
            "condition": "tested",
            "tested": True,
            "cpu_generation": 10,
            "expected_resale": 1800,
            "recovery_rate": 0.85,
            "current_bid": 300,
            "buyer_premium": 30,
            "freight": 100,
        }, "modern_computers")
        self.assertIn("modern_cpu", result["signals"])
        self.assertGreater(result["economics"]["max_total_acquisition"], 0)

    def test_locked_phone_risk(self):
        result = score_acquisition({
            "title": "Mixed smartphones",
            "activation_lock": True,
            "expected_resale": 2000,
            "recovery_rate": 0.7,
            "current_bid": 100,
        }, "phones_tablets")
        self.assertIn("activation_lock", result["signals"])
        self.assertLess(result["score"], 70)

    def test_max_bid_accounts_for_costs_and_recovery(self):
        result = estimate_max_bid({
            "expected_resale": 1000,
            "recovery_rate": 0.8,
            "buyer_premium": 50,
            "tax": 50,
            "freight": 100,
            "repair_cost": 50,
            "current_bid": 300,
        })
        self.assertEqual(result["effective_resale"], 800.0)
        self.assertEqual(result["fixed_costs"], 250.0)
        self.assertEqual(result["max_total_acquisition"], 310.0)
        self.assertEqual(result["headroom"], 10.0)


if __name__ == "__main__":
    unittest.main()
