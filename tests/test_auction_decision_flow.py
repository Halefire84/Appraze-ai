from auction_radar import enrich_auction_opportunities, rank_auction_catalog
from comps import Comp


def _record(source, price=50):
    return [{
        "lot_id": "LOT-1",
        "title": "Vintage watch",
        "price": price,
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
    candidate = rank_auction_catalog("hibid", _record("hibid", price=65), min_score=0)[0]
    evidence = enrich_auction_opportunities([candidate], {0: [_comp(80), _comp(100), _comp(120)]})
    result = evidence[0]["result"]
    assert result["decision"] == "BORDERLINE"


def _record_missing_premium(source, price=50):
    return [{
        "lot_id": "LOT-2",
        "title": "Vintage watch",
        "price": price,
        # deliberately no buyer_premium/shipping -- auction cost unknown
        "url": "https://example.test/lot-2",
    }]


def test_unknown_buyer_premium_never_becomes_a_hard_buy():
    """A materially favorable price must not become BUY just because the
    auction's buyer premium wasn't supplied -- CRTC must never treat an
    unknown cost as $0 (see decision_policy.py / F-05)."""
    candidate = rank_auction_catalog("ctbids", _record_missing_premium("ctbids", price=10), min_score=0)[0]
    evidence = enrich_auction_opportunities([candidate], {0: [_comp(100), _comp(120), _comp(110)]})
    result = evidence[0]["result"]
    assert result["decision"] not in ("BUY", "STRONG BUY")
    assert result["decision"] == "REVIEW"


def test_acquisition_cost_shape_preserved_for_the_auction_hunt_page():
    """pages/2_Auction_Hunt.py reads meta['acquisition_cost']['all_in_cost']
    directly -- this shape must survive the decision_policy migration."""
    candidate = rank_auction_catalog("ctbids", _record("ctbids"), min_score=0)[0]
    evidence = enrich_auction_opportunities([candidate], {0: [_comp(100), _comp(120), _comp(110)]})
    cost = evidence[0]["acquisition_cost"]
    # bid=50, buyer_premium=10% of 50=5, shipping=5 => 50 + 5 + 5 = 60
    assert cost["all_in_cost"] == 60.0
    assert cost["complete"] is True
