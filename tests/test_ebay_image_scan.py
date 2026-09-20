"""Unit tests for ebay_image_scan.py's defensive handling: bad input, a
hostile/broken eBay response, and network failure must never crash the
caller, and must never be silently treated as "no results" when it's
actually an error the caller should know about.
"""

import json
from types import SimpleNamespace
from unittest import mock

import pytest
import requests

from comps_adapters import EbayAuthError
from ebay_image_scan import (
    EbayImageSearchError,
    MAX_IMAGE_BYTES,
    search_ebay_by_image,
)

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP_BYTES = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 16


def _fake_resp(status_code=200, json_data=None, json_error=False):
    resp = mock.Mock()
    resp.status_code = status_code
    if json_error:
        resp.json.side_effect = json.JSONDecodeError("bad json", "doc", 0)
    else:
        resp.json.return_value = json_data if json_data is not None else {}
    return resp


@mock.patch("ebay_image_scan._get_ebay_access_token", return_value="tok")
class TestInputValidation:
    def test_missing_image_returns_empty_list_without_network_call(self, mock_token):
        assert search_ebay_by_image(b"", "image/jpeg") == []
        mock_token.assert_not_called()

    def test_oversized_image_raises_without_network_call(self, mock_token):
        huge = b"\xff\xd8\xff" + b"0" * (MAX_IMAGE_BYTES + 1)
        with pytest.raises(EbayImageSearchError):
            search_ebay_by_image(huge, "image/jpeg")
        mock_token.assert_not_called()

    def test_unsupported_mime_type_raises(self, mock_token):
        with pytest.raises(EbayImageSearchError):
            search_ebay_by_image(JPEG_BYTES, "application/pdf")
        mock_token.assert_not_called()

    def test_payload_not_matching_declared_type_raises(self, mock_token):
        with pytest.raises(EbayImageSearchError):
            search_ebay_by_image(b"not actually an image", "image/png")
        mock_token.assert_not_called()

    def test_missing_ebay_credentials_raises_ebay_auth_error(self, mock_token):
        mock_token.side_effect = EbayAuthError("not configured")
        with pytest.raises(EbayAuthError):
            search_ebay_by_image(JPEG_BYTES, "image/jpeg")


@mock.patch("ebay_image_scan._get_ebay_access_token", return_value="tok")
class TestNetworkAndResponseHandling:
    def test_timeout_raises_search_error(self, mock_token):
        with mock.patch("requests.post", side_effect=requests.exceptions.Timeout):
            with pytest.raises(EbayImageSearchError):
                search_ebay_by_image(JPEG_BYTES, "image/jpeg")

    def test_connection_failure_raises_search_error(self, mock_token):
        with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError):
            with pytest.raises(EbayImageSearchError):
                search_ebay_by_image(JPEG_BYTES, "image/jpeg")

    def test_expired_token_401_raises_search_error(self, mock_token):
        with mock.patch("requests.post", return_value=_fake_resp(status_code=401)):
            with pytest.raises(EbayImageSearchError):
                search_ebay_by_image(JPEG_BYTES, "image/jpeg")

    def test_http_4xx_raises_search_error(self, mock_token):
        with mock.patch("requests.post", return_value=_fake_resp(status_code=400)):
            with pytest.raises(EbayImageSearchError):
                search_ebay_by_image(JPEG_BYTES, "image/jpeg")

    def test_http_5xx_raises_search_error(self, mock_token):
        with mock.patch("requests.post", return_value=_fake_resp(status_code=503)):
            with pytest.raises(EbayImageSearchError):
                search_ebay_by_image(JPEG_BYTES, "image/jpeg")

    def test_malformed_json_raises_search_error(self, mock_token):
        with mock.patch("requests.post", return_value=_fake_resp(status_code=200, json_error=True)):
            with pytest.raises(EbayImageSearchError):
                search_ebay_by_image(JPEG_BYTES, "image/jpeg")

    def test_missing_item_summaries_returns_empty_list(self, mock_token):
        with mock.patch("requests.post", return_value=_fake_resp(status_code=200, json_data={})):
            assert search_ebay_by_image(JPEG_BYTES, "image/jpeg") == []

    def test_malformed_price_data_is_skipped_not_fatal(self, mock_token):
        payload = {
            "itemSummaries": [
                {"title": "Bad price", "price": {"value": "not-a-number"}, "itemWebUrl": "https://x/1"},
                {"title": "Good item", "price": {"value": "19.99"}, "itemWebUrl": "https://x/2"},
            ]
        }
        with mock.patch("requests.post", return_value=_fake_resp(status_code=200, json_data=payload)):
            results = search_ebay_by_image(JPEG_BYTES, "image/jpeg")
        assert len(results) == 1
        assert results[0].price == 19.99

    def test_duplicate_results_are_deduplicated(self, mock_token):
        payload = {
            "itemSummaries": [
                {"title": "Same item", "price": {"value": "10"}, "itemWebUrl": "https://x/1"},
                {"title": "Same item", "price": {"value": "10"}, "itemWebUrl": "https://x/1"},
            ]
        }
        with mock.patch("requests.post", return_value=_fake_resp(status_code=200, json_data=payload)):
            results = search_ebay_by_image(JPEG_BYTES, "image/jpeg")
        assert len(results) == 1

    def test_unreasonable_result_count_is_capped(self, mock_token):
        payload = {
            "itemSummaries": [
                {"title": f"Item {i}", "price": {"value": str(i + 1)}, "itemWebUrl": f"https://x/{i}"}
                for i in range(200)
            ]
        }
        with mock.patch("requests.post", return_value=_fake_resp(status_code=200, json_data=payload)):
            results = search_ebay_by_image(JPEG_BYTES, "image/jpeg", limit=10)
        assert len(results) == 10

    def test_valid_response_returns_comps(self, mock_token):
        payload = {
            "itemSummaries": [
                {
                    "title": "Vintage Camera",
                    "price": {"value": "49.99"},
                    "itemWebUrl": "https://example.com/1",
                    "condition": "Used",
                }
            ]
        }
        with mock.patch("requests.post", return_value=_fake_resp(status_code=200, json_data=payload)):
            results = search_ebay_by_image(JPEG_BYTES, "image/jpeg")
        assert len(results) == 1
        assert results[0].title == "Vintage Camera"
        assert results[0].price == 49.99

    def test_png_and_webp_are_accepted(self, mock_token):
        with mock.patch("requests.post", return_value=_fake_resp(status_code=200, json_data={})):
            assert search_ebay_by_image(PNG_BYTES, "image/png") == []
            assert search_ebay_by_image(WEBP_BYTES, "image/webp") == []
