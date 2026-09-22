"""Regression suite for simulation findings F-01 … F-17 (P0/P1).

Every test maps to a concrete finding. Do not delete these without replacing
the coverage.
"""
from __future__ import annotations

import hmac
import hashlib
import json
import math
import time
import pytest

from decision_policy import (
    evaluate_deal,
    DECISION_BUY,
    DECISION_REVIEW,
    DECISION_CONDITIONAL_BUY,
    DECISION_PASS,
    ACQUISITION_TARGET_PCT,
)
from finance import calc_deal, five_tier_verdict
from stripe_webhooks import (
    verify_stripe_signature,
    handle_charge_refunded,
    process_webhook_event,
    update_invoice_status,
    StripeWebhookError,
    can_transition,
)
from listing_bridge import build_master_listing, _stable_sku
from listing_normalizer import normalize_listing
from number_normalize import parse_percent_points, parse_money


# ---------------------------------------------------------------------------
# F-01 — Two decision systems / dual BUY language
# ---------------------------------------------------------------------------
def test_f01_canonical_engine_discloses_roi_tier_on_70pct_buy():
    """At the 70% acquisition limit, ROI after 13% fee is ~24% → AT CEILING, not BUY."""
    market = 200.0
    price = market * 0.70  # exactly at acquisition limit (no premium/shipping)
    d = evaluate_deal(price=price, market_value=market, is_auction=False, require_shipping=False)
    assert d.decision == DECISION_BUY
    assert d.roi_tier_label in ("AT CEILING", "BORDERLINE")
    assert d.projected_roi_pct is not None
    assert d.projected_roi_pct < 40.0
    assert any("finance BUY floor" in w or "ROI" in w for w in d.warnings) or d.roi_tier == "at_ceiling"


# ---------------------------------------------------------------------------
# F-02 — Webhook replay (stale timestamp)
# ---------------------------------------------------------------------------
def test_f02_stale_signature_rejected():
    secret = "whsec_test_secret"
    payload = b'{"id":"evt_1"}'
    old_ts = str(int(time.time()) - 400 * 86400)  # 400 days ago
    signed = f"{old_ts}.".encode() + payload
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    header = f"t={old_ts},v1={sig}"
    with pytest.raises(StripeWebhookError, match="tolerance|Timestamp"):
        verify_stripe_signature(payload, header, secret)


def test_f02_fresh_signature_accepted():
    secret = "whsec_test_secret"
    payload = b'{"id":"evt_1"}'
    ts = str(int(time.time()))
    signed = f"{ts}.".encode() + payload
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    header = f"t={ts},v1={sig}"
    assert verify_stripe_signature(payload, header, secret) is True


# ---------------------------------------------------------------------------
# F-03 — Refund amount from wrong field
# ---------------------------------------------------------------------------
def test_f03_full_refund_uses_amount_refunded():
    event_data = {
        "id": "ch_1",
        "amount": 2000,  # $20.00
        "amount_refunded": 2000,
        "refunded": True,  # boolean — must NOT be used as cents
        "metadata": {"invoice_id": "POS-1"},
        "created": int(time.time()),
    }
    result = handle_charge_refunded(event_data)
    assert result["refund_amount"] == 20.0
    assert result["new_status"] == "Refunded"


def test_f03_partial_refund_status():
    event_data = {
        "id": "ch_2",
        "amount": 2000,
        "amount_refunded": 500,  # $5.00
        "refunded": False,
        "metadata": {"invoice_id": "POS-2"},
        "created": int(time.time()),
    }
    result = handle_charge_refunded(event_data)
    assert result["refund_amount"] == 5.0
    assert result["new_status"] == "Partially Refunded"


# ---------------------------------------------------------------------------
# F-04 — Category mismatch self-cancellation
# ---------------------------------------------------------------------------
def test_f04_normalizer_does_not_auto_derive_expected_keywords():
    record = {
        "title": "Vintage Nikon camera body",
        "description": "35mm SLR",
        "category": "Clothing",  # deliberately wrong
        "price": 50,
    }
    listing = normalize_listing(record)
    # Must be empty unless independently supplied — so radar can detect mismatch
    assert list(listing.get("expected_keywords") or []) == []


