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
