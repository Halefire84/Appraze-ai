from auction_source_adapters import SUPPORTED_SOURCES, build_catalog_adapter


def test_supported_auction_sources_have_safe_adapters():
    assert set(SUPPORTED_SOURCES) == {"ctbids", "shopgoodwill", "hibid"}
    assert build_catalog_adapter("ctbids").source_name == "CTBids / Estate Auctions"
    assert build_catalog_adapter("shopgoodwill").source_name == "ShopGoodwill"
    assert build_catalog_adapter("hibid").source_name == "HiBid"


def test_catalog_records_normalize_without_scraping():
    adapter = build_catalog_adapter("hibid")
    records = adapter.normalize_records([
        {
            "id": "LOT-42",
            "title": "Vintage camera",
            "price": 35,
            "url": "https://example.test/lot/42",
            "condition": "Used",
        }
    ])
    assert len(records) == 1
    assert records[0]["source"] == "HiBid"
    assert records[0]["source_listing_id"] == "LOT-42"
    assert records[0]["url"] == "https://example.test/lot/42"
    assert records[0]["title"] == "Vintage camera"


def test_unknown_source_is_rejected():
    try:
        build_catalog_adapter("unknown")
    except ValueError as exc:
        assert "Unsupported auction source" in str(exc)
    else:
        raise AssertionError("Unknown source should be rejected")
