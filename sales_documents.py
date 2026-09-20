"""CRTC lightweight customer accounts, quotes and invoices.

Pure business logic for the sales-document layer. UI/persistence stay in app.py.
This intentionally stops short of full accounting/general-ledger behavior.
"""

from datetime import date
import secrets


ACCOUNT_COLUMNS = [
    "Account #", "Business / Customer", "Contact", "Email", "Phone",
    "Billing Address", "Shipping Address", "Payment Terms", "Default Discount %",
    "Notes", "Created",
]

DOCUMENT_COLUMNS = [
    "Document #", "Type", "Account #", "Customer", "Issue Date", "Due Date",
    "Expiration Date", "Status", "Subtotal", "Discount", "Tax", "Shipping",
    "Total", "Amount Paid", "Amount Due", "Notes", "Created",
]


def money(value, default=0.0):
    try:
        value = float(value)
        if value != value or value in (float("inf"), float("-inf")):
            return default
        return value
    except (TypeError, ValueError):
        return default


def calculate_totals(items, discount_value=0.0, discount_type="fixed",
                     tax_pct=0.0, shipping=0.0):
    subtotal = 0.0
    for item in items or []:
        qty = max(0.0, money(item.get("Quantity", item.get("quantity", 0))))
        price = max(0.0, money(item.get("Unit Price", item.get("unit_price", 0))))
        subtotal += qty * price

    raw_discount = max(0.0, money(discount_value))
    if discount_type == "percent":
        discount = subtotal * min(raw_discount, 100.0) / 100.0
    else:
        discount = min(raw_discount, subtotal)

    taxable = max(0.0, subtotal - discount)
    tax = taxable * max(0.0, money(tax_pct)) / 100.0
    shipping_amount = max(0.0, money(shipping))
    total = taxable + tax + shipping_amount

    return {
        "subtotal": round(subtotal, 2),
        "discount": round(discount, 2),
        "tax": round(tax, 2),
        "shipping": round(shipping_amount, 2),
        "total": round(total, 2),
        "amount_due": round(total, 2),
    }


def new_document_number(kind="INV"):
    prefix = "QUO" if kind.upper().startswith("QUO") else "INV"
    return f"{prefix}-{date.today().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


def new_account_number():
    return f"CUS-{date.today().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


def apply_payment(total, amount_paid):
    total = max(0.0, money(total))
    paid = min(total, max(0.0, money(amount_paid)))
    due = round(total - paid, 2)
    if due <= 0:
        status = "Paid"
    elif paid > 0:
        status = "Partially Paid"
    else:
        status = "Unpaid"
    return {"amount_paid": round(paid, 2), "amount_due": due, "status": status}
