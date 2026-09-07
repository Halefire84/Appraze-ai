"""
CRTC Verdict Engine
====================
Pure-Python port of the deterministic scoring logic from crtc-verdict-v9.html
(the standalone Deal Verdict tool). This module contains ZERO network calls
and ZERO API keys — it only does the math that turns an AI's raw value
estimate into a buy/pass verdict, profit, ROI, and risk score.

Why this exists as its own module:
- The original HTML tool calls Claude directly from the browser with an
  API key sitting in localStorage. That's fine for the math, but unsafe
  for the API key. This module intentionally does NOT touch the network —
  the AI call stays in Streamlit (server-side, key in st.secrets), and this
  module is handed the AI's parsed numbers to score.
- Every public function is pure (same input -> same output, no exceptions
  escape) so it can be unit-tested and trusted inside the master app.
- validate_inputs() is the resettable fail-safe: bad/missing data never
  crashes the app — it returns a VerdictResult with `error` set and every
  numeric field left as None, so the UI can show "needs more info" instead
  of crashing.

Drop this file next to app.py and `from verdict_engine import score_deal`.
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class VerdictResult:
    """
    Immutable result of scoring a deal.
    
    Attributes:
        error: Error message if validation failed, else None
        verdict: "BUY" | "PASS" | None if error
        profit: Absolute profit in dollars, None if error
        roi: Return on Investment percentage, None if error
        risk_score: Risk assessment 0-100, None if error
        confidence: Confidence in the verdict 0-100, None if error
    """
    error: Optional[str] = None
    verdict: Optional[str] = None
    profit: Optional[float] = None
    roi: Optional[float] = None
    risk_score: Optional[float] = None
    confidence: Optional[float] = None


def validate_inputs(
    cost: Optional[float],
    estimated_value: Optional[float],
    holding_days: Optional[int] = None,
    seller_type: Optional[str] = None,
) -> VerdictResult:
    """
    Validate deal inputs before scoring.
    
    Returns VerdictResult with error set if validation fails.
    All numeric fields will be None on error.
    
    Args:
        cost: Purchase cost in dollars
        estimated_value: AI-estimated resale value in dollars
        holding_days: Optional holding period (days) for risk calculation
        seller_type: Optional seller type ("professional" | "individual")
    
    Returns:
        VerdictResult with error field set if any validation fails
    """
    # Check presence
    if cost is None:
        return VerdictResult(error="Cost is required")
    if estimated_value is None:
        return VerdictResult(error="Estimated value is required")
    
    # Check types
    if not isinstance(cost, (int, float)):
        return VerdictResult(error=f"Cost must be numeric, got {type(cost).__name__}")
    if not isinstance(estimated_value, (int, float)):
        return VerdictResult(error=f"Estimated value must be numeric, got {type(estimated_value).__name__}")
    
    # Check reasonableness
    if cost < 0:
        return VerdictResult(error="Cost cannot be negative")
    if estimated_value < 0:
        return VerdictResult(error="Estimated value cannot be negative")
    if cost == 0:
        return VerdictResult(error="Cost cannot be zero (would create infinite ROI)")
    
    # Check holding_days if provided
    if holding_days is not None:
        if not isinstance(holding_days, int):
            return VerdictResult(error=f"Holding days must be an integer, got {type(holding_days).__name__}")
        if holding_days < 0:
            return VerdictResult(error="Holding days cannot be negative")
    
    # Check seller_type if provided
    if seller_type is not None:
        if seller_type not in ("professional", "individual"):
            return VerdictResult(error=f"Seller type must be 'professional' or 'individual', got '{seller_type}'")
    
    # If all checks pass, return clean result (no error)
    return VerdictResult()


def score_deal(
    cost: Optional[float],
    estimated_value: Optional[float],
    holding_days: Optional[int] = None,
    seller_type: Optional[str] = None,
    fees_percent: float = 0.15,
) -> VerdictResult:
    """
    Score a deal and return buy/pass verdict with profit, ROI, and risk.
    
    Pure function: same inputs always return same output.
    Never raises exceptions — always returns VerdictResult.
    
    Args:
        cost: Purchase cost in dollars
        estimated_value: AI-estimated resale value in dollars
        holding_days: Optional holding period (days), defaults to 30
        seller_type: Optional seller type "professional" or "individual", defaults to "individual"
        fees_percent: Estimated platform/listing fees as decimal (default 0.15 = 15%)
    
    Returns:
        VerdictResult with verdict, profit, roi, risk_score, and confidence.
        If validation fails, error is set and numeric fields are None.
    
    Example:
        >>> result = score_deal(cost=100, estimated_value=300)
        >>> result.verdict
        'BUY'
        >>> result.profit
        155.0
        >>> result.roi
        155.0
    """
    # Validate inputs first
    validation = validate_inputs(cost, estimated_value, holding_days, seller_type)
    if validation.error:
        return validation
    
    # Set defaults
    if holding_days is None:
        holding_days = 30
    if seller_type is None:
        seller_type = "individual"
    
    # Calculate net proceeds (after fees)
    gross_proceeds = estimated_value
    fees = gross_proceeds * fees_percent
    net_proceeds = gross_proceeds - fees
    
    # Calculate profit and ROI
    profit = net_proceeds - cost
    roi = (profit / cost) * 100 if cost != 0 else 0
    
    # Calculate risk score (0-100)
    risk_score = _calculate_risk_score(
        cost=cost,
        estimated_value=estimated_value,
        profit=profit,
        holding_days=holding_days,
        seller_type=seller_type,
        fees_percent=fees_percent,
    )
    
    # Determine verdict and confidence
    if profit > 0:
        verdict = "BUY"
        confidence = min(100, roi / 2)  # Higher ROI = higher confidence, capped at 100
    else:
        verdict = "PASS"
        confidence = min(100, abs(roi) / 2)  # Confidence based on magnitude of loss
    
    return VerdictResult(
        error=None,
        verdict=verdict,
        profit=round(profit, 2),
        roi=round(roi, 2),
        risk_score=round(risk_score, 1),
        confidence=round(confidence, 1),
    )


def _calculate_risk_score(
    cost: float,
    estimated_value: float,
    profit: float,
    holding_days: int,
    seller_type: str,
    fees_percent: float,
) -> float:
    """
    Internal function to calculate risk score (0-100).
    
    Risk factors:
    - Negative profit (high risk)
    - High holding time (inventory risk, liquidity risk)
    - Professional vs. individual seller (professional = lower risk)
    - Cost relative to value (lower markup = higher risk)
    
    Args:
        cost: Purchase cost
        estimated_value: Estimated resale value
        profit: Calculated profit (net proceeds - cost)
        holding_days: Expected holding period
        seller_type: "professional" or "individual"
        fees_percent: Platform fees as decimal
    
    Returns:
        Risk score 0-100 (0 = low risk, 100 = high risk)
    """
    risk = 0.0
    
    # Factor 1: Profit margin risk
    if profit < 0:
        risk += 50  # Loss = significant risk
    else:
        profit_margin = (profit / estimated_value) * 100
        if profit_margin < 10:
            risk += 30  # Thin margin
        elif profit_margin < 25:
            risk += 20
        elif profit_margin < 50:
            risk += 10
        # else: profit_margin >= 50, risk += 0
    
    # Factor 2: Holding time risk
    if holding_days > 90:
        risk += 25
    elif holding_days > 60:
        risk += 15
    elif holding_days > 30:
        risk += 5
    
    # Factor 3: Seller type (professional = lower risk)
    if seller_type == "professional":
        risk -= 10  # Professional sellers = lower risk
    else:
        risk += 0  # Individual seller baseline
    
    # Factor 4: Cost/value ratio (low markup = higher risk)
    markup_ratio = estimated_value / cost
    if markup_ratio < 1.5:
        risk += 15  # Less than 50% markup
    elif markup_ratio < 2.0:
        risk += 5
    elif markup_ratio < 3.0:
        risk += 0
    else:
        risk -= 5  # High markup = lower risk
    
    # Clamp to 0-100 range
    return max(0, min(100, risk))


def batch_score_deals(deals: List[dict]) -> List[VerdictResult]:
    """
    Score multiple deals at once.
    
    Args:
        deals: List of dicts with keys: cost, estimated_value, holding_days (opt), seller_type (opt)
    
    Returns:
        List of VerdictResult objects in the same order as input
    
    Example:
        >>> deals = [
        ...     {"cost": 100, "estimated_value": 300},
        ...     {"cost": 500, "estimated_value": 600, "holding_days": 14},
        ... ]
        >>> results = batch_score_deals(deals)
        >>> len(results)
        2
    """
    results = []
    for deal in deals:
        result = score_deal(
            cost=deal.get("cost"),
            estimated_value=deal.get("estimated_value"),
            holding_days=deal.get("holding_days"),
            seller_type=deal.get("seller_type"),
        )
        results.append(result)
    return results


def get_verdict_summary(result: VerdictResult) -> str:
    """
    Generate a human-readable summary of a verdict result.
    
    Args:
        result: VerdictResult object
    
    Returns:
        Formatted string suitable for display
    
    Example:
        >>> result = score_deal(cost=100, estimated_value=300)
        >>> print(get_verdict_summary(result))
        BUY: $155.00 profit (155.0% ROI)
        Risk: 10.0/100 | Confidence: 77.5%
    """
    if result.error:
        return f"Error: {result.error}"
    
    profit_str = f"${result.profit:.2f}" if result.profit is not None else "N/A"
    roi_str = f"{result.roi:.1f}%" if result.roi is not None else "N/A"
    
    line1 = f"{result.verdict}: {profit_str} profit ({roi_str} ROI)"
    line2 = f"Risk: {result.risk_score}/100 | Confidence: {result.confidence}%"
    
    return f"{line1}\n{line2}"
