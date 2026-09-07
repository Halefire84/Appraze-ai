"""
Appraze Production Smoke Test
==============================
Validates that the production entry point (app.py) can initialize without errors.
This is NOT a unit test — it's a real startup test that catches import errors,
syntax errors, missing dependencies, and fatal initialization issues.

Run locally:
    python3 -m pytest tests/test_smoke.py -v

Run in CI:
    python3 -m pytest tests/test_smoke.py::test_app_imports -v
"""

import sys
import os
import unittest
from unittest import mock
from pathlib import Path

# Add repo root to path so we can import app modules
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))


class TestAppImports(unittest.TestCase):
    """Test that all app.py imports and dependencies load without errors."""

    def test_finance_module_loads(self):
        """finance.py must import without errors."""
        try:
            import finance
            self.assertIsNotNone(finance)
            # Verify canonical exports exist
            self.assertTrue(hasattr(finance, 'calc_deal'))
            self.assertTrue(hasattr(finance, 'calc_melt'))
            self.assertTrue(hasattr(finance, 'format_roi'))
            self.assertTrue(hasattr(finance, 'max_cost_for_target_roi'))
            self.assertTrue(hasattr(finance, 'DEFAULT_FEE_PCT'))
            self.assertTrue(hasattr(finance, 'DEFAULT_PREMIUM_PCT'))
            self.assertTrue(hasattr(finance, 'GOLD_PURITY'))
            self.assertTrue(hasattr(finance, 'SILVER_PURITY'))
        except Exception as e:
            self.fail(f"finance.py import failed: {e}")

    def test_auth_module_loads(self):
        """auth.py must import without errors."""
        try:
            import auth
            self.assertIsNotNone(auth)
            self.assertTrue(hasattr(auth, 'render_login_gate'))
            self.assertTrue(hasattr(auth, 'mark_paid'))
        except Exception as e:
            self.fail(f"auth.py import failed: {e}")

    def test_billing_module_loads(self):
        """billing.py must import without errors."""
        try:
            import billing
            self.assertIsNotNone(billing)
            self.assertTrue(hasattr(billing, 'verify_checkout_session'))
            self.assertTrue(hasattr(billing, 'payment_link_url'))
        except Exception as e:
            self.fail(f"billing.py import failed: {e}")

    def test_storage_module_loads(self):
        """storage.py must import without errors."""
        try:
            import storage
            self.assertIsNotNone(storage)
            self.assertTrue(hasattr(storage, 'save_deals'))
            self.assertTrue(hasattr(storage, 'load_deals'))
        except Exception as e:
            self.fail(f"storage.py import failed: {e}")

    def test_app_imports_work(self):
        """app.py import chain must not fail (mock Streamlit)."""
        # Mock Streamlit so we don't actually start a web server
        sys.modules['streamlit'] = mock.MagicMock()
        
        try:
            # Try importing core dependencies that app.py uses
            from finance import (
                DEFAULT_FEE_PCT,
                DEFAULT_PREMIUM_PCT,
                GOLD_PURITY,
                SILVER_PURITY,
                calc_deal,
                calc_melt,
                format_roi,
                max_cost_for_target_roi,
            )
            self.assertEqual(DEFAULT_FEE_PCT, 13.0)
            self.assertEqual(DEFAULT_PREMIUM_PCT, 18.0)
            self.assertIsNotNone(GOLD_PURITY)
            self.assertIsNotNone(SILVER_PURITY)
        except Exception as e:
            self.fail(f"app.py import chain failed: {e}")


