from auction_costs import calculate_auction_cost, max_bid_for_target_all_in


def test_all_in_cost_includes_premium_and_shipping():
    result = calculate_auction_cost(100, buyer_premium_pct=18, shipping=20)
    assert result["buyer_premium_amount"] == 18.0
    assert result["all_in_cost"] == 138.0
    assert result["complete"] is True


def test_max_bid_inverts_all_in_target():
    assert max_bid_for_target_all_in(138, buyer_premium_pct=18, shipping=20) == 100.0


def test_unknown_premium_does_not_fake_a_max_bid():
    result = calculate_auction_cost(100, shipping=20)
    assert result["all_in_cost"] == 120.0
    assert result["complete"] is False
    assert max_bid_for_target_all_in(100, shipping=20) is None
