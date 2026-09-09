import unittest

from crtc_hunt_engine import analyze_listing


class TestCRTCUnifiedHunt(unittest.TestCase):
    def test_information_failure_and_acquisition_brains_combine(self):
        result = analyze_listing({
            "source": "user_input",
            "title": "Dell laptop lot",
            "description": "2 Dell Latitude laptops, Intel i5-8365U, tested, chargers included",
            "category": "laptop",
            "price": 80,
            "current_bid": 80,
            "quantity": 2,
            "expected_resale": 350,
            "recovery_rate": 0.90,
            "tested": True,
            "condition": "tested",
            "cpu_generation": 8,
        })
        self.assertIn("holy_grail", result)
        self.assertIn("acquisition", result)
        self.assertGreaterEqual(result["combined_score"], 0)
        self.assertLessEqual(result["combined_score"], 100)

    def test_missing_risk_does_not_create_fake_value(self):
        result = analyze_listing({
            "source": "user_input",
            "title": "Unknown laptop lot",
            "description": "untested laptops",
            "category": "laptop",
            "price": 80,
            "current_bid": 80,
        })
        self.assertEqual(result["acquisition"]["economics"]["effective_resale"], 0.0)
        self.assertNotEqual(result["decision"], "BUY_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