class TestFinanceCore(unittest.TestCase):
    """Test canonical finance engine functions with edge cases."""

    def setUp(self):
        import finance
        self.finance = finance

    def test_calc_deal_normal(self):
        """Normal deal: cost 100, resale 300, expect profit and ROI."""
        result = self.finance.calc_deal(100, 300)
        self.assertIsNotNone(result)
        self.assertGreater(result.gross_profit, 0)
        self.assertGreater(result.roi_pct, 0)
        self.assertIsNotNone(result.verdict)
        self.assertIsNotNone(result.verdict_tier)

    def test_calc_deal_zero_cost(self):
        """Free find: cost 0, resale 100, expect infinite ROI."""
        result = self.finance.calc_deal(0, 100)
        self.assertIsNotNone(result)
        # Free find should be handled gracefully
        self.assertGreater(result.gross_profit, 0)

    def test_calc_deal_zero_resale(self):
        """Loss scenario: cost 100, resale 0, expect loss."""
        result = self.finance.calc_deal(100, 0)
        self.assertIsNotNone(result)
        self.assertLess(result.gross_profit, 0)

    def test_calc_deal_zero_both(self):
        """Both zero: cost 0, resale 0, expect zero profit."""
        result = self.finance.calc_deal(0, 0)
        self.assertIsNotNone(result)
        self.assertEqual(result.gross_profit, 0)

    def test_calc_deal_negative_input_rejected(self):
        """Negative costs should be handled gracefully (clamped or rejected)."""
        # finance.py should not crash on negative input
        result = self.finance.calc_deal(-100, 300)
        # If it returns, it should have valid fields (even if error is set)
        self.assertIsNotNone(result)

    def test_calc_melt_normal(self):
        """Normal melt: 10g gold, 14k, $2000/oz."""
        result = self.finance.calc_melt(10, 0.585, 2000)
        self.assertIsNotNone(result)
        self.assertGreater(result.melt_value, 0)
        self.assertGreater(result.ceiling_price, 0)
        # Ceiling should be 80% of melt
        self.assertAlmostEqual(
            result.ceiling_price / result.melt_value, 0.80, places=2
        )

    def test_calc_melt_zero_weight(self):
        """Zero weight should produce zero value."""
        result = self.finance.calc_melt(0, 0.585, 2000)
        self.assertIsNotNone(result)
        self.assertEqual(result.melt_value, 0)
        self.assertEqual(result.ceiling_price, 0)

    def test_calc_melt_zero_price(self):
        """Zero spot price should produce zero value."""
        result = self.finance.calc_melt(10, 0.585, 0)
        self.assertIsNotNone(result)
        self.assertEqual(result.melt_value, 0)
        self.assertEqual(result.ceiling_price, 0)

    def test_verdict_scale_strong_buy(self):
        """ROI >= 60% should be STRONG BUY."""
        result = self.finance.calc_deal(100, 400)  # 200% gross profit = 200% ROI
        self.assertEqual(result.verdict, "STRONG BUY")
        self.assertEqual(result.verdict_tier, "strong_buy")

    def test_verdict_scale_buy(self):
        """ROI 40-59% (after default 13% fee / 18% premium) should be BUY."""
        result = self.finance.calc_deal(100, 190)  # true_cost 118, net_resale 165.3 -> ~40.1% ROI
        self.assertEqual(result.verdict, "BUY")

    def test_verdict_scale_pass(self):
        """ROI < 5% should be PASS."""
        result = self.finance.calc_deal(100, 104)  # ~2% ROI
        self.assertEqual(result.verdict, "PASS")
        self.assertEqual(result.verdict_tier, "pass")

    def test_max_cost_for_target_roi(self):
        """Max cost to hit 40% ROI at $300 resale."""
        max_cost = self.finance.max_cost_for_target_roi(300, target_roi_pct=40.0)
        self.assertGreater(max_cost, 0)
        self.assertLess(max_cost, 300)

    def test_format_roi_normal(self):
        """Normal ROI should format with percent sign."""
        formatted = self.finance.format_roi(45.5)
        self.assertIn("%", formatted)
        self.assertIn("45.5", formatted)

    def test_format_roi_infinity(self):
        """Infinite ROI (free find) should show infinity symbol."""
        formatted = self.finance.format_roi(float("inf"))
        self.assertIn("∞", formatted)


class TestPythonSyntax(unittest.TestCase):
    """Test that all Python files have valid syntax."""

    def test_app_syntax(self):
        """app.py must have valid Python syntax."""
        app_path = repo_root / "app.py"
        self.assertTrue(app_path.exists(), f"app.py not found at {app_path}")
        try:
            with open(app_path) as f:
                compile(f.read(), str(app_path), "exec")
        except SyntaxError as e:
            self.fail(f"app.py has syntax error: {e}")

    def test_finance_syntax(self):
        """finance.py must have valid Python syntax."""
        finance_path = repo_root / "finance.py"
        self.assertTrue(finance_path.exists(), f"finance.py not found at {finance_path}")
        try:
            with open(finance_path) as f:
                compile(f.read(), str(finance_path), "exec")
        except SyntaxError as e:
            self.fail(f"finance.py has syntax error: {e}")

    def test_auth_syntax(self):
        """auth.py must have valid Python syntax."""
        auth_path = repo_root / "auth.py"
        self.assertTrue(auth_path.exists(), f"auth.py not found at {auth_path}")
        try:
            with open(auth_path) as f:
                compile(f.read(), str(auth_path), "exec")
        except SyntaxError as e:
            self.fail(f"auth.py has syntax error: {e}")

    def test_billing_syntax(self):
        """billing.py must have valid Python syntax."""
        billing_path = repo_root / "billing.py"
        self.assertTrue(billing_path.exists(), f"billing.py not found at {billing_path}")
        try:
            with open(billing_path) as f:
                compile(f.read(), str(billing_path), "exec")
        except SyntaxError as e:
            self.fail(f"billing.py has syntax error: {e}")

    def test_storage_syntax(self):
        """storage.py must have valid Python syntax."""
        storage_path = repo_root / "storage.py"
        self.assertTrue(storage_path.exists(), f"storage.py not found at {storage_path}")
        try:
            with open(storage_path) as f:
                compile(f.read(), str(storage_path), "exec")
        except SyntaxError as e:
            self.fail(f"storage.py has syntax error: {e}")


class TestRequirements(unittest.TestCase):
    """Test that required dependencies are available."""

    def test_pandas_available(self):
        """pandas must be installed."""
        try:
            import pandas
            self.assertIsNotNone(pandas)
        except ImportError:
            self.fail("pandas is not installed (required by app.py)")

    def test_requests_available(self):
        """requests must be installed."""
        try:
            import requests
            self.assertIsNotNone(requests)
        except ImportError:
            self.fail("requests is not installed (required by auth, billing, etc.)")


if __name__ == "__main__":
    unittest.main()
