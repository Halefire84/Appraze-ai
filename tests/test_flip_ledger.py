from flip_ledger import build_flip_record, calculate_flip_profit, update_flip


def test_profit_accounts_for_fee_and_shipping():
    result = calculate_flip_profit(100, 250, fee_pct=13, shipping_out=15, shipping_charged=10)
    assert result["platform_fee"] == 32.5
    assert result["net_proceeds"] == 212.5
    assert result["profit"] == 112.5
    assert result["margin_pct"] == 45.0
    assert result["roi_pct"] == 112.5


def test_free_find_has_infinite_roi_when_profitable():
    result = calculate_flip_profit(0, 100, fee_pct=0)
    assert result["profit"] == 100
    assert result["roi_pct"] == float("inf")


def test_zero_sale_never_divides_by_zero():
    result = calculate_flip_profit(50, 0)
    assert result["profit"] == -50
    assert result["margin_pct"] == 0


def test_intake_becomes_canonical_flip():
    record = build_flip_record({"item_name": "Camera", "cost_basis": 75, "source": "HiBid"})
    assert record["status"] == "PURCHASED"
    assert record["cost_basis"] == 75.0
    assert record["list_price"] == 0.0


def test_sold_update_calculates_realized_profit():
    record = build_flip_record({"item_name": "Camera", "cost_basis": 75})
    sold = update_flip(record, status="SOLD", sale_price=150, platform_fee_pct=13, shipping_out=10)
    assert sold["profit"] == 45.5
    assert sold["status"] == "SOLD"


def test_invalid_status_is_rejected():
    record = build_flip_record({"item_name": "Camera", "cost_basis": 75})
    try:
        update_flip(record, status="WHATEVER")
        assert False, "expected ValueError"
    except ValueError:
        pass
