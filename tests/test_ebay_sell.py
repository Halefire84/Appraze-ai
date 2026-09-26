"""Tests for the eBay Sell API sandbox adapter.

Every HTTP call is mocked — these tests must never touch the network, and they
must never need real eBay credentials.
"""
import json
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

import ebay_sell
from ebay_sell import (
    EbayConfig,
    EbaySellAuthError,
    EbaySellClient,
    EbaySellConfigError,
    EbaySellError,
    exchange_code_for_tokens,
    get_authorization_url,
    get_valid_access_token,
    load_config,
    map_condition,
    master_to_inventory_item,
    master_to_offer,
    publish_master,
    refresh_access_token,
)


def _config(**overrides):
    base = dict(
        client_id="CID-SANDBOX",
        client_secret="CSECRET-SANDBOX",
        redirect_uri="Alex-RuName-SBX",
        marketplace_id="EBAY_US",
        merchant_location_key="CRTC_WAREHOUSE",
        fulfillment_policy_id="FP-1",
        payment_policy_id="PP-1",
        return_policy_id="RP-1",
    )
    base.update(overrides)
    return EbayConfig(**base)


def _response(status_code=200, body=None, text=""):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.content = (json.dumps(body) if body is not None else text).encode()
    resp.text = text or (json.dumps(body) if body is not None else "")
    resp.json.side_effect = (lambda: body) if body is not None else ValueError("no json")
    return resp


SAMPLE_MASTER = {
    "sku": "CRTC-1042",
    "marketplace": "eBay",
    "title": "Vintage Pyrex Mixing Bowl Set — 4 piece, primary colors",
    "description": "Complete nesting set. No chips or cracks.",
    "condition": "Very Good",
    "condition_notes": "Light utensil marks inside the yellow bowl.",
    "price": 129.5,
    "quantity": 2,
    "weight_lbs": 6.5,
    "length_in": 14,
    "width_in": 14,
    "height_in": 10,
    "brand": "Pyrex",
    "image_urls": ["https://example.com/a.jpg", "https://example.com/b.jpg"],
    "ebay_category_id": "20624",
}


# --- config -----------------------------------------------------------------
def test_config_reads_ebay_sell_prefix_and_ignores_browse_keys():
    env = {
        "EBAY_SELL_CLIENT_ID": "sell-id",
        "EBAY_SELL_CLIENT_SECRET": "sell-secret",
        "EBAY_SELL_REDIRECT_URI": "RuName",
        # The Browse-API credentials used by comps_adapters.py must not leak in.
        "EBAY_CLIENT_ID": "browse-id",
        "EBAY_CLIENT_SECRET": "browse-secret",
    }
    config = load_config(env=env, config_path=ebay_sell.Path("does-not-exist.json"))
    assert config.client_id == "sell-id"
    assert config.client_secret == "sell-secret"
    assert config.marketplace_id == "EBAY_US"


def test_config_repr_never_leaks_secret():
    rendered = repr(_config())
    assert "CSECRET-SANDBOX" not in rendered
    assert "client_secret=set" in rendered


def test_missing_credentials_raise_config_error():
    with pytest.raises(EbaySellConfigError) as exc:
        EbayConfig().require_auth_fields()
    assert "EBAY_SELL_CLIENT_ID" in str(exc.value)


def test_missing_business_policies_raise_before_any_http(tmp_path):
    client = MagicMock(spec=EbaySellClient)
    with pytest.raises(EbaySellConfigError):
        publish_master(SAMPLE_MASTER, config=_config(fulfillment_policy_id=""), client=client)
    client.create_or_replace_inventory_item.assert_not_called()


# --- auth -------------------------------------------------------------------
def test_authorization_url_is_sandbox_and_carries_scopes():
    url = get_authorization_url(config=_config())
    assert url.startswith("https://auth.sandbox.ebay.com/oauth2/authorize?")
    assert "client_id=CID-SANDBOX" in url
    assert "response_type=code" in url
    assert "sell.inventory" in url


