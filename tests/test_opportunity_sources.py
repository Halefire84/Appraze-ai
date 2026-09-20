import unittest
from unittest.mock import patch

from opportunity_sources import scan_ebay, scan_ebay_active


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


class ScanEbayActivePreservesRichListingsTests(unittest.TestCase):
    """Regression coverage for the fix: scan_ebay_active() used to rebuild
    its listing dicts from Comp objects (via fetch_comps()), which have no
    source_listing_id/description/category field -- every listing scanned
    this way collapsed onto the same blank identifier. It now uses
    fetch_listings() so those fields reach Opportunity Radar."""

    @patch("opportunity_sources.EbayBrowseAdapter")
    def test_source_listing_id_and_url_survive_into_the_ranked_candidate(self, mock_adapter_cls):
        mock_adapter_cls.return_value.fetch_listings.return_value = [
            {
                "source": "eBay",
                "source_listing_id": "v1|555|0",
                "url": "https://ebay.com/item/555",
                "title": "14k gold ring, seperate stones",  # deliberate typo for a nonzero score
                "description": "Solid 14k gold ring with three seperate gemstones.",
                "category": "Jewelry",
                "price": 45.0,
                "condition": "Used",
                "shipping": 4.0,
            }
        ]
        result = scan_ebay_active("14k gold ring", limit=10, min_score=0)
        self.assertEqual(result.fetched, 1)
        self.assertEqual(len(result.opportunities), 1)
        listing = result.opportunities[0].listing
        self.assertEqual(listing["source_listing_id"], "v1|555|0")
        self.assertEqual(listing["url"], "https://ebay.com/item/555")
        self.assertEqual(listing["description"], "Solid 14k gold ring with three seperate gemstones.")

    @patch("opportunity_sources.EbayBrowseAdapter")
    def test_two_listings_never_collapse_onto_the_same_identifier(self, mock_adapter_cls):
        mock_adapter_cls.return_value.fetch_listings.return_value = [
            {"source": "eBay", "source_listing_id": "A1", "url": "https://ebay.com/a", "title": "Item A", "price": 10.0},
            {"source": "eBay", "source_listing_id": "B2", "url": "https://ebay.com/b", "title": "Item B", "price": 20.0},
        ]
        result = scan_ebay_active("test", limit=10, min_score=0)
        ids = {c.listing["source_listing_id"] for c in result.opportunities}
        self.assertEqual(ids, {"A1", "B2"})

    @patch("opportunity_sources.EbayBrowseAdapter")
    def test_blank_query_does_not_call_the_adapter(self, mock_adapter_cls):
        result = scan_ebay_active("   ")
        mock_adapter_cls.return_value.fetch_listings.assert_not_called()
        self.assertEqual(result.fetched, 0)
        self.assertEqual(result.opportunities, [])

    @patch("opportunity_sources.EbayBrowseAdapter")
    def test_fetch_comps_is_not_called_by_scan_ebay_active(self, mock_adapter_cls):
        """fetch_comps() must be left for the Market Comps valuation path;
        scan_ebay_active() should only ever call fetch_listings() now."""
        mock_adapter_cls.return_value.fetch_listings.return_value = []
        scan_ebay_active("test")
        mock_adapter_cls.return_value.fetch_comps.assert_not_called()


if __name__ == "__main__":
    unittest.main()
