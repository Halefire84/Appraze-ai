"""
mail_parse.py — pure, testable parsing for detecting shipment tracking
numbers, invoice/order references, and dollar amounts inside an email's
subject/body text.

Deliberately has zero dependency on Streamlit, imaplib, or the email
package (see mail.py for the actual inbox-fetching side) so it can be
unit-tested in isolation, the same way finance.py's money math is kept
separate from the Streamlit UI in app.py.

Detection is heuristic and best-effort — a regex can't reliably tell a
UPS tracking number from a random 18-character order ID, so the Mail tab
always shows the original subject/snippet alongside whatever this found,
and nothing here should ever be trusted as ground truth without a human
looking at it.
"""

import re

# Checked in order from most to least distinctive, so a UPS number never
# gets mis-tagged as a bare FedEx/DHL digit run, and longer digit-only
# formats are tried before shorter ones that could otherwise "match" a
# prefix of them.
_TRACKING_PATTERNS = [
    ("UPS", re.compile(r"\b1Z[0-9A-Z]{16}\b")),
    ("USPS", re.compile(r"\b(?:94|93|92|82)\d{18,20}\b|\b[A-Z]{2}\d{9}US\b")),
    ("FedEx", re.compile(r"\b\d{20}\b|\b\d{15}\b|\b\d{12}\b")),
    ("DHL", re.compile(r"\b\d{10}\b")),
]

_INVOICE_PATTERN = re.compile(
    r"\b(?:invoice|order|po|ref(?:erence)?)\b\s*#?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-]{3,19})",
    re.IGNORECASE,
)

_AMOUNT_PATTERN = re.compile(r"\$\s?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")

_TRACKING_KEYWORDS = ("tracking", "shipped", "shipment", "out for delivery", "delivered", "in transit")
_INVOICE_KEYWORDS = ("invoice", "receipt", "payment due", "order confirmation", "your order", "bill")


def detect_tracking(text: str):
    """Returns (carrier, tracking_number) for the first recognized carrier
    pattern found in text, or None if nothing matched."""
    if not text:
        return None
    for carrier, pattern in _TRACKING_PATTERNS:
        match = pattern.search(text)
        if match:
            return carrier, match.group(0)
    return None


def detect_invoice_ref(text: str):
    """Returns the first invoice/order/PO reference found (e.g. from
    'Invoice #A1234' or 'Order: 98-2201'), or None."""
    if not text:
        return None
    match = _INVOICE_PATTERN.search(text)
    return match.group(1) if match else None


def detect_amount(text: str):
    """Returns the first dollar amount found in text as a float, or None."""
    if not text:
        return None
    match = _AMOUNT_PATTERN.search(text)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def classify_message(subject: str, body: str) -> str:
    """Buckets a message as 'Tracking', 'Invoice', or 'Other' from keyword
    and pattern hits, for a quick-glance column in the Mail tab. Tracking
    wins over Invoice when both are present (e.g. a "shipping confirmation"
    email that also quotes the order total) since the tracking number is
    usually the more time-sensitive thing to act on."""
    combined = f"{subject or ''} {body or ''}"
    lowered = combined.lower()
    has_tracking = detect_tracking(combined) is not None
    has_tracking_kw = any(kw in lowered for kw in _TRACKING_KEYWORDS)
    has_invoice_kw = any(kw in lowered for kw in _INVOICE_KEYWORDS)
    if has_tracking or has_tracking_kw:
        return "Tracking"
    if has_invoice_kw:
        return "Invoice"
    return "Other"
