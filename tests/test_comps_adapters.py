"""
Unit tests for comps_adapters.py. ManualCompsAdapter/CsvCompsAdapter are
pure and tested directly; EbayBrowseAdapter's network calls are mocked —
same convention as storage.py/mail.py not being live-network-tested.

    python3 -m pytest tests/test_comps_adapters.py -v
"""

import io
import unittest
from unittest import mock

import pandas as pd

from comps import ACTIVE, SOLD, Comp
from comps_adapters import (
    CsvCompsAdapter,
    EbayAuthError,
    EbayBrowseAdapter,
    EbayInsightsNotApprovedError,
    EbayMarketplaceInsightsAdapter,
    ManualCompsAdapter,
    is_ebay_configured,
    is_marketplace_insights_configured,
)


class TestManualCompsAdapter(unittest.TestCase):
    def test_returns_the_comps_it_was_given(self):
        comps = [Comp(price=100), Comp(price=200)]
        adapter = ManualCompsAdapter(comps)
        self.assertEqual(adapter.fetch_comps(), comps)

    def test_respects_limit(self):
        comps = [Comp(price=p) for p in range(10)]
        adapter = ManualCompsAdapter(comps)
        self.assertEqual(len(adapter.fetch_comps(limit=3)), 3)


class TestCsvCompsAdapter(unittest.TestCase):
    def test_parses_minimal_csv_with_only_price(self):
        csv_bytes = b"price\n100\n200\n"
        adapter = CsvCompsAdapter(csv_bytes=csv_bytes)
        comps = adapter.fetch_comps()
        self.assertEqual(len(comps), 2)
        self.assertEqual(comps[0].price, 100.0)
        self.assertEqual(comps[0].listing_type, SOLD)  # defaults to sold

    def test_parses_full_csv(self):
        csv_bytes = (
            b"price,source,listing_type,condition,shipping,listing_date,title,url\n"
            b"150.50,eBay,sold,Used,5.99,2026-01-01,14k Gold Ring,http://example.com/1\n"
        )
        adapter = CsvCompsAdapter(csv_bytes=csv_bytes)
        comps = adapter.fetch_comps()
        self.assertEqual(len(comps), 1)
        c = comps[0]
        self.assertEqual(c.price, 150.50)
        self.assertEqual(c.source, "eBay")
        self.assertEqual(c.condition, "Used")
        self.assertEqual(c.shipping, 5.99)
        self.assertEqual(c.title, "14k Gold Ring")

    def test_rows_missing_price_are_skipped(self):
        df = pd.DataFrame([{"price": 100}, {"price": None}, {"price": 200}])
        adapter = CsvCompsAdapter(dataframe=df)
        comps = adapter.fetch_comps()
        self.assertEqual(len(comps), 2)

    def test_dataframe_constructor_works_directly(self):
        df = pd.DataFrame([{"price": 42}])
        adapter = CsvCompsAdapter(dataframe=df)
        self.assertEqual(adapter.fetch_comps()[0].price, 42.0)

    def test_requires_either_csv_bytes_or_dataframe(self):
        with self.assertRaises(ValueError):
            CsvCompsAdapter()

    def test_respects_limit(self):
        csv_bytes = b"price\n" + b"\n".join(str(p).encode() for p in range(10))
        adapter = CsvCompsAdapter(csv_bytes=csv_bytes)
        self.assertEqual(len(adapter.fetch_comps(limit=4)), 4)


