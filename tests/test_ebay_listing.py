"""
Unit tests for ebay_listing.py. Network calls and Streamlit secrets are
mocked throughout, same convention as tests/test_comps_adapters.py.

Core contracts under test:
  - The Authorization Code OAuth flow (distinct from comps_adapters.py's
    client_credentials grant) builds the right consent URL and correctly
    exchanges/refreshes tokens.
  - publish_listing() never claims success from a partial completion --
    a failure at any step reports that exact step, not a generic error.
  - Every network failure is a normal PublishResult(ok=False, ...), never
    an unhandled exception.
"""

import unittest
from unittest import mock

import ebay_listing
from ebay_listing import (
    EbayListingError,
    PublishResult,
    SellerCredentials,
    authorization_url,
    create_inventory_item,
    create_offer,
    exchange_code_for_tokens,
    publish_listing,
    publish_offer,
    refresh_access_token,
)


def _secrets(**overrides):
    base = {
        "EBAY_CLIENT_ID": "client-id-123",
        "EBAY_CLIENT_SECRET": "client-secret-456",
        "EBAY_RUNAME": "Cooper_River-Appraze-RuName-abc",
        "EBAY_SANDBOX": False,
    }
    base.update(overrides)
    return lambda key, default=None: base.get(key, default)


class TestAuthorizationUrl(unittest.TestCase):
    @mock.patch("ebay_listing.st")
    def test_builds_expected_url_with_sell_scopes(self, mock_st):
        mock_st.secrets.get.side_effect = _secrets()
        url = authorization_url("state-token-xyz")
        self.assertTrue(url.startswith("https://auth.ebay.com/oauth2/authorize?"))
        self.assertIn("client_id=client-id-123", url)
        self.assertIn("sell.inventory", url)
        self.assertIn("state=state-token-xyz", url)

    @mock.patch("ebay_listing.st")
    def test_sandbox_mode_uses_sandbox_auth_host(self, mock_st):
        mock_st.secrets.get.side_effect = _secrets(EBAY_SANDBOX=True)
        url = authorization_url("state")
        self.assertTrue(url.startswith("https://auth.sandbox.ebay.com/"))

    @mock.patch("ebay_listing.st")
    def test_missing_runame_raises_clear_error(self, mock_st):
        mock_st.secrets.get.side_effect = _secrets(EBAY_RUNAME=None)
        with self.assertRaises(EbayListingError):
            authorization_url("state")

    @mock.patch("ebay_listing.st")
    def test_missing_client_credentials_raises_clear_error(self, mock_st):
        mock_st.secrets.get.side_effect = _secrets(EBAY_CLIENT_ID=None)
        with self.assertRaises(EbayListingError):
            authorization_url("state")


class TestTokenExchange(unittest.TestCase):
    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing.st")
    def test_exchange_code_returns_credentials(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = _secrets()
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"access_token": "AT1", "refresh_token": "RT1", "expires_in": 7200}
        mock_requests.post.return_value = resp

        creds = exchange_code_for_tokens("auth-code-abc")
        self.assertEqual(creds.access_token, "AT1")
        self.assertEqual(creds.refresh_token, "RT1")
        call_kwargs = mock_requests.post.call_args.kwargs
        self.assertEqual(call_kwargs["data"]["grant_type"], "authorization_code")
        self.assertEqual(call_kwargs["data"]["code"], "auth-code-abc")

    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing.st")
    def test_exchange_http_error_raises_ebay_listing_error_not_raw_exception(self, mock_st, mock_requests):
        import requests as real_requests
        mock_st.secrets.get.side_effect = _secrets()
        resp = mock.Mock()
        resp.status_code = 400
        resp.text = "invalid_grant"
        error = real_requests.exceptions.HTTPError("400")
        error.response = resp
        resp.raise_for_status.side_effect = error
        mock_requests.post.return_value = resp
        mock_requests.exceptions = real_requests.exceptions

        with self.assertRaises(EbayListingError):
            exchange_code_for_tokens("bad-code")

    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing.st")
    def test_refresh_keeps_same_refresh_token(self, mock_st, mock_requests):
        mock_st.secrets.get.side_effect = _secrets()
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"access_token": "AT2", "expires_in": 7200}
        mock_requests.post.return_value = resp

        creds = refresh_access_token("RT-original")
        self.assertEqual(creds.access_token, "AT2")
        self.assertEqual(creds.refresh_token, "RT-original")


