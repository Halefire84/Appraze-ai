from deal_workspace import build_deal_workspace


def test_auction_without_premium_stays_review():
    result = build_deal_workspace({"source": "HiBid", "price": 50, "shipping": 10}, 100, "MEDIUM")
    assert result["decision"] == "REVIEW"
    assert result["max_bid"] is None


def test_auction_buy_uses_all_in_target():
    result = build_deal_workspace({"source": "HiBid", "price": 50, "buyer_premium": 20, "shipping": 10}, 100, "HIGH")
    assert result["decision"] == "BUY"
    assert result["max_bid"] == 50.0


def test_missing_market_value_stays_review():
    result = build_deal_workspace({"source": "eBay", "price": 50}, None)
    assert result["decision"] == "REVIEW"
