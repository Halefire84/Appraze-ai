"""
Unit tests for mail_parse.py - the pure tracking/invoice detection module
behind the Mail tab. No Streamlit/imaplib/email/network dependency, so
these run anywhere:

    python3 -m unittest tests.test_mail_parse -v
"""

import unittest

from mail_parse import classify_message, detect_amount, detect_invoice_ref, detect_tracking


class TestDetectTracking(unittest.TestCase):
    def test_ups(self):
        text = "Your package is on its way. Tracking number: 1Z999AA10123456784"
        self.assertEqual(detect_tracking(text), ("UPS", "1Z999AA10123456784"))

    def test_usps(self):
        text = "USPS Tracking #: 9400111899223197428490"
        self.assertEqual(detect_tracking(text), ("USPS", "9400111899223197428490"))

    def test_fedex_12_digit(self):
        text = "FedEx tracking: 123456789012 has shipped"
        self.assertEqual(detect_tracking(text), ("FedEx", "123456789012"))

    def test_dhl_10_digit(self):
        text = "DHL awb 1234567890 is in transit"
        self.assertEqual(detect_tracking(text), ("DHL", "1234567890"))

    def test_no_match_returns_none(self):
        self.assertIsNone(detect_tracking("Just checking in about last week's estate sale."))

    def test_empty_text_returns_none(self):
        self.assertIsNone(detect_tracking(""))
        self.assertIsNone(detect_tracking(None))

    def test_ups_takes_priority_over_generic_digit_runs(self):
        # A UPS number embedded alongside an unrelated 10-digit run should
        # still resolve to UPS, since it's checked first and is far more
        # distinctive than a bare digit-only pattern.
        text = "Order 1234567890 shipped via 1Z999AA10123456784"
        self.assertEqual(detect_tracking(text), ("UPS", "1Z999AA10123456784"))


class TestDetectInvoiceRef(unittest.TestCase):
    def test_invoice_hash(self):
        self.assertEqual(detect_invoice_ref("Invoice #INV-2024-88213 attached"), "INV-2024-88213")

    def test_order_colon(self):
        self.assertEqual(detect_invoice_ref("Order: 98-2201 has been confirmed"), "98-2201")

    def test_po_number(self):
        self.assertEqual(detect_invoice_ref("PO# A1234 for your records"), "A1234")

    def test_case_insensitive(self):
        self.assertEqual(detect_invoice_ref("invoice #12345"), "12345")

    def test_no_match_returns_none(self):
        self.assertIsNone(detect_invoice_ref("How's business going this week?"))

    def test_empty_text_returns_none(self):
        self.assertIsNone(detect_invoice_ref(""))


class TestDetectAmount(unittest.TestCase):
    def test_simple_amount(self):
        self.assertEqual(detect_amount("Total due: $240.00"), 240.00)

    def test_amount_with_thousands_separator(self):
        self.assertEqual(detect_amount("Grand total $1,234.56"), 1234.56)

    def test_no_match_returns_none(self):
        self.assertIsNone(detect_amount("No dollar amount in here at all"))

    def test_empty_text_returns_none(self):
        self.assertIsNone(detect_amount(""))


class TestClassifyMessage(unittest.TestCase):
    def test_tracking_from_keyword(self):
        self.assertEqual(
            classify_message("Your order has shipped!", "It's on the way to you now."),
            "Tracking",
        )

    def test_tracking_from_pattern_even_without_keyword(self):
        self.assertEqual(
            classify_message("Update on your recent purchase", "Ref 1Z999AA10123456784"),
            "Tracking",
        )

    def test_invoice_from_keyword(self):
        self.assertEqual(
            classify_message("Invoice from ABC Liquidators", "Invoice #12345 Total: $500.00, please remit payment."),
            "Invoice",
        )

    def test_tracking_wins_over_invoice_when_both_present(self):
        self.assertEqual(
            classify_message("Your invoice has shipped", "Invoice #12345, tracking attached."),
            "Tracking",
        )

    def test_other_when_neither_matches(self):
        self.assertEqual(classify_message("Hey", "Just checking in, no rush."), "Other")


if __name__ == "__main__":
    unittest.main()
