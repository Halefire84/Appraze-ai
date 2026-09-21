from flip_ledger import build_flip_record, calculate_flip_profit, update_flip


def test_profit_accounts_for_fee_and_shipping():
    # fee is charged on (sale + shipping_charged) = 260, not sale alone --
    # see DEAL-MATH.md / the fee-basis fix in calculate_flip_profit.
    # fee = 260 * 13% = 33.8; net_proceeds = 250+10-33.8-15 = 211.2
    result = calculate_flip_profit(100, 250, fee_pct=13, shipping_out=15, shipping_charged=10)
    assert result["platform_fee"] == 33.8
    assert result["net_proceeds"] == 211.2
    assert result["profit"] == 111.2
    assert result["margin_pct"] == 44.48
    assert result["roi_pct"] == 111.2


def test_fee_basis_includes_buyer_paid_shipping_not_just_sale_price():
    # Regression test for the 2026-09-21 audit finding: charging the fee
    # on sale price alone (ignoring buyer-paid shipping) understates the
    # real platform fee and overstates profit. With shipping_charged=100
    # and sale=0, a sale-price-only fee basis would compute $0 fee --
    # the fix must still charge fee_pct against the shipping amount.
    result = calculate_flip_profit(0, 0, fee_pct=13, shipping_charged=100)
    assert result["platform_fee"] == 13.0


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
    listed = update_flip(record, status="LISTED", list_price=150)
    sold = update_flip(listed, status="SOLD", sale_price=150, platform_fee_pct=13, shipping_out=10)
    assert sold["profit"] == 45.5
    assert sold["status"] == "SOLD"


def test_invalid_status_is_rejected():
    record = build_flip_record({"item_name": "Camera", "cost_basis": 75})
    try:
        update_flip(record, status="WHATEVER")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_lifecycle_rejects_skipping_purchase_to_sold():
    record = build_flip_record({"item_name": "Camera", "cost_basis": 75})
    try:
        update_flip(record, status="SOLD", sale_price=150)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_terminal_sold_cannot_be_reopened():
    record = build_flip_record({"item_name": "Camera", "cost_basis": 75})
    listed = update_flip(record, status="LISTED", list_price=150)
    sold = update_flip(listed, status="SOLD", sale_price=150)
    try:
        update_flip(sold, status="PURCHASED")
        assert False, "expected ValueError"
    except ValueError:
        pass
