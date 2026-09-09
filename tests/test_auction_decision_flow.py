from auction_radar import enrich_auction_opportunities, rank_auction_catalog
from comps import Comp


def _record(source):
    return [{
        "lot_id": "LOT-1",
        "title": "Vintage watch",
        "price": 50,
        "buyer_premium": 10,
        "shipping": 5,
        "url": "https://example.test/lot-1",
    }]


def _comp(price, listing_type="sold"):
    return Comp(title="Vintage watch", price=price, condition="used", url="https://example.test/comp", listing_type=listing_type)


def test_ctbids_record_reaches_canonical_buy_decision():
    candidate = rank_auction_catalog("ctbids", _record("ctbids"), min_score=0)[0]
    evidence = enrich_auction_opportunities([candidate], {0: [_comp(100), _comp(120), _comp(110)]})
    result = evidence[0]["result"]
    assert result["decision"] == "BUY"
    assert result["market_value"] == 110.0
    assert result["url"] == "https://example.test/lot-1"


def test_shopgoodwill_record_reaches_canonical_review_without_comps():
    candidate = rank_auction_catalog("shopgoodwill", _record("shopgoodwill"), min_score=0)[0]
    result = enrich_auction_opportunities([candidate], {})[0]["result"]
    assert result["decision"] == "REVIEW"


def test_hibid_record_reaches_canonical_borderline_decision():
    candidate = rank_auction_catalog("hibid", _record("hibid"), min_score=0)[0]
    evidence = enrich_auction_opportunities([candidate], {0: [_comp(60), _comp(70), _comp(80)]})
    result = evidence[0]["result"]
    assert result["decision"] == "BORDERLINE"
