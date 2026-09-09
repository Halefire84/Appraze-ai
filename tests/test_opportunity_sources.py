import unittest
from unittest.mock import patch

from comps import Comp
from opportunity_sources import scan_ebay


class OpportunitySourceTests(unittest.TestCase):
    @patch("opportunity_sources.EbayBrowseAdapter.fetch_comps")
    def test_ebay_results_are_normalized_and_ranked(self, fetch):
        fetch.return_value = [
            Comp(
                price=40,
                source="eBay",
                listing_type="active",
                condition="Used",
                shipping=0,
                listing_date=None,
                title="Vintage sterlling silver watch",
                url="https://example.com/1",
            ),
            Comp(
                price=100,
                source="eBay",
                listing_type="active",
                condition="Used",
                shipping=10,
                listing_date=None,
                title="Ordinary watch",
                url="https://example.com/2",
            ),
        ]
        result = scan_ebay("silver watch", limit=10, min_score=0)
        self.assertEqual(result.fetched, 2)
        self.assertEqual(result.source, "eBay")
        self.assertEqual(result.opportunities[0].listing["title"], "Vintage sterlling silver watch")
        self.assertGreaterEqual(result.opportunities[0].score, result.opportunities[-1].score)

    def test_blank_query_does_not_call_adapter(self):
        with patch("opportunity_sources.EbayBrowseAdapter.fetch_comps") as fetch:
            result = scan_ebay("   ")
        fetch.assert_not_called()
        self.assertEqual(result.fetched, 0)
        self.assertEqual(result.opportunities, [])


if __name__ == "__main__":
    unittest.main()
