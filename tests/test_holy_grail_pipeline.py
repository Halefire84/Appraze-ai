import unittest

import finance
from holy_grail_pipeline import opportunity_summary, rank_opportunities, score_listing


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

    def test_candidate_carries_finance_verdict_and_max_buy_price(self):
        candidate = score_listing({
            "title": "Vintage sterlling silver watch",
            "price": 40,
            "estimated_value": 300,
        })
        self.assertEqual(candidate.verdict, finance.calc_deal(cost=40, resale_value=300).verdict)
        self.assertEqual(candidate.max_buy_price, round(finance.max_cost_for_target_roi(300), 2))
        self.assertEqual(opportunity_summary(candidate)["verdict"], candidate.verdict)
        self.assertEqual(opportunity_summary(candidate)["max_buy_price"], candidate.max_buy_price)

    def test_candidate_without_value_evidence_has_no_verdict(self):
        candidate = score_listing({"title": "Normal item", "price": 100})
        self.assertIsNone(candidate.verdict)
        self.assertIsNone(candidate.max_buy_price)


if __name__ == "__main__":
    unittest.main()
