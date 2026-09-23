from crtc_opportunity import build_opportunity
from holy_grail_pipeline import score_listing


def test_opportunity_requires_market_evidence_for_decision():
    candidate = score_listing({
        "source": "eBay",
        "title": "vinta ge gold ring",
        "price": 50,
        "url": "https://example.com/item/1",
        "category": "Jewelry",
    })
    result = build_opportunity(candidate)
    assert result.decision == "REVIEW"
    assert result.radar_score == candidate.score
    assert result.market_value is None
    assert result.max_buy_price is None


def test_opportunity_uses_seventy_percent_target_when_value_exists():
    candidate = score_listing({
        "source": "CTBids",
        "title": "vintage camera lot",
        "price": 60,
        "estimated_value": 120,
        "url": "https://example.com/item/2",
        "category": "Cameras",
    })
    result = build_opportunity(candidate, market_confidence="MEDIUM")
    assert result.max_buy_price == 84.0
    assert result.decision == "BUY"
    assert result.market_confidence == "MEDIUM"


def test_opportunity_can_be_borderline():
    candidate = score_listing({
        "source": "eBay",
        "title": "vintage receiver",
        "price": 80,
        "estimated_value": 100,
        "url": "https://example.com/item/3",
        "category": "Electronics",
    })
    result = build_opportunity(candidate)
    assert result.decision == "BORDERLINE"


def test_opportunity_all_in_cost_includes_shipping_and_tax_not_just_price():
    # price=60, value=120 -> 70% target is $84. Bare item price alone
    # ($60) is well within target, but known shipping ($15) + tax ($10)
    # push the true all-in cost to $85 -- one dollar over target. The BUY
    # verdict must be based on that all-in cost, not the bare item price.
    candidate = score_listing({
        "source": "eBay",
        "title": "vintage camera lot",
        "price": 60,
        "estimated_value": 120,
        "shipping": 15,
        "tax": 10,
        "url": "https://example.com/item/4",
        "category": "Cameras",
    })
    result = build_opportunity(candidate, market_confidence="MEDIUM")
    assert result.decision != "BUY"


def test_opportunity_still_buys_when_all_in_cost_clears_target():
    # Same shipping/tax as above, but a smaller combined add-on ($5 total)
    # keeps all-in cost ($65) under the $84 target -- still a BUY.
    candidate = score_listing({
        "source": "eBay",
        "title": "vintage camera lot",
        "price": 60,
        "estimated_value": 120,
        "shipping": 3,
        "tax": 2,
        "url": "https://example.com/item/5",
        "category": "Cameras",
    })
    result = build_opportunity(candidate, market_confidence="MEDIUM")
    assert result.decision == "BUY"
