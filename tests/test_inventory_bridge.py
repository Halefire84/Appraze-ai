import pytest

from inventory_bridge import build_inventory_intake


def test_buy_decision_creates_inventory_intake():
    result = build_inventory_intake(
        {"title": "Vintage camera", "source": "eBay", "source_listing_id": "123", "url": "https://example.com", "radar_score": 82},
        {"decision": "BUY", "market_value": 200, "all_in": {"all_in_cost": 70}},
    )
    assert result["item_name"] == "Vintage camera"
    assert result["cost_basis"] == 70.0
    assert result["status"] == "PURCHASE_PENDING"


def test_non_buy_cannot_enter_inventory():
    with pytest.raises(ValueError):
        build_inventory_intake({"title": "Camera", "price": 50}, {"decision": "BORDERLINE"})
