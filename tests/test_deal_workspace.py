from unittest import mock

from deal_workspace import build_deal_workspace


def test_auction_without_premium_stays_review():
    result = build_deal_workspace({"source": "HiBid", "price": 50, "shipping": 10}, 100, "MEDIUM")
    assert result["decision"] == "REVIEW"
    assert result["max_bid"] is None


def test_build_deal_workspace_logs_the_decision():
    # Observability requirement: every deal evaluation must produce a
    # log_event() call for operator visibility (financial decisions), not
    # just payment events. build_deal_workspace() is the one canonical
    # entry point every caller goes through, so this is the single place
    # that needs to be checked, rather than every individual caller.
    with mock.patch("deal_workspace.log_event") as mock_log:
        result = build_deal_workspace({"source": "HiBid", "price": 50, "buyer_premium": 20, "shipping": 10}, 100, "HIGH")

    mock_log.assert_called_once()
    args, _kwargs = mock_log.call_args
    assert args[0] == "INFO"
    assert args[1] == "decision"
    context = args[4]
    assert context["decision"] == result["decision"] == "BUY"
    assert context["roi_tier"] == result["roi_tier"]


def test_auction_buy_uses_all_in_target():
    result = build_deal_workspace({"source": "HiBid", "price": 50, "buyer_premium": 20, "shipping": 10}, 100, "HIGH")
    assert result["decision"] == "BUY"
    assert result["max_bid"] == 50.0
    assert result["all_in"]["all_in_cost"] == 70.0


def test_missing_market_value_stays_review():
    result = build_deal_workspace({"source": "eBay", "price": 50}, None)
    assert result["decision"] == "REVIEW"