def test_exchange_code_persists_tokens(tmp_path):
    token_path = tmp_path / ".ebay_tokens.json"
    payload = {
        "access_token": "ACCESS-1",
        "expires_in": 7200,
        "refresh_token": "REFRESH-1",
        "refresh_token_expires_in": 47304000,
    }
    with patch("ebay_sell.requests.post", return_value=_response(200, payload)) as post:
        tokens = exchange_code_for_tokens("the-code", config=_config(), token_path=token_path)
    assert post.call_args.kwargs["data"]["grant_type"] == "authorization_code"
    assert tokens["access_token"] == "ACCESS-1"
    assert tokens["expires_at"] > time.time()
    assert json.loads(token_path.read_text())["refresh_token"] == "REFRESH-1"


def test_expired_token_triggers_refresh_and_keeps_refresh_token(tmp_path):
    token_path = tmp_path / ".ebay_tokens.json"
    token_path.write_text(json.dumps({
        "access_token": "OLD",
        "expires_at": time.time() - 10,  # expired
        "refresh_token": "REFRESH-1",
    }))
    # eBay's refresh response omits refresh_token; it must survive the round trip.
    with patch("ebay_sell.requests.post", return_value=_response(200, {"access_token": "NEW", "expires_in": 7200})) as post:
        token = get_valid_access_token(config=_config(), token_path=token_path)
    assert token == "NEW"
    assert post.call_args.kwargs["data"]["grant_type"] == "refresh_token"
    assert json.loads(token_path.read_text())["refresh_token"] == "REFRESH-1"


def test_live_token_is_reused_without_network(tmp_path):
    token_path = tmp_path / ".ebay_tokens.json"
    token_path.write_text(json.dumps({
        "access_token": "STILL-GOOD",
        "expires_at": time.time() + 3600,
        "refresh_token": "REFRESH-1",
    }))
    with patch("ebay_sell.requests.post", side_effect=AssertionError("must not call eBay")):
        assert get_valid_access_token(config=_config(), token_path=token_path) == "STILL-GOOD"


def test_unauthorized_state_raises_actionable_auth_error(tmp_path):
    with pytest.raises(EbaySellAuthError) as exc:
        get_valid_access_token(config=_config(), token_path=tmp_path / "missing.json")
    assert "authorize" in str(exc.value).lower()


def test_refresh_without_stored_token_raises(tmp_path):
    with pytest.raises(EbaySellAuthError):
        refresh_access_token(config=_config(), token_path=tmp_path / "missing.json")


def test_token_endpoint_error_does_not_echo_secret(tmp_path):
    token_path = tmp_path / ".ebay_tokens.json"
    token_path.write_text(json.dumps({"refresh_token": "REFRESH-1", "expires_at": 0}))
    body = {"errors": [{"errorId": 1001, "message": "invalid_grant"}]}
    with patch("ebay_sell.requests.post", return_value=_response(400, body)):
        with pytest.raises(EbaySellAuthError) as exc:
            get_valid_access_token(config=_config(), token_path=token_path)
    message = str(exc.value)
    assert "invalid_grant" in message
    assert "CSECRET-SANDBOX" not in message


# --- mapping (pure) ---------------------------------------------------------
def test_master_to_inventory_item_maps_core_fields():
    item = master_to_inventory_item(SAMPLE_MASTER)
    assert item["product"]["title"] == SAMPLE_MASTER["title"]
    assert item["product"]["description"] == SAMPLE_MASTER["description"]
    assert item["product"]["brand"] == "Pyrex"
    assert item["product"]["imageUrls"] == SAMPLE_MASTER["image_urls"]
    assert item["condition"] == "USED_VERY_GOOD"
    assert item["conditionDescription"].startswith("Light utensil marks")
    assert item["availability"]["shipToLocationAvailability"]["quantity"] == 2
    assert item["packageWeightAndSize"]["weight"] == {"value": 6.5, "unit": "POUND"}
    assert item["packageWeightAndSize"]["dimensions"]["length"] == 14.0


