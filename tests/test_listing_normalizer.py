from listing_normalizer import normalize_listing, normalize_listings


def test_normalizes_common_marketplace_aliases():
    listing = normalize_listing({
        "marketplace": "eBay",
        "item_id": "123",
        "name": "14k gold chain",
        "details": "Vintage chain in good condition",
        "category_name": "Jewelry",
        "asking_price": "$240.00",
        "source_url": "https://example.com/item/123",
        "seller_name": "Example Seller",
        "shipping_cost": "12.50",
        "imageUrls": ["https://example.com/1.jpg"],
    })

    assert listing["source"] == "eBay"
    assert listing["source_listing_id"] == "123"
    assert listing["title"] == "14k gold chain"
    assert listing["description"] == "Vintage chain in good condition"
    assert listing["category"] == "Jewelry"
    assert listing["price"] == 240.0
    assert listing["shipping"] == 12.5
    assert listing["url"].endswith("/123")
    assert listing["images"] == ["https://example.com/1.jpg"]


def test_preserves_radar_fields_and_metadata():
    listing = normalize_listing({
        "source": "HiBid",
        "id": "lot-7",
        "title": "Vintage reciever",
        "description": "Needs gone today",
        "category": "Electronics",
        "current_bid": 100,
        "estimated_value": 400,
        "lot": "7",
        "ends_at": "2026-09-10T20:00:00Z",
    })

    assert listing["price"] == 100.0
    assert listing["estimated_value"] == 400.0
    assert listing["lot_number"] == "7"
    assert listing["auction_end"] == "2026-09-10T20:00:00Z"
    assert "source" in listing and "url" in listing
    assert "expected_keywords" in listing


def test_explicit_expected_keywords_win_over_inferred_keywords():
    listing = normalize_listing({
        "category": "Specialty",
        "title": "Vintage watch",
        "expected_keywords": ["watch", "rolex"],
    })
    assert listing["expected_keywords"] == ["watch", "rolex"]


def test_batch_normalization_preserves_order():
    listings = normalize_listings([
        {"title": "First", "price": 10},
        {"title": "Second", "price": 20},
    ], source="Test")
    assert [x["title"] for x in listings] == ["First", "Second"]
    assert all(x["source"] == "Test" for x in listings)