class TestCredentialLifecycle(unittest.TestCase):
    @mock.patch("ebay_listing.save_credentials")
    @mock.patch("ebay_listing.refresh_access_token")
    @mock.patch("ebay_listing.load_credentials")
    def test_uses_cached_token_when_not_expired(self, mock_load, mock_refresh, mock_save):
        import time
        mock_load.return_value = SellerCredentials("AT-fresh", "RT", time.time() + 3600)
        token = ebay_listing._valid_access_token()
        self.assertEqual(token, "AT-fresh")
        mock_refresh.assert_not_called()

    @mock.patch("ebay_listing.save_credentials")
    @mock.patch("ebay_listing.refresh_access_token")
    @mock.patch("ebay_listing.load_credentials")
    def test_refreshes_when_expired(self, mock_load, mock_refresh, mock_save):
        import time
        mock_load.return_value = SellerCredentials("AT-stale", "RT", time.time() - 10)
        mock_refresh.return_value = SellerCredentials("AT-new", "RT", time.time() + 3600)
        token = ebay_listing._valid_access_token()
        self.assertEqual(token, "AT-new")
        mock_save.assert_called_once()

    @mock.patch("ebay_listing.load_credentials")
    def test_raises_when_nothing_connected(self, mock_load):
        mock_load.return_value = None
        with self.assertRaises(EbayListingError):
            ebay_listing._valid_access_token()


class TestPublishListing(unittest.TestCase):
    """These test the orchestration logic in publish_listing() by mocking
    the three underlying step functions directly -- the steps' own network
    behavior is covered separately below."""

    @mock.patch("ebay_listing.publish_offer")
    @mock.patch("ebay_listing.create_offer")
    @mock.patch("ebay_listing.create_inventory_item")
    def test_all_three_steps_succeed(self, mock_item, mock_offer, mock_publish):
        mock_item.return_value = PublishResult(ok=True)
        mock_offer.return_value = PublishResult(ok=True, listing_id="offer-1")
        mock_publish.return_value = PublishResult(ok=True, listing_id="listing-1", listing_url="https://www.ebay.com/itm/listing-1")

        result = publish_listing("SKU-1", {"title": "x"}, {"price": 10})
        self.assertTrue(result.ok)
        self.assertEqual(result.listing_url, "https://www.ebay.com/itm/listing-1")
        mock_publish.assert_called_once_with("offer-1")

    @mock.patch("ebay_listing.publish_offer")
    @mock.patch("ebay_listing.create_offer")
    @mock.patch("ebay_listing.create_inventory_item")
    def test_stops_at_inventory_item_failure_never_calls_offer_or_publish(self, mock_item, mock_offer, mock_publish):
        mock_item.return_value = PublishResult(ok=False, error="bad title", step="inventory_item")

        result = publish_listing("SKU-1", {"title": "x"}, {"price": 10})
        self.assertFalse(result.ok)
        self.assertEqual(result.step, "inventory_item")
        mock_offer.assert_not_called()
        mock_publish.assert_not_called()

    @mock.patch("ebay_listing.publish_offer")
    @mock.patch("ebay_listing.create_offer")
    @mock.patch("ebay_listing.create_inventory_item")
    def test_stops_at_offer_failure_never_calls_publish(self, mock_item, mock_offer, mock_publish):
        mock_item.return_value = PublishResult(ok=True)
        mock_offer.return_value = PublishResult(ok=False, error="missing policy", step="offer")

        result = publish_listing("SKU-1", {"title": "x"}, {"price": 10})
        self.assertFalse(result.ok)
        self.assertEqual(result.step, "offer")
        mock_publish.assert_not_called()

    @mock.patch("ebay_listing.publish_offer")
    @mock.patch("ebay_listing.create_offer")
    @mock.patch("ebay_listing.create_inventory_item")
    def test_publish_step_failure_reports_publish_not_offer(self, mock_item, mock_offer, mock_publish):
        mock_item.return_value = PublishResult(ok=True)
        mock_offer.return_value = PublishResult(ok=True, listing_id="offer-1")
        mock_publish.return_value = PublishResult(ok=False, error="publish rejected", step="publish", listing_id="offer-1")

        result = publish_listing("SKU-1", {"title": "x"}, {"price": 10})
        self.assertFalse(result.ok)
        self.assertEqual(result.step, "publish")


class TestCreateInventoryItem(unittest.TestCase):
    @mock.patch("ebay_listing._base_url", return_value="https://api.ebay.com")
    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing._valid_access_token")
    def test_success(self, mock_token, mock_requests, mock_base_url):
        mock_token.return_value = "AT"
        resp = mock.Mock(status_code=200)
        mock_requests.put.return_value = resp

        result = create_inventory_item("SKU-1", {"title": "Vintage lamp", "quantity": 1})
        self.assertTrue(result.ok)

    @mock.patch("ebay_listing._base_url", return_value="https://api.ebay.com")
    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing._valid_access_token")
    def test_rejection_reports_inventory_item_step_and_real_reason(self, mock_token, mock_requests, mock_base_url):
        mock_token.return_value = "AT"
        resp = mock.Mock(status_code=400, text="Invalid condition")
        mock_requests.put.return_value = resp

        result = create_inventory_item("SKU-1", {"title": "x"})
        self.assertFalse(result.ok)
        self.assertEqual(result.step, "inventory_item")
        self.assertIn("Invalid condition", result.error)

    @mock.patch("ebay_listing._valid_access_token")
    def test_not_connected_reports_inventory_item_step_not_a_crash(self, mock_token):
        mock_token.side_effect = EbayListingError("not connected")
        result = create_inventory_item("SKU-1", {"title": "x"})
        self.assertFalse(result.ok)
        self.assertEqual(result.step, "inventory_item")
        self.assertIn("not connected", result.error)