def test_inventory_item_title_truncated_to_ebay_limit():
    item = master_to_inventory_item({"title": "x" * 200, "sku": "S"})
    assert len(item["product"]["title"]) == 80


def test_inventory_item_omits_empty_package_rather_than_sending_zeros():
    item = master_to_inventory_item({"sku": "S", "title": "T", "price": 5})
    assert "packageWeightAndSize" not in item
    assert item["condition"] == "USED_GOOD"
    assert item["availability"]["shipToLocationAvailability"]["quantity"] == 1


def test_inventory_item_ignores_partial_dimensions():
    item = master_to_inventory_item({"sku": "S", "title": "T", "weight_lbs": 2, "length_in": 10})
    assert "dimensions" not in item["packageWeightAndSize"]
    assert item["packageWeightAndSize"]["weight"]["value"] == 2.0


@pytest.mark.parametrize("raw,expected", [
    ("New", "NEW"),
    ("new with tags", "NEW_WITH_TAGS"),
    ("For parts", "FOR_PARTS_OR_NOT_WORKING"),
    ("", "USED_GOOD"),
    (None, "USED_GOOD"),
    ("something unmappable", "USED_GOOD"),
    ("USED_EXCELLENT", "USED_EXCELLENT"),
])
def test_condition_mapping(raw, expected):
    assert map_condition(raw) == expected


def test_master_to_offer_is_fixed_price_with_policies():
    offer = master_to_offer(SAMPLE_MASTER, _config())
    assert offer["format"] == "FIXED_PRICE"
    assert offer["pricingSummary"]["price"] == {"value": "129.50", "currency": "USD"}
    assert offer["listingPolicies"]["fulfillmentPolicyId"] == "FP-1"
    assert offer["merchantLocationKey"] == "CRTC_WAREHOUSE"
    assert offer["categoryId"] == "20624"


# --- client / publish -------------------------------------------------------
def _client(session, config=None):
    return EbaySellClient(config=config or _config(), access_token="ACCESS-1", session=session)


def test_publish_happy_path_calls_sandbox_endpoints_in_order():
    session = MagicMock()
    session.request.side_effect = [
        _response(204),                                     # PUT inventory_item
        _response(200, {"offers": []}),                     # GET offer?sku=
        _response(201, {"offerId": "OFFER-9"}),             # POST offer
        _response(200, {"listingId": "LISTING-7"}),         # POST publish
    ]
    result = publish_master(SAMPLE_MASTER, config=_config(), client=_client(session))
    assert result == {"sku": "CRTC-1042", "offer_id": "OFFER-9", "listing_id": "LISTING-7"}

    calls = [(c.args[0], c.args[1]) for c in session.request.call_args_list]
    assert calls[0] == ("PUT", "https://api.sandbox.ebay.com/sell/inventory/v1/inventory_item/CRTC-1042")
    assert calls[2] == ("POST", "https://api.sandbox.ebay.com/sell/inventory/v1/offer")
    assert calls[3] == ("POST", "https://api.sandbox.ebay.com/sell/inventory/v1/offer/OFFER-9/publish")
    assert all("api.sandbox.ebay.com" in url for _, url in calls)


def test_publish_updates_existing_offer_instead_of_duplicating():
    session = MagicMock()
    session.request.side_effect = [
        _response(204),                                     # PUT inventory_item
        _response(200, {"offers": [{"offerId": "OFFER-EXISTING"}]}),
        _response(204),                                     # PUT offer (update)
        _response(200, {"listingId": "LISTING-7"}),
    ]
    result = publish_master(SAMPLE_MASTER, config=_config(), client=_client(session))
    assert result["offer_id"] == "OFFER-EXISTING"
    methods = [c.args[0] for c in session.request.call_args_list]
    assert methods == ["PUT", "GET", "PUT", "POST"]


