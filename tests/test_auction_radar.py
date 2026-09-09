from auction_radar import rank_auction_catalog, summarize_auction_scan


def _records():
    return [
        {"lot_id": "A1", "title": "vintange gold ring", "price": 500, "url": "https://example.test/a1"},
        {"lot_id": "A2", "title": "ordinary item", "price": 1000, "url": "https://example.test/a2"},
    ]


def test_auction_catalog_uses_canonical_radar_and_preserves_source():
    opportunities = rank_auction_catalog("ctbids", _records(), min_score=0)
    assert len(opportunities) == 2
    assert all(item.listing["source"] == "CTBids / Estate Auctions" for item in opportunities)
    assert opportunities[0].listing["source_listing_id"] == "A1"


def test_auction_scan_summary_has_common_shape():
    result = summarize_auction_scan("hibid", _records(), min_score=0)
    assert result["source"] == "HiBid"
    assert result["fetched"] == 2
    assert result["qualified"] == 2


def test_supported_sources_share_the_same_radar_path():
    for source in ("ctbids", "shopgoodwill", "hibid"):
        result = summarize_auction_scan(source, _records(), min_score=0)
        assert result["fetched"] == 2
        assert result["opportunities"]