class TestCreateOffer(unittest.TestCase):
    @mock.patch("ebay_listing._base_url", return_value="https://api.ebay.com")
    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing._valid_access_token")
    def test_success_returns_offer_id(self, mock_token, mock_requests, mock_base_url):
        mock_token.return_value = "AT"
        resp = mock.Mock(status_code=201)
        resp.json.return_value = {"offerId": "offer-123"}
        mock_requests.post.return_value = resp

        result = create_offer("SKU-1", {"price": 25.0, "payment_policy_id": "pp1", "return_policy_id": "rp1", "fulfillment_policy_id": "fp1"})
        self.assertTrue(result.ok)
        self.assertEqual(result.listing_id, "offer-123")

    @mock.patch("ebay_listing._base_url", return_value="https://api.ebay.com")
    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing._valid_access_token")
    def test_missing_policy_rejection_reports_offer_step_and_real_reason(self, mock_token, mock_requests, mock_base_url):
        mock_token.return_value = "AT"
        resp = mock.Mock(status_code=400, text="Invalid paymentPolicyId")
        mock_requests.post.return_value = resp

        result = create_offer("SKU-1", {"price": 25.0})
        self.assertFalse(result.ok)
        self.assertEqual(result.step, "offer")
        self.assertIn("Invalid paymentPolicyId", result.error)


class TestPublishOffer(unittest.TestCase):
    @mock.patch("ebay_listing._base_url", return_value="https://api.ebay.com")
    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing._valid_access_token")
    def test_success_returns_listing_url(self, mock_token, mock_requests, mock_base_url):
        mock_token.return_value = "AT"
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"listingId": "999888777"}
        mock_requests.post.return_value = resp

        result = publish_offer("offer-123")
        self.assertTrue(result.ok)
        self.assertEqual(result.listing_url, "https://www.ebay.com/itm/999888777")

    @mock.patch("ebay_listing._base_url", return_value="https://api.ebay.com")
    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing._valid_access_token")
    def test_rejection_keeps_offer_id_for_diagnostics(self, mock_token, mock_requests, mock_base_url):
        mock_token.return_value = "AT"
        resp = mock.Mock(status_code=400, text="listing incomplete")
        mock_requests.post.return_value = resp

        result = publish_offer("offer-123")
        self.assertFalse(result.ok)
        self.assertEqual(result.step, "publish")
        self.assertEqual(result.listing_id, "offer-123")
        self.assertIn("listing incomplete", result.error)


class TestConnectionState(unittest.TestCase):
    @mock.patch("ebay_listing.load_credentials")
    def test_is_connected_true(self, mock_load):
        import time
        mock_load.return_value = SellerCredentials("AT", "RT", time.time() + 3600)
        self.assertTrue(ebay_listing.is_connected())

    @mock.patch("ebay_listing.load_credentials")
    def test_is_connected_false(self, mock_load):
        mock_load.return_value = None
        self.assertFalse(ebay_listing.is_connected())


class TestGetBusinessPolicies(unittest.TestCase):
    @mock.patch("ebay_listing._base_url", return_value="https://api.ebay.com")
    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing._valid_access_token")
    def test_returns_policies_by_type(self, mock_token, mock_requests, mock_base_url):
        mock_token.return_value = "AT"

        def fake_get(url, headers=None, params=None, timeout=None):
            resp = mock.Mock(status_code=200)
            if "payment_policy" in url:
                resp.json.return_value = {"paymentPolicies": [{"paymentPolicyId": "pp1", "name": "Standard"}]}
            elif "return_policy" in url:
                resp.json.return_value = {"returnPolicies": [{"returnPolicyId": "rp1", "name": "30-day"}]}
            else:
                resp.json.return_value = {"fulfillmentPolicies": [{"fulfillmentPolicyId": "fp1", "name": "Ships in 2 days"}]}
            resp.raise_for_status.return_value = None
            return resp

        mock_requests.get.side_effect = fake_get
        policies = ebay_listing.get_business_policies()
        self.assertEqual(len(policies["payment"]) + len(policies["return"]) + len(policies["fulfillment"]), 3)
        self.assertEqual(policies["payment"][0]["id"], "pp1")
        self.assertEqual(policies["return"][0]["id"], "rp1")
        self.assertEqual(policies["fulfillment"][0]["id"], "fp1")

    @mock.patch("ebay_listing._base_url", return_value="https://api.ebay.com")
    @mock.patch("ebay_listing.requests")
    @mock.patch("ebay_listing._valid_access_token")
    def test_network_failure_returns_empty_lists_not_a_crash(self, mock_token, mock_requests, mock_base_url):
        mock_token.return_value = "AT"
        mock_requests.get.side_effect = Exception("timeout")

        policies = ebay_listing.get_business_policies()
        self.assertEqual(policies, {"payment": [], "return": [], "fulfillment": []})


if __name__ == "__main__":
    unittest.main()
