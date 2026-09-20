import pytest
from sales_documents import calculate_totals, apply_payment


def test_fixed_discount_and_tax():
    result = calculate_totals(
        [{"Quantity": 2, "Unit Price": 50}],
        discount_value=10,
        discount_type="fixed",
        tax_pct=8,
        shipping=5,
    )
    assert result == {
        "subtotal": 100.0, "discount": 10.0, "tax": 7.2,
        "shipping": 5.0, "total": 102.2, "amount_due": 102.2,
    }


def test_percent_discount_cannot_exceed_subtotal():
    result = calculate_totals(
        [{"Quantity": 1, "Unit Price": 40}],
        discount_value=150,
        discount_type="percent",
    )
    assert result["discount"] == 40.0
    assert result["total"] == 0.0


def test_negative_inputs_are_safe():
    result = calculate_totals(
        [{"Quantity": -2, "Unit Price": 100}],
        discount_value=-5,
        tax_pct=-10,
        shipping=-2,
    )
    assert result["total"] == 0.0


@pytest.mark.parametrize(
    ("total", "paid", "status", "due"),
    [(100, 0, "Unpaid", 100), (100, 25, "Partially Paid", 75), (100, 100, "Paid", 0)],
)
def test_payment_status(total, paid, status, due):
    assert apply_payment(total, paid) == {
        "amount_paid": paid, "amount_due": due, "status": status
    }


def test_overpayment_is_capped():
    assert apply_payment(100, 150)["amount_paid"] == 100
