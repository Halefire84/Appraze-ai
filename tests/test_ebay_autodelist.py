"""Tests for crosslist.ebay_autodelist (auto-delist orchestration).

All eBay API interactions are mocked. No network calls, no credentials,
no real listings. Sandbox proof only.
"""

from unittest.mock import MagicMock, patch

from crosslist import ebay_autodelist
from crosslist.config import EBAY_API_SCOPES


def _make_client(offers):
    """Make a mock EbaySellClient whose GET returns the given offers list."""
    client = MagicMock()
    client.get.return_value = {"offers": offers}
    return client


def test_delist_offers_for_sku_withdraws_published():
    client = _make_client([
        {"offerId": "off1", "status": "PUBLISHED", "sku": "SKU1"},
        {"offerId": "off2", "status": "UNPUBLISHED", "sku": "SKU1"},
        {"offerId": "off3", "status": "PUBLISHED", "sku": "SKU1"},
    ])
    with patch.object(ebay_autodelist, "ebay_sell") as mock_mod:
        result = ebay_autodelist.delist_offers_for_sku(client, "SKU1")
    # Only the PUBLISHED offers are withdrawn.
    assert mock_mod.withdraw_offer.call_count == 2
    mock_mod.withdraw_offer.assert_any_call(client, "off1")
    mock_mod.withdraw_offer.assert_any_call(client, "off3")
    assert result["sku"] == "SKU1"
    assert result["offers_withdrawn"] == ["off1", "off3"]
    assert result["status"] == "delisted"
    # Offers are looked up by SKU.
    client.get.assert_called_once_with(
        "/sell/inventory/v1/offer", params={"sku": "SKU1"}
    )


def test_delist_offers_for_sku_no_live_offers():
    client = _make_client([
        {"offerId": "off1", "status": "UNPUBLISHED", "sku": "SKU1"},
    ])
    with patch.object(ebay_autodelist, "ebay_sell") as mock_mod:
        result = ebay_autodelist.delist_offers_for_sku(client, "SKU1")
    mock_mod.withdraw_offer.assert_not_called()
    assert result["status"] == "no_live_offers"
    assert result["offers_withdrawn"] == []


def test_delist_offers_for_sku_empty():
    client = _make_client([])
    with patch.object(ebay_autodelist, "ebay_sell") as mock_mod:
        result = ebay_autodelist.delist_offers_for_sku(client, "SKU1")
    mock_mod.withdraw_offer.assert_not_called()
    assert result["status"] == "no_live_offers"


def test_auto_delist_sku_end_to_end():
    with patch.object(ebay_autodelist, "ebay_sell") as mock_mod:
        mock_config = MagicMock()
        mock_mod.load_config.return_value = mock_config
        mock_mod.get_valid_access_token.return_value = "tok123"
        mock_client = MagicMock()
        mock_mod.EbaySellClient.return_value = mock_client
        with patch.object(
            ebay_autodelist,
            "delist_offers_for_sku",
            return_value={"status": "delisted", "offers_withdrawn": ["off1"]},
        ) as mock_delist:
            result = ebay_autodelist.auto_delist_sku("SKU1")
        mock_mod.load_config.assert_called_once()
        mock_mod.get_valid_access_token.assert_called_once_with(mock_config)
        mock_mod.EbaySellClient.assert_called_once_with("tok123")
        mock_delist.assert_called_once_with(mock_client, "SKU1")
        assert result["status"] == "delisted"


def test_config_scopes_include_required():
    """The crosslist config must list all three publish-proof scopes."""
    joined = " ".join(EBAY_API_SCOPES)
    assert "sell.inventory" in joined
    assert "sell.inventory.readonly" in joined
    assert "sell.account" in joined