# ---------------------------------------------------------------------------
# F-05 — Unknown shipping must not yield hard BUY
# ---------------------------------------------------------------------------
def test_f05_unknown_shipping_not_hard_buy():
    d = evaluate_deal(
        price=100.0,
        market_value=200.0,
        is_auction=True,
        buyer_premium_pct=18.0,
        shipping=None,
        require_shipping=True,
    )
    assert d.decision in (DECISION_REVIEW, DECISION_CONDITIONAL_BUY)
    assert d.costs_complete is False


# ---------------------------------------------------------------------------
# F-06 / F-17 — buyer_premium units / fractional parse
# ---------------------------------------------------------------------------
def test_f06_buyer_premium_fraction_normalized():
    assert parse_percent_points(0.18) == 18.0
    assert parse_percent_points("18%") == 18.0
    assert parse_percent_points("18") == 18.0
    assert parse_percent_points("0.18") == 18.0


# ---------------------------------------------------------------------------
# F-08 — SKU collision
# ---------------------------------------------------------------------------
def test_f08_manual_flips_get_distinct_skus():
    flips = [
        {"item_name": f"Item {i}", "list_price": 10 + i, "status": "PURCHASED", "cost_basis": i}
        for i in range(20)
    ]
    skus = set()
    for flip in flips:
        master = build_master_listing(flip)
        skus.add(master["sku"])
    assert len(skus) == 20
    assert "CRTC-ITEM" not in skus


# ---------------------------------------------------------------------------
# F-09 — Out-of-order webhook cannot downgrade Refunded → Paid
# ---------------------------------------------------------------------------
def test_f09_out_of_order_preserves_refunded():
    log = [{"Invoice #": "POS-1", "Status": "Refunded"}]
    ok = update_invoice_status(log, "POS-1", "Paid (Card)")
    assert ok is False
    assert log[0]["Status"] == "Refunded"


def test_f09_forward_transition_allowed():
    log = [{"Invoice #": "POS-1", "Status": "Paid (Card)"}]
    ok = update_invoice_status(log, "POS-1", "Refunded")
    assert ok is True
    assert log[0]["Status"] == "Refunded"


# ---------------------------------------------------------------------------
# F-10 / F-11 / F-15 / F-16 — Invalid numbers never BUY
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -5.0, float("-inf")])
def test_f10_invalid_cost_not_buy(bad):
    d = evaluate_deal(price=bad, market_value=100.0, is_auction=False, require_shipping=False)
    assert d.decision == DECISION_REVIEW
    result = calc_deal(bad, 100.0)
    assert result.verdict == "PASS"


def test_f11_nan_resale_not_buy():
    d = evaluate_deal(price=50.0, market_value=float("nan"), is_auction=False, require_shipping=False)
    assert d.decision == DECISION_REVIEW


# ---------------------------------------------------------------------------
# F-12 — Non-ASCII signature → controlled rejection
# ---------------------------------------------------------------------------
def test_f12_non_ascii_signature_header():
    with pytest.raises(StripeWebhookError, match="Non-ASCII|signature"):
        verify_stripe_signature(b"{}", "t=1,v1=abc\u2603", "secret")


# ---------------------------------------------------------------------------
# F-13 — Any of multiple v1 signatures may match
# ---------------------------------------------------------------------------
def test_f13_secret_rotation_accepts_first_valid_v1():
    secret = "whsec_rot"
    payload = b'{"ok":true}'
    ts = str(int(time.time()))
    signed = f"{ts}.".encode() + payload
    good = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    header = f"t={ts},v1=deadbeef,v1={good}"
    assert verify_stripe_signature(payload, header, secret) is True
    header2 = f"t={ts},v1={good},v1=deadbeef"
    assert verify_stripe_signature(payload, header2, secret) is True


# ---------------------------------------------------------------------------
# Money parser basics
# ---------------------------------------------------------------------------
def test_parse_money_common_forms():
    assert parse_money("$1,234.50") == 1234.50
    assert parse_money("1234.50") == 1234.50
    assert parse_money("USD 12.50") == 12.50
    assert parse_money("nan") is None
    assert parse_money(-3) is None
