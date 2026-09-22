"""CRTC financial intelligence layer.

Provider-neutral foundation for Plaid, Venmo/PayPal, and future payment/bank
connectors. Secrets and provider-specific authentication belong in the backend
or Streamlit secrets, never in client-side code.
"""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional


@dataclass(frozen=True)
class CashPosition:
    available_cash: float
    reserved_cash: float = 0.0
    inventory_capital: float = 0.0
    upcoming_obligations: float = 0.0

    @property
    def deployable_cash(self) -> float:
        return max(0.0, self.available_cash - self.reserved_cash - self.upcoming_obligations)


def summarize_transactions(transactions: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    """Summarize normalized bank/payment transactions supplied by an adapter."""
    inflow = 0.0
    outflow = 0.0
    for tx in transactions:
        amount = float(tx.get("amount", 0) or 0)
        if amount < 0:
            inflow += abs(amount)
        else:
            outflow += amount
    return {
        "inflow": round(inflow, 2),
        "outflow": round(outflow, 2),
        "net_cash_flow": round(inflow - outflow, 2),
    }


def safe_opportunity_budget(
    cash: CashPosition,
    *,
    requested_bid: Optional[float] = None,
    safety_buffer: float = 0.20,
) -> Dict[str, Any]:
    """Decide whether an acquisition fits within a conservative cash budget."""
    deployable = cash.deployable_cash
    budget = max(0.0, deployable * (1.0 - max(0.0, min(0.8, safety_buffer))))
    result: Dict[str, Any] = {
        "deployable_cash": round(deployable, 2),
        "safe_buying_budget": round(budget, 2),
        "decision": "BUY_WITHIN_BUDGET",
    }
    if requested_bid is not None:
        bid = max(0.0, float(requested_bid))
        result["requested_bid"] = round(bid, 2)
        if bid > budget:
            result["decision"] = "PRESERVE_CASH"
        elif bid > deployable:
            result["decision"] = "PASS"
    return result
