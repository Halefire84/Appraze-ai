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
    assert offer["categoryId"] == "20624"


def test_master_to_offer_never_sends_the_configured_location_key():
    # The stored merchant-location key is invalid for real sandbox sellers
    # ("Location information not found" on createOffer) — publish_master()
    # resolves a real one via find_merchant_location_key() instead.
    offer = master_to_offer(SAMPLE_MASTER, _config(merchant_location_key="STALE_KEY"))
    assert "merchantLocationKey" not in offer


def test_inventory_item_passes_through_ebay_aspects():
    item = master_to_inventory_item({
        "sku": "S",
        "title": "T",
        "ebay_aspects": {"Brand": "Unbranded", "Type": ["Mixing Bowl"]},
    })
    assert item["product"]["aspects"] == {"Brand": ["Unbranded"], "Type": ["Mixing Bowl"]}


def test_inventory_item_omits_aspects_when_not_a_dict():
    item = master_to_inventory_item({"sku": "S", "title": "T", "ebay_aspects": "not-a-dict"})
    assert "aspects" not in item["product"]


# --- client / publish -------------------------------------------------------
def _client(session, config=None):
    return EbaySellClient(config=config or _config(), access_token="ACCESS-1", session=session)


def test_publish_happy_path_calls_sandbox_endpoints_in_order():
    session = MagicMock()
    session.request.side_effect = [
        _response(204),                                     # PUT inventory_item
        _response(200, {"locations": [{"merchantLocationKey": "LOC-1", "merchantLocationStatus": "ENABLED"}]}),
        _response(200, {"offers": []}),                     # GET offer?sku=
        _response(201, {"offerId": "OFFER-9"}),             # POST offer
        _response(200, {"listingId": "LISTING-7"}),         # POST publish
    ]
    result = publish_master(SAMPLE_MASTER, config=_config(), client=_client(session))
    assert result == {"sku": "CRTC-1042", "offer_id": "OFFER-9", "listing_id": "LISTING-7"}

    calls = [(c.args[0], c.args[1]) for c in session.request.call_args_list]
    assert calls[0] == ("PUT", "https://api.sandbox.ebay.com/sell/inventory/v1/inventory_item/CRTC-1042")
    assert calls[3] == ("POST", "https://api.sandbox.ebay.com/sell/inventory/v1/offer")
    assert calls[4] == ("POST", "https://api.sandbox.ebay.com/sell/inventory/v1/offer/OFFER-9/publish")
    assert all("api.sandbox.ebay.com" in url for _, url in calls)

    # The resolved (live, ENABLED) location key is attached to the created offer.
    create_offer_body = session.request.call_args_list[3].kwargs["json"]
    assert create_offer_body["merchantLocationKey"] == "LOC-1"


def test_publish_updates_existing_offer_instead_of_duplicating():
    session = MagicMock()
    session.request.side_effect = [
        _response(204),                                     # PUT inventory_item
        _response(200, {"locations": []}),                  # GET location (none found)
        _response(200, {"offers": [{"offerId": "OFFER-EXISTING"}]}),
        _response(204),                                     # PUT offer (update)
        _response(200, {"listingId": "LISTING-7"}),
    ]
    result = publish_master(SAMPLE_MASTER, config=_config(), client=_client(session))
    assert result["offer_id"] == "OFFER-EXISTING"
    methods = [c.args[0] for c in session.request.call_args_list]
    assert methods == ["PUT", "GET", "GET", "PUT", "POST"]

    # No location was found, so none is forced onto the update body.
    update_offer_body = session.request.call_args_list[3].kwargs["json"]
    assert "merchantLocationKey" not in update_offer_body


def test_publish_master_treats_no_existing_offer_404_as_none_not_fatal():
    """find_offer_id's GET 404s ('Offer is not available') for a SKU with no
    offer yet — publish_master must still proceed to createOffer, not raise."""
    session = MagicMock()
    session.request.side_effect = [
        _response(204),                                          # PUT inventory_item
        _response(200, {"locations": []}),                       # GET location
        _response(404, {"errors": [{"errorId": 11800, "message": "Offer is not available"}]}),
        _response(201, {"offerId": "OFFER-9"}),                  # POST offer
        _response(200, {"listingId": "LISTING-7"}),
    ]
    result = publish_master(SAMPLE_MASTER, config=_config(), client=_client(session))
    assert result["offer_id"] == "OFFER-9"


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
        _response(204), _response(200, {"locations": []}), _response(200, {"offers": []}),
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


def test_find_offer_id_returns_none_on_404_instead_of_raising():
    """eBay 404s ('Offer is not available') for a SKU with no offer yet —
    that's a normal 'no existing offer' result, not a failure."""
    session = MagicMock()
    session.request.return_value = _response(404, {"errors": [{"errorId": 11800, "message": "Offer is not available"}]})
    assert _client(session).find_offer_id("NO-SUCH-SKU") is None


def test_find_offer_id_still_raises_on_other_errors():
    session = MagicMock()
    session.request.return_value = _response(500, {"errors": [{"errorId": 1, "message": "boom"}]})
    with pytest.raises(EbaySellError):
        _client(session).find_offer_id("SOME-SKU")


def test_publish_offer_sends_a_real_json_body_not_none():
    """A bodyless POST 411s at eBay's sandbox edge; requests only sets
    Content-Length when a json body is actually passed."""
    session = MagicMock()
    session.request.return_value = _response(200, {"listingId": "LISTING-7"})
    _client(session).publish_offer("OFFER-9")
    assert session.request.call_args.kwargs["json"] == {}


def test_withdraw_offer_sends_a_real_json_body_not_none():
    session = MagicMock()
    session.request.return_value = _response(200, {"listingId": "LISTING-7"})
    _client(session).withdraw_offer("OFFER-9")
    assert session.request.call_args.kwargs["json"] == {}


def test_find_merchant_location_key_returns_first_enabled_location():
    session = MagicMock()
    session.request.return_value = _response(200, {"locations": [
        {"merchantLocationKey": "DISABLED-LOC", "merchantLocationStatus": "DISABLED"},
        {"merchantLocationKey": "LOC-OK", "merchantLocationStatus": "ENABLED"},
    ]})
    assert _client(session).find_merchant_location_key() == "LOC-OK"


def test_find_merchant_location_key_returns_none_when_no_locations_exist():
    session = MagicMock()
    session.request.return_value = _response(200, {"locations": []})
    assert _client(session).find_merchant_location_key() is None


def test_inventory_item_request_sends_content_language_header():
    session = MagicMock()
    session.request.return_value = _response(204)
    _client(session).create_or_replace_inventory_item("SKU-1", {"condition": "NEW"})
    headers = session.request.call_args.kwargs["headers"]
    assert headers["Content-Language"] == "en-US"
    assert headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"
    assert headers["Authorization"] == "Bearer ACCESS-1"
