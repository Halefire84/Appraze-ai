"""
decision_policy.py — Canonical CRTC deal decision authority.

ONE source of truth for:
  estimated resale value, acquisition cost components, projected profit/ROI,
  maximum allowable acquisition price, confidence, and final recommendation.

All other modules (deal_workspace, auction_radar, crtc_opportunity, pages)
MUST consume evaluate_deal() / build_decision() rather than inventing their
own BUY thresholds.

Policy (documented, tested, not silently changed):
  - Target acquisition: all-in cost <= 70% of estimated market value
    (the classic CRTC 70% rule). This is the acquisition ceiling.
  - ROI tiers (after known fees) are reported alongside every decision:
      STRONG BUY  ROI >= 60%
      BUY         ROI >= 40%
      AT CEILING  ROI >= 20%
      BORDERLINE  ROI >= 5%
      PASS        ROI < 5%
  - A workspace-style "BUY" (at the 70% limit) typically yields ~24% ROI
    after a 13% resale fee and is therefore labeled AT CEILING on the
    finance scale. Callers must surface BOTH the acquisition decision
    and the implied ROI tier so the dual language is explicit, not hidden.
  - Unknown material costs (shipping when required, buyer premium on auctions)
    NEVER become $0. Decision becomes REVIEW or CONDITIONAL_BUY with the
    missing assumption listed.
  - Invalid numbers (NaN, Inf, negative prices) never produce BUY/STRONG BUY.

Cost states: KNOWN | UNKNOWN | ESTIMATED | NOT_APPLICABLE
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from finance import (
    DEFAULT_FEE_PCT,
    DEFAULT_PREMIUM_PCT,
    calc_deal,
    five_tier_verdict,
    max_cost_for_target_roi,
    format_roi,
)
from deal_settings import (
    DealMathSettings,
    category_fee_pct as _category_fee_pct,
    estimate_shipping_cost,
    key_attribute_for_category,
    PHOTO_CONFIDENCE_MACRO_NO_SCALE,
    PHOTO_CONFIDENCE_UNKNOWN,
)

# ---------------------------------------------------------------------------
# Canonical constants (single place to retune)
# ---------------------------------------------------------------------------
ACQUISITION_TARGET_PCT = 70.0          # all-in cost as % of market value
ROI_BUY_FLOOR_PCT = 40.0               # finance BUY tier floor
ROI_STRONG_BUY_PCT = 60.0
ROI_AT_CEILING_PCT = 20.0
ROI_BORDERLINE_PCT = 5.0
DEFAULT_RESALE_FEE_PCT = DEFAULT_FEE_PCT

COST_KNOWN = "KNOWN"
COST_UNKNOWN = "UNKNOWN"
COST_ESTIMATED = "ESTIMATED"
COST_NA = "NOT_APPLICABLE"

# Decision labels (explicit, documented)
DECISION_BUY = "BUY"
DECISION_STRONG_BUY = "STRONG BUY"
DECISION_AT_CEILING = "AT CEILING"
DECISION_BORDERLINE = "BORDERLINE"
DECISION_PASS = "PASS"
DECISION_REVIEW = "REVIEW"
DECISION_CONDITIONAL_BUY = "CONDITIONAL BUY"


@dataclass
class CostComponent:
    name: str
    amount: Optional[float]
    state: str  # KNOWN | UNKNOWN | ESTIMATED | NOT_APPLICABLE
    unit: str = "USD"  # USD | pct

    def is_material_unknown(self) -> bool:
        return self.state == COST_UNKNOWN and self.unit == "USD"


@dataclass
class DealDecision:
    """Canonical result every consumer must use."""
    decision: str
    reason: str
    market_value: Optional[float]
    confidence: str
    acquisition_target_all_in: Optional[float]
    max_bid_or_price: Optional[float]
    all_in_cost: Optional[float]
    projected_roi_pct: Optional[float]
    projected_profit_usd: Optional[float]
    roi_tier: str
    roi_tier_label: str
    costs_complete: bool
    cost_components: List[CostComponent] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # Explicit dual-scale disclosure
    acquisition_rule: str = f"all-in <= {ACQUISITION_TARGET_PCT:.0f}% of market value"
    finance_buy_floor_roi_pct: float = ROI_BUY_FLOOR_PCT

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["cost_components"] = [asdict(c) for c in self.cost_components]
        return d


def _is_invalid_number(value: Any) -> bool:
    if value is None:
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return True
    return math.isnan(v) or math.isinf(v)


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


# ---------------------------------------------------------------------------
# Brief item 9 -- structured buy -> outcome event capture.
#
# An append-only log of every verdict CRTC hands back, keyed by event_id, so
# a later actual-sale outcome can be attached to the same row. This is the
# data flywheel: buy cost, predicted profit/ROI at verdict time now, actual
# sale price/fees/dates later. Deliberately simple (JSON lines) -- no DB,
# no schema migration, just an append + a lookup-and-append-again for the
# outcome half. Recalibrating the haircuts/trims/defaults in this file and
# comps.py from real outcomes is future work; this only builds the capture.
# ---------------------------------------------------------------------------
DEFAULT_EVENT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "deal_events.jsonl"
)


class EventLog:
    """Append-only buy -> outcome event log, JSON lines on disk.

    Thread-safe for simple append use (a lock around file writes); not a
    database -- fine for CRTC's single-user, single-process deployment.
    """

    def __init__(self, path: Optional[str] = None, *, in_memory: bool = False):
        self.path = path or DEFAULT_EVENT_LOG_PATH
        self.in_memory = in_memory
        self._lock = threading.Lock()
        self._buffer: List[Dict[str, Any]] = []

    def record_verdict(
        self,
        *,
        inputs: Dict[str, Any],
        decision: "DealDecision",
        deal_id: Optional[str] = None,
    ) -> str:
        """Append a new event at verdict time. Returns the event_id so the
        caller can attach an actual outcome later via record_outcome()."""
        event_id = deal_id or uuid.uuid4().hex
        record = {
            "event_id": event_id,
            "verdict_at": time.time(),
            "inputs": inputs,
            "verdict": decision.decision,
            "roi_tier": decision.roi_tier_label,
            "predicted_profit_usd": decision.projected_profit_usd,
            "predicted_roi_pct": decision.projected_roi_pct,
            "all_in_cost": decision.all_in_cost,
            "market_value": decision.market_value,
            # Outcome fields are filled in later by record_outcome(); present
            # up front (as null) so every row has a stable schema to parse.
            "outcome_at": None,
            "actual_sale_price": None,
            "actual_fees": None,
            "actual_shipping": None,
            "actual_profit_usd": None,
            "outcome_notes": None,
        }
        self._append(record)
        return event_id

    def record_outcome(
        self,
        event_id: str,
        *,
        actual_sale_price: Optional[float] = None,
        actual_fees: Optional[float] = None,
        actual_shipping: Optional[float] = None,
        outcome_notes: Optional[str] = None,
    ) -> None:
        """Append an outcome row for a previously-recorded event_id. Kept
        append-only (rather than rewriting the original line) so the log
        never needs in-place file edits."""
        record = {
            "event_id": event_id,
            "outcome_at": time.time(),
            "actual_sale_price": actual_sale_price,
            "actual_fees": actual_fees,
            "actual_shipping": actual_shipping,
            "actual_profit_usd": (
                round(actual_sale_price - (actual_fees or 0.0) - (actual_shipping or 0.0), 2)
                if actual_sale_price is not None
                else None
            ),
            "outcome_notes": outcome_notes,
        }
        self._append(record)

    def _append(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._buffer.append(record)
            if not self.in_memory:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "a") as f:
                    # default=str: inputs can carry a DealMathSettings or
                    # other non-JSON-native object; never let logging crash
                    # the verdict path over a serialization detail.
                    f.write(json.dumps(record, default=str) + "\n")

    def flush(self) -> List[Dict[str, Any]]:
        """Return (and keep) all events recorded this session. For
        in_memory logs this is the only place the data lives; for
        file-backed logs it's a convenience mirror of what was written."""
        with self._lock:
            return list(self._buffer)