def test_api_error_is_surfaced_cleanly():
    session = MagicMock()
    session.request.return_value = _response(400, {"errors": [
        {"errorId": 25002, "message": "A user error has occurred.", "longMessage": "SKU already exists."}
    ]})
    with pytest.raises(EbaySellError) as exc:
        publish_master(SAMPLE_MASTER, config=_config(), client=_client(session))
    message = str(exc.value)
    assert "25002" in message and "SKU already exists." in message
    assert "HTTP 400" in message


def test_network_failure_is_wrapped_not_raw():
    session = MagicMock()
    session.request.side_effect = requests.exceptions.ConnectionError("dns down")
    with pytest.raises(EbaySellError) as exc:
        publish_master(SAMPLE_MASTER, config=_config(), client=_client(session))
    assert "dns down" in str(exc.value)


def test_publish_without_sku_raises_before_http():
    session = MagicMock()
    with pytest.raises(EbaySellError):
        publish_master({"title": "No SKU"}, config=_config(), client=_client(session))
    session.request.assert_not_called()


def test_missing_listing_id_on_publish_is_an_error():
    session = MagicMock()
    session.request.side_effect = [
        _response(204), _response(200, {"offers": []}),
        _response(201, {"offerId": "OFFER-9"}), _response(200, {}),
    ]
    with pytest.raises(EbaySellError) as exc:
        publish_master(SAMPLE_MASTER, config=_config(), client=_client(session))
    assert "listingId" in str(exc.value)


def test_withdraw_and_status_hit_sandbox_cleanup_endpoints():
    session = MagicMock()
    session.request.return_value = _response(200, {"listingId": "LISTING-7", "status": "PUBLISHED"})
    client = _client(session)
    assert client.get_offer_status("OFFER-9")["status"] == "PUBLISHED"
    client.withdraw_offer("OFFER-9")
    urls = [c.args[1] for c in session.request.call_args_list]
    assert urls[0].endswith("/offer/OFFER-9")
    assert urls[1].endswith("/offer/OFFER-9/withdraw")


def test_inventory_item_request_sends_content_language_header():
    session = MagicMock()
    session.request.return_value = _response(204)
    _client(session).create_or_replace_inventory_item("SKU-1", {"condition": "NEW"})
    headers = session.request.call_args.kwargs["headers"]
    assert headers["Content-Language"] == "en-US"
    assert headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"
    assert headers["Authorization"] == "Bearer ACCESS-1"


# --- account-scope required for policy/location creation --------------------
def test_default_scopes_include_sell_account():
    # Without this, every policy/location builder below 403s on a live
    # sandbox call even though the mocked tests here would still pass --
    # this is the one thing mocks cannot catch, so it's pinned explicitly.
    assert any(scope.endswith("/sell.account") for scope in ebay_sell.DEFAULT_SCOPES)


# --- account/location endpoint constants are sandbox-only -------------------
def test_account_base_is_sandbox_only():
    assert ebay_sell.ACCOUNT_BASE == "https://api.sandbox.ebay.com/sell/account/v1"
    assert "sandbox" in ebay_sell.ACCOUNT_BASE
    assert "api.ebay.com" not in ebay_sell.ACCOUNT_BASE.replace("api.sandbox.ebay.com", "")


# --- policy/location builders: list + create, reuse-if-exists ---------------
def test_list_payment_policies_hits_sandbox_account_endpoint():
    session = MagicMock()
    session.request.return_value = _response(200, {"paymentPolicies": [{"paymentPolicyId": "PP-9", "name": "X"}]})
    policies = _client(session).list_payment_policies()
    assert policies == [{"paymentPolicyId": "PP-9", "name": "X"}]
    url = session.request.call_args.args[1]
    assert url == "https://api.sandbox.ebay.com/sell/account/v1/payment_policy?marketplace_id=EBAY_US"


def test_create_payment_policy_returns_new_id():
    session = MagicMock()
    session.request.return_value = _response(201, {"paymentPolicyId": "PP-NEW"})
    policy_id = _client(session).create_payment_policy("Test Payment Policy")
    assert policy_id == "PP-NEW"
    body = session.request.call_args.kwargs["json"]
    assert body["name"] == "Test Payment Policy"
    assert body["immediatePay"] is False


