import unittest
from unittest.mock import patch

from opportunity_sources import scan_ebay


class OpportunitySourceTests(unittest.TestCase):
    @patch("ebay_holy_grail._fetch")
    @patch("ebay_holy_grail.datetime")
    def test_ebay_last_chance_filters_by_price_and_end_time(self, mock_datetime, fetch):
        from datetime import datetime, timezone
        now = datetime(2026, 9, 9, 6, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        fetch.return_value = [
            {
                "itemId": "1", "title": "Vintage sterlling silver watch",
                "price": {"value": "40"}, "itemWebUrl": "https://example.com/1",
                "itemEndDate": "2026-09-09T12:00:00Z", "condition": "Used",
            },
            {
                "itemId": "2", "title": "Too expensive",
                "price": {"value": "151"}, "itemWebUrl": "https://example.com/2",
                "itemEndDate": "2026-09-09T10:00:00Z",
            },
            {
                "itemId": "3", "title": "Too late",
                "price": {"value": "20"}, "itemWebUrl": "https://example.com/3",
                "itemEndDate": "2026-09-10T07:00:01Z",
            },
        ]
        result = scan_ebay("silver watch", limit=10, min_score=0)
        self.assertEqual(result.source, "eBay")
        self.assertEqual(result.fetched, 1)
        self.assertEqual(len(result.opportunities), 1)
        self.assertEqual(result.opportunities[0].listing["title"], "Vintage sterlling silver watch")

    def test_blank_query_does_not_call_network(self):
        with patch("ebay_holy_grail._fetch") as fetch:
            result = scan_ebay("   ")
        fetch.assert_not_called()
        self.assertEqual(result.fetched, 0)
        self.assertEqual(result.opportunities, [])


if __name__ == "__main__":
    unittest.main()
