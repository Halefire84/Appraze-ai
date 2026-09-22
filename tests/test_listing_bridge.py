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


def test_image_urls_carry_through_to_master_listing():
    # Regression for a real bug: this used to be written out as "photos",
    # a key nothing downstream ever read (ebay_sell.py's
    # master_to_inventory_item() and pages/5_Cross_List.py's production
    # publish payload both read "image_urls"/draft["image_urls"]) -- every
    # eBay listing published through this pipeline went out with zero
    # images regardless of what a flip actually had.
    result = build_master_listing({
        "status": "PURCHASED",
        "item_name": "Vintage Camera",
        "list_price": 199,
        "image_urls": ["https://example.com/a.jpg", "https://example.com/b.jpg"],
    })
    assert result["image_urls"] == ["https://example.com/a.jpg", "https://example.com/b.jpg"]
    assert "photos" not in result


def test_missing_image_urls_defaults_to_empty_list_not_missing_key():
    result = build_master_listing({"status": "PURCHASED", "item_name": "Camera", "list_price": 50})
    assert result["image_urls"] == []