def test_create_payment_policy_raises_if_no_id_returned():
    session = MagicMock()
    session.request.return_value = _response(201, {})
    with pytest.raises(EbaySellError, match="paymentPolicyId"):
        _client(session).create_payment_policy("Test Payment Policy")


def test_get_or_create_payment_policy_reuses_existing_by_name():
    session = MagicMock()
    session.request.return_value = _response(200, {"paymentPolicies": [
        {"paymentPolicyId": "PP-EXISTING", "name": ebay_sell.DEFAULT_PAYMENT_POLICY_NAME},
    ]})
    policy_id = ebay_sell.get_or_create_payment_policy(_client(session))
    assert policy_id == "PP-EXISTING"
    # Only the list call happened -- no POST to create a duplicate.
    assert session.request.call_args.args[0] == "GET"
    assert session.request.call_count == 1


def test_get_or_create_payment_policy_creates_when_no_name_match():
    session = MagicMock()
    session.request.side_effect = [
        _response(200, {"paymentPolicies": [{"paymentPolicyId": "PP-OTHER", "name": "Some Other Policy"}]}),
        _response(201, {"paymentPolicyId": "PP-NEW"}),
    ]
    policy_id = ebay_sell.get_or_create_payment_policy(_client(session))
    assert policy_id == "PP-NEW"
    assert session.request.call_count == 2


def test_get_or_create_fulfillment_policy_reuses_existing_by_name():
    session = MagicMock()
    session.request.return_value = _response(200, {"fulfillmentPolicies": [
        {"fulfillmentPolicyId": "FP-EXISTING", "name": ebay_sell.DEFAULT_FULFILLMENT_POLICY_NAME},
    ]})
    policy_id = ebay_sell.get_or_create_fulfillment_policy(_client(session))
    assert policy_id == "FP-EXISTING"
    assert session.request.call_count == 1


def test_create_fulfillment_policy_sends_shipping_terms():
    session = MagicMock()
    session.request.return_value = _response(201, {"fulfillmentPolicyId": "FP-NEW"})
    _client(session).create_fulfillment_policy("Test Fulfillment Policy")
    body = session.request.call_args.kwargs["json"]
    assert body["handlingTime"] == {"value": 3, "unit": "DAY"}
    assert body["shippingOptions"][0]["costType"] == "FLAT_RATE"


def test_get_or_create_return_policy_reuses_existing_by_name():
    session = MagicMock()
    session.request.return_value = _response(200, {"returnPolicies": [
        {"returnPolicyId": "RP-EXISTING", "name": ebay_sell.DEFAULT_RETURN_POLICY_NAME},
    ]})
    policy_id = ebay_sell.get_or_create_return_policy(_client(session))
    assert policy_id == "RP-EXISTING"
    assert session.request.call_count == 1


def test_create_return_policy_sends_30_day_terms():
    session = MagicMock()
    session.request.return_value = _response(201, {"returnPolicyId": "RP-NEW"})
    _client(session).create_return_policy("Test Return Policy")
    body = session.request.call_args.kwargs["json"]
    assert body["returnsAccepted"] is True
    assert body["returnPeriod"] == {"value": 30, "unit": "DAY"}


def test_list_merchant_locations_hits_inventory_location_endpoint():
    session = MagicMock()
    session.request.return_value = _response(200, {"locations": [{"merchantLocationKey": "appraze-test-warehouse"}]})
    locations = _client(session).list_merchant_locations()
    assert locations == [{"merchantLocationKey": "appraze-test-warehouse"}]
    url = session.request.call_args.args[1]
    assert url == "https://api.sandbox.ebay.com/sell/inventory/v1/location"