class TestEbayBrowseAdapter(unittest.TestCase):
    def setUp(self):
        # Reset the module-level token cache between tests so mocked
        # secrets/responses don't leak across test cases.
        import comps_adapters
        comps_adapters._token_cache = {}

    @mock.patch("comps_adapters.st")
    def test_raises_ebay_auth_error_when_not_configured(self, mock_st):
        mock_st.secrets.get.return_value = None
        adapter = EbayBrowseAdapter()
        with self.assertRaises(EbayAuthError):
            adapter.fetch_comps("14k gold ring")

    @mock.patch("comps_adapters.st")
    def test_is_ebay_configured_false_without_secrets(self, mock_st):
        mock_st.secrets.get.return_value = None
        self.assertFalse(is_ebay_configured())

    @mock.patch("comps_adapters.st")
    def test_is_ebay_configured_true_with_secrets(self, mock_st):
        mock_st.secrets.get.side_effect = lambda k: {"EBAY_CLIENT_ID": "id", "EBAY_CLIENT_SECRET": "secret"}.get(k)
        self.assertTrue(is_ebay_configured())

    @mock.patch("comps_adapters.requests")
    @mock.patch("comps_adapters.st")
    def test_fetch_comps_parses_active_listings(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k: {"EBAY_CLIENT_ID": "id", "EBAY_CLIENT_SECRET": "secret"}.get(k)

        token_response = mock.Mock()
        token_response.json.return_value = {"access_token": "fake_token", "expires_in": 7200}
        token_response.raise_for_status.return_value = None

        search_response = mock.Mock()
        search_response.json.return_value = {
            "itemSummaries": [
                {
                    "title": "14k Gold Chain 22in",
                    "price": {"value": "240.00", "currency": "USD"},
                    "condition": "Pre-owned",
                    "itemWebUrl": "https://ebay.com/item/1",
                    "shippingOptions": [{"shippingCost": {"value": "5.00"}}],
                },
                {
                    "title": "Bad listing with no price",
                    "price": {},
                },
            ]
        }
        search_response.raise_for_status.return_value = None

        mock_requests.post.return_value = token_response
        mock_requests.get.return_value = search_response

        adapter = EbayBrowseAdapter()
        comps = adapter.fetch_comps("14k gold chain")

        self.assertEqual(len(comps), 1)  # the no-price listing is skipped
        self.assertEqual(comps[0].price, 240.0)
        self.assertEqual(comps[0].shipping, 5.0)
        self.assertEqual(comps[0].listing_type, ACTIVE)  # never claims to be a sold comp
        self.assertEqual(comps[0].source, "eBay")

    @mock.patch("comps_adapters.requests")
    @mock.patch("comps_adapters.st")
    def test_empty_query_returns_no_comps_without_a_network_call(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k: {"EBAY_CLIENT_ID": "id", "EBAY_CLIENT_SECRET": "secret"}.get(k)
        adapter = EbayBrowseAdapter()
        comps = adapter.fetch_comps("   ")
        self.assertEqual(comps, [])
        mock_requests.post.assert_not_called()
        mock_requests.get.assert_not_called()


class TestEbayMarketplaceInsightsAdapter(unittest.TestCase):
    def setUp(self):
        import comps_adapters
        comps_adapters._token_cache = {}
        comps_adapters._insights_approval_cache = {"approved": None}

    def _mock_token_response(self, mock_requests):
        token_response = mock.Mock()
        token_response.json.return_value = {"access_token": "fake_insights_token", "expires_in": 7200}
        token_response.raise_for_status.return_value = None
        mock_requests.post.return_value = token_response

    @mock.patch("comps_adapters.st")
    def test_raises_ebay_auth_error_when_not_configured(self, mock_st):
        mock_st.secrets.get.return_value = None
        adapter = EbayMarketplaceInsightsAdapter()
        with self.assertRaises(EbayAuthError):
            adapter.fetch_comps("14k gold ring")

    @mock.patch("comps_adapters.requests")
    @mock.patch("comps_adapters.st")
    def test_empty_query_returns_no_comps_without_a_network_call(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k: {"EBAY_CLIENT_ID": "id", "EBAY_CLIENT_SECRET": "secret"}.get(k)
        adapter = EbayMarketplaceInsightsAdapter()
        comps = adapter.fetch_comps("   ")
        self.assertEqual(comps, [])
        mock_requests.post.assert_not_called()
        mock_requests.get.assert_not_called()

    @mock.patch("comps_adapters.requests")
    @mock.patch("comps_adapters.st")
    def test_fetch_comps_parses_sold_items(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k: {"EBAY_CLIENT_ID": "id", "EBAY_CLIENT_SECRET": "secret"}.get(k)
        self._mock_token_response(mock_requests)

        search_response = mock.Mock()
        search_response.status_code = 200
        search_response.json.return_value = {
            "itemSales": [
                {
                    "title": "14k Gold Chain 22in",
                    "lastSoldPrice": {"value": "255.00", "currency": "USD"},
                    "lastSoldDate": "2026-08-01T00:00:00Z",
                    "condition": "Pre-owned",
                    "itemWebUrl": "https://ebay.com/item/1",
                },
                {"title": "Bad row with no sold price", "lastSoldPrice": {}},
            ]
        }
        search_response.raise_for_status.return_value = None
        mock_requests.get.return_value = search_response

        adapter = EbayMarketplaceInsightsAdapter()
        comps = adapter.fetch_comps("14k gold chain")

        self.assertEqual(len(comps), 1)
        self.assertEqual(comps[0].price, 255.0)
        self.assertEqual(comps[0].listing_type, SOLD)  # real sold evidence, unlike Browse
        self.assertEqual(comps[0].source, "eBay (sold)")
        self.assertEqual(comps[0].listing_date, "2026-08-01T00:00:00Z")

        # Confirms it requested the insights scope, not the plain Browse scope.
        import comps_adapters
        token_call_kwargs = mock_requests.post.call_args.kwargs
        self.assertEqual(token_call_kwargs["data"]["scope"], comps_adapters._INSIGHTS_SCOPE)

    @mock.patch("comps_adapters.requests")
    @mock.patch("comps_adapters.st")
    def test_unapproved_app_raises_specific_error(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k: {"EBAY_CLIENT_ID": "id", "EBAY_CLIENT_SECRET": "secret"}.get(k)
        self._mock_token_response(mock_requests)

        denied_response = mock.Mock()
        denied_response.status_code = 403
        denied_response.headers = {"content-type": "application/json"}
        denied_response.json.return_value = {
            "errors": [{"errorId": 1100, "domain": "ACCESS", "category": "REQUEST", "message": "Access denied"}]
        }
        mock_requests.get.return_value = denied_response

        adapter = EbayMarketplaceInsightsAdapter()
        with self.assertRaises(EbayInsightsNotApprovedError):
            adapter.fetch_comps("14k gold chain")

    @mock.patch("comps_adapters.requests")
    @mock.patch("comps_adapters.st")
    def test_other_403_is_not_mistaken_for_unapproved(self, mock_st, mock_requests):
        """A 403 for some other reason (bad token, revoked key, etc.) should
        surface as a normal HTTP error, not get misreported as "not approved
        yet" - those need different fixes and shouldn't be conflated."""
        mock_st.secrets.get.side_effect = lambda k: {"EBAY_CLIENT_ID": "id", "EBAY_CLIENT_SECRET": "secret"}.get(k)
        self._mock_token_response(mock_requests)

        import requests as real_requests

        other_403 = mock.Mock()
        other_403.status_code = 403
        other_403.headers = {"content-type": "application/json"}
        other_403.json.return_value = {"errors": [{"errorId": 2001, "message": "Some other problem"}]}
        other_403.raise_for_status.side_effect = real_requests.exceptions.HTTPError("403 Forbidden")
        mock_requests.get.return_value = other_403
        mock_requests.exceptions = real_requests.exceptions

        adapter = EbayMarketplaceInsightsAdapter()
        with self.assertRaises(real_requests.exceptions.HTTPError):
            adapter.fetch_comps("14k gold chain")

    @mock.patch("comps_adapters.requests")
    @mock.patch("comps_adapters.st")
    def test_is_marketplace_insights_configured_false_when_not_approved(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k: {"EBAY_CLIENT_ID": "id", "EBAY_CLIENT_SECRET": "secret"}.get(k)
        self._mock_token_response(mock_requests)

        denied_response = mock.Mock()
        denied_response.status_code = 403
        denied_response.headers = {"content-type": "application/json"}
        denied_response.json.return_value = {"errors": [{"errorId": 1100}]}
        mock_requests.get.return_value = denied_response

        self.assertFalse(is_marketplace_insights_configured())
        # Cached - a second call shouldn't hit the network again.
        call_count_before = mock_requests.get.call_count
        self.assertFalse(is_marketplace_insights_configured())
        self.assertEqual(mock_requests.get.call_count, call_count_before)

    @mock.patch("comps_adapters.requests")
    @mock.patch("comps_adapters.st")
    def test_is_marketplace_insights_configured_true_when_approved(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = lambda k: {"EBAY_CLIENT_ID": "id", "EBAY_CLIENT_SECRET": "secret"}.get(k)
        self._mock_token_response(mock_requests)

        ok_response = mock.Mock()
        ok_response.status_code = 200
        ok_response.raise_for_status.return_value = None
        ok_response.json.return_value = {"itemSales": []}
        mock_requests.get.return_value = ok_response

        self.assertTrue(is_marketplace_insights_configured())

    @mock.patch("comps_adapters.st")
    def test_is_marketplace_insights_configured_false_without_secrets(self, mock_st):
        mock_st.secrets.get.return_value = None
        self.assertFalse(is_marketplace_insights_configured())


if __name__ == "__main__":
    unittest.main()