_default_event_log: Optional[EventLog] = None


def get_event_log() -> EventLog:
    """Process-wide default event log (file-backed, data/deal_events.jsonl)."""
    global _default_event_log
    if _default_event_log is None:
        _default_event_log = EventLog()
    return _default_event_log


def _evaluate_deal(
    *,
    price: Optional[float],
    market_value: Optional[float],
    confidence: str = "UNKNOWN",
    is_auction: bool = False,
    buyer_premium_pct: Optional[float] = None,
    shipping: Optional[float] = None,
    other_fees: Optional[float] = None,
    resale_fee_pct: Optional[float] = None,
    require_shipping: bool = True,
    category: Optional[str] = None,
    weight_lb: Optional[float] = None,
    packaging_type: Optional[str] = None,
    apply_default_auction_fees: bool = False,
    missing_key_attribute: bool = False,
    photo_confidence: str = PHOTO_CONFIDENCE_UNKNOWN,
    comps_warnings: Optional[List[str]] = None,
    settings: Optional[DealMathSettings] = None,
    enforce_min_profit: bool = False,
) -> DealDecision:
    """
    Canonical decision engine.

    price: current bid (auction) or asking price (fixed-price)
    market_value: estimated resale / comps value (before resale fees)
    buyer_premium_pct: percentage points (18 means 18%), never dollars
    shipping / other_fees: absolute USD amounts
    resale_fee_pct: if omitted, resolved from `category` via the
        category-aware eBay fee table in deal_settings.py (brief item 1) --
        never a flat 13% guess.
    category / weight_lb / packaging_type: when shipping is omitted and
        either of these is supplied, shipping is estimated from the
        weight-tier table (brief item 2) instead of being left UNKNOWN.
    apply_default_auction_fees: opt-in. When True and is_auction, an
        omitted buyer_premium_pct / other_fees falls back to
        settings.buyer_premium_pct / settings.per_lot_fee (brief item 3)
        rather than the stricter "unknown cost blocks BUY" path. Off by
        default so existing "unknown premium must never become a silent
        BUY" behavior (F-05) is unchanged unless a caller opts in.
    missing_key_attribute: item 6 -- listing omits a category value driver
        (e.g. jewelry weight). Discounts market_value and flags a
        "verify before buying" prompt.
    photo_confidence: item 7 -- PHOTO_CONFIDENCE_MACRO_NO_SCALE discounts
        market_value and nudges the user to request more photos/inspect.
    comps_warnings: pass through comps.summarize_comps()'s warnings (thin
        comps / comps-disagree signals) so they surface on this verdict.
    enforce_min_profit: item 8 -- opt-in. When True, a would-be BUY/BORDERLINE
        whose projected dollar profit falls below settings.min_profit
        (default $10, user-editable) is downgraded to PASS with a warning.
        Off by default, same convention as apply_default_auction_fees, so
        existing callers of the acquisition-rule engine are unaffected
        unless they opt in; deal_settings.passes_min_thresholds() remains
        the standalone gate for radar/holy-grail-style candidate filtering.
    """
    settings = settings or DealMathSettings()
    warnings: List[str] = list(comps_warnings or [])
    assumptions: List[str] = []
    components: List[CostComponent] = []

    if resale_fee_pct is None:
        resale_fee_pct = _category_fee_pct(category, settings)

    if is_auction and apply_default_auction_fees:
        if buyer_premium_pct is None:
            buyer_premium_pct = settings.buyer_premium_pct
            assumptions.append(f"Buyer premium defaulted to {settings.buyer_premium_pct:g}% (no listing-specific premium supplied).")
        if other_fees is None:
            other_fees = settings.per_lot_fee
            assumptions.append(f"Per-lot auction fee defaulted to ${settings.per_lot_fee:.2f}.")

    # --- Reject invalid financial inputs ---
    if _is_invalid_number(price) or (price is not None and float(price) < 0):
        return DealDecision(
            decision=DECISION_REVIEW,
            reason="Invalid or negative price; cannot form a financial decision.",
            market_value=_safe_float(market_value),
            confidence=confidence,
            acquisition_target_all_in=None,
            max_bid_or_price=None,
            all_in_cost=None,
            projected_roi_pct=None,
            projected_profit_usd=None,
            roi_tier="pass",
            roi_tier_label=DECISION_PASS,
            costs_complete=False,
            warnings=["Invalid price input"],
        )
    if _is_invalid_number(market_value) or (market_value is not None and float(market_value) < 0):
        return DealDecision(
            decision=DECISION_REVIEW,
            reason="Invalid or negative market value; cannot form a financial decision.",
            market_value=None,
            confidence=confidence,
            acquisition_target_all_in=None,
            max_bid_or_price=None,
            all_in_cost=None,
            projected_roi_pct=None,
            projected_profit_usd=None,
            roi_tier="pass",
            roi_tier_label=DECISION_PASS,
            costs_complete=False,
            warnings=["Invalid market_value input"],
        )

    price_f = _safe_float(price)
    value_f = _safe_float(market_value)

    if price_f is None:
        return DealDecision(
            decision=DECISION_REVIEW,
            reason="No asking/current-bid price supplied.",
            market_value=value_f,
            confidence=confidence,
            acquisition_target_all_in=None,
            max_bid_or_price=None,
            all_in_cost=None,
            projected_roi_pct=None,
            projected_profit_usd=None,
            roi_tier="pass",
            roi_tier_label=DECISION_PASS,
            costs_complete=False,
        )
    if value_f is None:
        return DealDecision(
            decision=DECISION_REVIEW,
            reason="Market-value evidence is required before a purchase decision.",
            market_value=None,
            confidence=confidence,
            acquisition_target_all_in=None,
            max_bid_or_price=None,
            all_in_cost=None,
            projected_roi_pct=None,
            projected_profit_usd=None,
            roi_tier="pass",
            roi_tier_label=DECISION_PASS,
            costs_complete=False,
        )

    # --- Item 6: hidden/missing-attribute uncertainty discount ---
    if missing_key_attribute:
        attr = key_attribute_for_category(category) or "a key attribute"
        value_f = value_f * (1 - settings.missing_attribute_discount_pct / 100.0)
        warnings.append(
            f"Missing {attr} -- verify before buying. Applied a "
            f"{settings.missing_attribute_discount_pct:g}% uncertainty discount to the estimate."
        )

    # --- Item 7: photo-presentation risk discount ---
    if photo_confidence == PHOTO_CONFIDENCE_MACRO_NO_SCALE:
        value_f = value_f * (1 - settings.photo_risk_discount_pct / 100.0)
        warnings.append(
            "No scale reference in photos -- request more photos or inspect in person. "
            f"Applied a {settings.photo_risk_discount_pct:g}% confidence discount."
        )

    target_all_in = round(value_f * (ACQUISITION_TARGET_PCT / 100.0), 2)

    # --- Build cost components with explicit states ---
    premium_pct = _safe_float(buyer_premium_pct)
    ship = _safe_float(shipping)
    fees = _safe_float(other_fees)

    # --- Item 2: weight-tiered shipping estimate when shipping is omitted
    # but a weight or category is available (opt-in: callers that supply
    # neither keep the old UNKNOWN-shipping behavior, see F-05). ---
    ship_state_override: Optional[str] = None
    if ship is None and (weight_lb is not None or category is not None):
        est_total, _tier_cost, _pack_cost, weight_source = estimate_shipping_cost(
            weight_lb, category, packaging_type, settings
        )
        ship = est_total
        ship_state_override = COST_ESTIMATED
        weight_note = "given weight" if weight_source == "given" else "category-default weight (verify actual weight)"
        assumptions.append(f"Shipping estimated at ${est_total:.2f} from weight tier + packaging ({weight_note}).")

    if is_auction:
        if premium_pct is None:
            components.append(CostComponent("buyer_premium", None, COST_UNKNOWN, "pct"))
        else:
            if premium_pct < 0 or premium_pct > 100:
                warnings.append(f"Unusual buyer_premium_pct={premium_pct}")
            prem_amt = price_f * premium_pct / 100.0
            components.append(CostComponent("buyer_premium", round(prem_amt, 2), COST_KNOWN, "USD"))
            components.append(CostComponent("buyer_premium_pct", premium_pct, COST_KNOWN, "pct"))
    else:
        components.append(CostComponent("buyer_premium", 0.0, COST_NA, "USD"))

    if require_shipping or is_auction:
        if ship is None:
            components.append(CostComponent("shipping", None, COST_UNKNOWN, "USD"))
        else:
            components.append(CostComponent("shipping", round(ship, 2), ship_state_override or COST_KNOWN, "USD"))
    else:
        # Non-auction, shipping not required: still record a *known* shipping
        # dollar amount when one was actually supplied, rather than always
        # reporting 0.0 -- otherwise a listing with a real shipping cost has
        # it silently dropped from all_in_cost just because it isn't
        # mandatory here (fix: non-auction all-in cost must include known
        # shipping/fees, not just the item price).
        components.append(
            CostComponent("shipping", round(ship, 2) if ship is not None else 0.0,
                          COST_NA if ship is None else COST_KNOWN, "USD")
        )

    if fees is not None:
        components.append(CostComponent("other_fees", round(fees, 2), COST_KNOWN, "USD"))
    else:
        components.append(CostComponent("other_fees", 0.0, COST_NA, "USD"))

    material_unknown = [c for c in components if c.is_material_unknown()]
    premium_unknown = is_auction and premium_pct is None

    # All-in cost: only sum KNOWN / NA amounts; never invent 0 for UNKNOWN
    known_addons = 0.0
    for c in components:
        if c.state in (COST_KNOWN, COST_NA, COST_ESTIMATED) and c.unit == "USD" and c.amount is not None:
            known_addons += c.amount
    all_in = round(price_f + known_addons, 2)
    costs_complete = len(material_unknown) == 0 and not premium_unknown

    # Max bid / max price under the 70% acquisition rule
    max_bid_or_price: Optional[float] = None
    if is_auction:
        if premium_pct is None:
            max_bid_or_price = None
        else:
            fixed = (ship or 0.0) + (fees or 0.0)
            # When shipping is unknown we still compute a bid ceiling that
            # assumes $0 shipping, but the decision will be REVIEW/CONDITIONAL.
            if ship is None:
                assumptions.append("Shipping treated as $0 for max-bid math only; decision will not be a hard BUY.")
            multiplier = 1.0 + max(0.0, premium_pct) / 100.0
            max_bid_or_price = round(max(0.0, target_all_in - fixed) / multiplier, 2)
    else:
        # Non-auction: the item price itself must clear the 70% target only
        # after known fixed costs (shipping, other fees/tax) are subtracted,
        # so a BUY verdict reflects all-in cost (item + fees + shipping +
        # tax) rather than just the asking price. Unknown shipping/fees are
        # NA-priced at $0 here (require_shipping=False), matching the
        # pre-existing "unknown non-required cost doesn't block a decision"
        # behavior -- only costs actually supplied on the listing change the
        # threshold.
        fixed = (ship or 0.0) + (fees or 0.0)
        max_bid_or_price = round(target_all_in - fixed, 2)

    # Projected ROI at the *current* price (using known costs only)
    # Use finance.calc_deal with premium; shipping is added into true cost manually when known.
    effective_premium = premium_pct if (is_auction and premium_pct is not None) else 0.0
    # calc_deal applies premium to cost; we need shipping in the cost base.
    cost_for_roi = price_f
    if ship is not None:
        # Fold known shipping into an equivalent pre-premium cost so calc_deal stays consistent,
        # or apply after. Simpler: compute true_cost ourselves.
        pass
    true_cost = price_f * (1 + effective_premium / 100.0) + (ship or 0.0) + (fees or 0.0)
    deal = calc_deal(cost=price_f, resale_value=value_f, fee_pct=resale_fee_pct, premium_pct=effective_premium)
    # Adjust ROI if shipping was known (calc_deal does not include shipping)
    if ship is not None or fees is not None:
        net_resale = value_f * (1 - resale_fee_pct / 100.0)
        true_cost_adj = price_f * (1 + effective_premium / 100.0) + (ship or 0.0) + (fees or 0.0)
        if true_cost_adj > 0:
            roi_pct = (net_resale - true_cost_adj) / true_cost_adj * 100.0
        elif net_resale > 0:
            roi_pct = float("inf")
        else:
            roi_pct = 0.0
        roi_label, roi_tier = five_tier_verdict(roi_pct if math.isfinite(roi_pct) else 999.0)
        projected_roi = None if not math.isfinite(roi_pct) else round(roi_pct, 2)
        projected_profit = round(net_resale - true_cost_adj, 2)
    else:
        roi_label, roi_tier = deal.verdict, deal.verdict_tier
        projected_roi = None if not math.isfinite(deal.roi_pct) else round(deal.roi_pct, 2)
        projected_profit = round(deal.gross_profit, 2)

    # --- Decision logic ---
    if premium_unknown:
        return DealDecision(
            decision=DECISION_REVIEW,
            reason="Auction buyer premium is unknown; CRTC will not claim a safe maximum bid.",
            market_value=value_f,
            confidence=confidence,
            acquisition_target_all_in=target_all_in,
            max_bid_or_price=None,
            all_in_cost=all_in,
            projected_roi_pct=projected_roi,
            projected_profit_usd=projected_profit,
            roi_tier=roi_tier,
            roi_tier_label=roi_label,
            costs_complete=False,
            cost_components=components,
            assumptions=assumptions,
            warnings=warnings,
        )

    if material_unknown:
        # Explicit CONDITIONAL / REVIEW — never treat unknown shipping as $0 for a hard BUY
        missing = ", ".join(c.name for c in material_unknown)
        if max_bid_or_price is not None and price_f <= max_bid_or_price:
            decision = DECISION_CONDITIONAL_BUY
            reason = (
                f"Price is within the {ACQUISITION_TARGET_PCT:.0f}% all-in target IF missing costs "
                f"({missing}) are zero. Confirm those costs before treating this as a BUY."
            )
        else:
            decision = DECISION_REVIEW
            reason = f"Material acquisition cost(s) unknown ({missing}); cannot issue a firm BUY."
        return DealDecision(
            decision=decision,
            reason=reason,
            market_value=value_f,
            confidence=confidence,
            acquisition_target_all_in=target_all_in,
            max_bid_or_price=max_bid_or_price,
            all_in_cost=all_in,
            projected_roi_pct=projected_roi,
            projected_profit_usd=projected_profit,
            roi_tier=roi_tier,
            roi_tier_label=roi_label,
            costs_complete=False,
            cost_components=components,
            assumptions=assumptions + [f"Unknown: {missing}"],
            warnings=warnings,
        )

    # Costs complete — apply 70% acquisition rule
    assert max_bid_or_price is not None
    if price_f <= max_bid_or_price:
        # Acquisition BUY under 70% rule
        acquisition_decision = DECISION_BUY
        reason = f"Current price is within the {ACQUISITION_TARGET_PCT:.0f}% all-in acquisition target."
    elif price_f <= value_f * 0.85:
        acquisition_decision = DECISION_BORDERLINE
        reason = "Price is below market value but above the 70% all-in target."
    else:
        acquisition_decision = DECISION_PASS
        reason = "Price is too high relative to market value after known acquisition costs."

    # --- Item 8: settings-driven minimum dollar profit (default $10), opt-in ---
    if (
        enforce_min_profit
        and acquisition_decision != DECISION_PASS
        and projected_profit is not None
        and projected_profit < settings.min_profit
    ):
        warnings.append(
            f"Projected profit ${projected_profit:.2f} is below the ${settings.min_profit:.2f} "
            "minimum profit threshold; downgraded to PASS."
        )
        acquisition_decision = DECISION_PASS
        reason = (
            f"Projected profit (${projected_profit:.2f}) does not clear the "
            f"${settings.min_profit:.2f} minimum profit threshold."
        )

    # Surface the dual-scale truth: acquisition BUY at the limit is often AT CEILING on ROI scale
    if acquisition_decision == DECISION_BUY and roi_tier in ("at_ceiling", "borderline", "pass"):
        warnings.append(
            f"Acquisition rule says BUY (70% target), but projected ROI ({format_roi(projected_roi or 0)}) "
            f"is below the finance BUY floor ({ROI_BUY_FLOOR_PCT:.0f}%). "
            f"ROI tier: {roi_label}."
        )

    return DealDecision(
        decision=acquisition_decision,
        reason=reason,
        market_value=value_f,
        confidence=confidence,
        acquisition_target_all_in=target_all_in,
        max_bid_or_price=max_bid_or_price,
        all_in_cost=all_in,
        projected_roi_pct=projected_roi,
        projected_profit_usd=projected_profit,
        roi_tier=roi_tier,
        roi_tier_label=roi_label,
        costs_complete=True,
        cost_components=components,
        assumptions=assumptions,
        warnings=warnings,
    )