def test_create_merchant_location_sends_address_from_config():
    session = MagicMock()
    session.request.return_value = _response(204)
    config = _config(location_city="Testville", location_state="TX")
    client = EbaySellClient(config=config, access_token="ACCESS-1", session=session)
    key = client.create_merchant_location("appraze-test-warehouse")
    assert key == "appraze-test-warehouse"
    body = session.request.call_args.kwargs["json"]
    assert body["location"]["address"]["city"] == "Testville"
    assert body["location"]["address"]["stateOrProvince"] == "TX"
    assert body["locationTypes"] == ["WAREHOUSE"]


def test_get_or_create_merchant_location_reuses_existing_key():
    session = MagicMock()
    session.request.return_value = _response(200, {"locations": [{"merchantLocationKey": "appraze-test-warehouse"}]})
    key = ebay_sell.get_or_create_merchant_location(_client(session))
    assert key == "appraze-test-warehouse"
    assert session.request.call_count == 1  # list only, no create POST


def test_get_or_create_merchant_location_creates_when_missing():
    session = MagicMock()
    session.request.side_effect = [
        _response(200, {"locations": []}),
        _response(204),
    ]
    key = ebay_sell.get_or_create_merchant_location(_client(session))
    assert key == ebay_sell.DEFAULT_MERCHANT_LOCATION_KEY
    assert session.request.call_count == 2


def test_ensure_sandbox_listing_prerequisites_fills_and_saves_config(tmp_path, monkeypatch):
    config_path = tmp_path / "ebay_config.json"
    monkeypatch.setattr(ebay_sell, "CONFIG_FILE", config_path)
    session = MagicMock()
    session.request.side_effect = [
        _response(200, {"paymentPolicies": []}),
        _response(201, {"paymentPolicyId": "PP-NEW"}),
        _response(200, {"fulfillmentPolicies": []}),
        _response(201, {"fulfillmentPolicyId": "FP-NEW"}),
        _response(200, {"returnPolicies": []}),
        _response(201, {"returnPolicyId": "RP-NEW"}),
        _response(200, {"locations": []}),
        _response(204),
    ]
    client = _client(session, config=_config(payment_policy_id="", fulfillment_policy_id="", return_policy_id="", merchant_location_key=""))
    config = ebay_sell.ensure_sandbox_listing_prerequisites(client)
    assert config.payment_policy_id == "PP-NEW"
    assert config.fulfillment_policy_id == "FP-NEW"
    assert config.return_policy_id == "RP-NEW"
    assert config.merchant_location_key == ebay_sell.DEFAULT_MERCHANT_LOCATION_KEY
    saved = json.loads(config_path.read_text())
    assert saved["PAYMENT_POLICY_ID"] == "PP-NEW"
    assert saved["FULFILLMENT_POLICY_ID"] == "FP-NEW"
    assert saved["RETURN_POLICY_ID"] == "RP-NEW"
    assert saved["MERCHANT_LOCATION_KEY"] == ebay_sell.DEFAULT_MERCHANT_LOCATION_KEY


# --- config save --------------------------------------------------------
def test_save_config_writes_all_fields_and_preserves_unknown_keys(tmp_path):
    path = tmp_path / "ebay_config.json"
    path.write_text(json.dumps({"_comment": "keep me"}), encoding="utf-8")
    config = _config(payment_policy_id="PP-1", merchant_location_key="LOC-1")
    ebay_sell.save_config(config, path)
    saved = json.loads(path.read_text())
    assert saved["_comment"] == "keep me"
    assert saved["PAYMENT_POLICY_ID"] == "PP-1"
    assert saved["MERCHANT_LOCATION_KEY"] == "LOC-1"
    assert saved["CLIENT_SECRET"] == "CSECRET-SANDBOX"


def test_save_config_never_overwrites_with_missing_file(tmp_path):
    path = tmp_path / "ebay_config.json"  # does not exist yet
    config = _config()
    result_path = ebay_sell.save_config(config, path)
    assert result_path == path
    assert json.loads(path.read_text())["CLIENT_ID"] == "CID-SANDBOX"
