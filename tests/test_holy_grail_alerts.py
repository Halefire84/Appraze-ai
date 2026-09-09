import unittest

from alert_engine import AlertPolicy, alert_fingerprint, should_alert


class TestHolyGrailAlerts(unittest.TestCase):
    def test_fingerprint_is_stable(self):
        listing = {"source": "eBay", "source_listing_id": "123", "url": "https://example.com/123"}
        self.assertEqual(alert_fingerprint(listing), alert_fingerprint(dict(listing)))

    def test_holy_grail_threshold(self):
        policy = AlertPolicy()
        self.assertTrue(should_alert(95, set(), "eBay:123", policy))
        self.assertFalse(should_alert(94.9, set(), "eBay:123", policy))

    def test_dedupe(self):
        policy = AlertPolicy(min_score=85)
        self.assertFalse(should_alert(95, {"eBay:123"}, "eBay:123", policy))

    def test_lower_threshold(self):
        policy = AlertPolicy(min_score=85)
        self.assertTrue(should_alert(86, set(), "x", policy))


if __name__ == "__main__":
    unittest.main()
