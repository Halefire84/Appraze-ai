from unittest.mock import Mock

from comps import Comp, SOLD
from holy_grail_pipeline import score_listing
from valuation_bridge import value_candidate, value_candidate_from_adapter


def _candidate(price=50):
    return score_listing({
        "source": "eBay",
        "title": "Vintage camera",
        "price": price,
        "url": "https://example.com/item/1",
        "category": "Cameras",
    })


def test_no_comps_keeps_candidate_in_review():
    result = value_candidate(_candidate(), [])
    assert result["decision"] == "REVIEW"
    assert result["market_value"] is None
    assert result["max_buy_price"] is None


def test_sold_comps_supply_market_value_and_confidence():
    result = value_candidate(_candidate(), [
        Comp(price=100, source="Manual", listing_type=SOLD),
        Comp(price=120, source="Manual", listing_type=SOLD),
        Comp(price=110, source="Manual", listing_type=SOLD),
    ])
    assert result["market_value"] == 110.0
    assert result["market_confidence"] == "MEDIUM"
    assert result["max_buy_price"] == 77.0
    assert result["decision"] == "BUY"


def test_adapter_bridge_uses_existing_adapter_without_new_valuation_math():
    adapter = Mock()
    adapter.fetch_comps.return_value = [
        Comp(price=200, source="eBay", listing_type=SOLD),
        Comp(price=220, source="eBay", listing_type=SOLD),
        Comp(price=210, source="eBay", listing_type=SOLD),
    ]
    result = value_candidate_from_adapter(_candidate(price=140), adapter)
    adapter.fetch_comps.assert_called_once_with("Vintage camera", limit=20)
    assert result["market_value"] == 210.0
    assert result["max_buy_price"] == 147.0
    assert result["decision"] == "BUY"
