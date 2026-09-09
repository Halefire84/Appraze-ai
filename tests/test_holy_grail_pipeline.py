import unittest

from holy_grail_pipeline import rank_opportunities, score_listing


class HolyGrailPipelineTests(unittest.TestCase):
    def test_normalizes_and_scores_listing(self):
        candidate = score_listing({
            "name": "Vintage sterlling silver watch",
            "details": "Old watch, marked 925",
            "asking_price": 40,
            "url": "https://example.com/item/1",
            "category": "Jewelry",
        })
        self.assertEqual(candidate.listing["source_url"], "https://example.com/item/1")
        self.assertGreaterEqual(candidate.score, 25)
        self.assertTrue(candidate.review)

    def test_ranking_is_descending(self):
        results = rank_opportunities([
            {"title": "Normal item", "price": 100},
            {"title": "Vintage sterlling silver", "price": 20, "estimated_value": 300},
        ])
        self.assertGreaterEqual(results[0].score, results[-1].score)


if __name__ == "__main__":
    unittest.main()
