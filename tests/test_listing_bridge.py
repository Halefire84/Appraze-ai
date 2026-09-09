import pytest

from listing_bridge import build_master_listing


def test_purchased_flip_becomes_master_listing():
    result = build_master_listing({
        "status": "PURCHASED",
        "item_name": "Vintage Camera",
        "source": "HiBid",
        "source_listing_id": "H1",
        "cost_basis": 75,
        "list_price": 199,
        "notes": "Cleaned and tested",
    })
    assert result["title"] == "Vintage Camera"
    assert result["price"] == 199.0
    assert result["cost"] == 75.0
    assert result["status"] == "MASTER_READY"
    assert result["source_listing_id"] == "H1"


def test_unsold_or_passed_flip_cannot_be_listed():
    with pytest.raises(ValueError):
        build_master_listing({"status": "SOLD", "item_name": "Camera", "list_price": 100})


def test_listing_requires_positive_price():
    with pytest.raises(ValueError):
        build_master_listing({"status": "PURCHASED", "item_name": "Camera", "list_price": 0})