def evaluate_deal(
    *,
    log_event: bool = False,
    event_log: Optional[EventLog] = None,
    deal_id: Optional[str] = None,
    **kwargs: Any,
) -> DealDecision:
    """Thin wrapper around the decision engine (_evaluate_deal) that adds
    opt-in buy -> outcome event capture (brief item 9).

    log_event: opt-in, off by default like apply_default_auction_fees /
        enforce_min_profit above, so existing callers are unaffected. When
        True, the inputs and resulting verdict (decision, predicted profit,
        predicted ROI) are appended to `event_log` (or the process-wide
        default file-backed log) via EventLog.record_verdict().
    event_log: inject a specific EventLog (e.g. an in-memory one in tests);
        defaults to get_event_log().
    deal_id: optional caller-supplied id (e.g. a listing id) to key the
        event, so a later actual outcome can be attached with the same id
        via EventLog.record_outcome(). Defaults to a random id.

    Returns exactly what _evaluate_deal returns -- logging never changes
    the decision.
    """
    decision = _evaluate_deal(**kwargs)
    if log_event:
        log = event_log or get_event_log()
        log.record_verdict(inputs=dict(kwargs), decision=decision, deal_id=deal_id)
    return decision


def build_deal_workspace_record(
    listing: Dict[str, Any],
    market_value: Optional[float] = None,
    confidence: str = "UNKNOWN",
) -> Dict[str, Any]:
    """Drop-in replacement shape for the old deal_workspace.build_deal_workspace()."""
    source = str(listing.get("source") or "")
    is_auction = (
        source.lower() in {"ctbids / estate auctions", "shopgoodwill", "hibid"}
        or listing.get("buyer_premium") is not None
        or listing.get("buyer_premium_pct") is not None
    )
    premium = listing.get("buyer_premium_pct")
    if premium is None:
        premium = listing.get("buyer_premium")  # legacy key; treated as percentage points

    decision = evaluate_deal(
        price=listing.get("price"),
        market_value=market_value if market_value is not None else listing.get("estimated_value"),
        confidence=confidence,
        is_auction=is_auction,
        buyer_premium_pct=premium,
        shipping=listing.get("shipping"),
        other_fees=listing.get("other_fees"),
        require_shipping=is_auction,
    )
    out = decision.to_dict()
    # Back-compat keys expected by existing UI / tests
    out["max_bid"] = decision.max_bid_or_price
    # Prefer structured cost dict (legacy auction_costs shape) when components exist
    cost_dict = {
        "bid": None,
        "buyer_premium_pct": None,
        "buyer_premium_amount": None,
        "shipping": None,
        "other_fees": None,
        "known_addons": 0.0,
        "all_in_cost": decision.all_in_cost,
        "complete": decision.costs_complete,
    }
    for c in decision.cost_components:
        if c.name == "buyer_premium_pct":
            cost_dict["buyer_premium_pct"] = c.amount
        elif c.name == "buyer_premium":
            cost_dict["buyer_premium_amount"] = c.amount
        elif c.name == "shipping":
            cost_dict["shipping"] = c.amount
        elif c.name == "other_fees":
            cost_dict["other_fees"] = c.amount
    if decision.all_in_cost is not None and listing.get("price") is not None:
        try:
            cost_dict["bid"] = round(float(listing["price"]), 2)
        except (TypeError, ValueError):
            pass
        known = 0.0
        for key in ("buyer_premium_amount", "shipping", "other_fees"):
            if cost_dict[key] is not None:
                known += cost_dict[key]
        cost_dict["known_addons"] = round(known, 2)
    out["all_in"] = cost_dict
    return out
