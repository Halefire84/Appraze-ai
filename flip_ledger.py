"""CRTC canonical flip lifecycle and profit math.

Pure logic only. A flip moves LEAD -> PURCHASED -> LISTED -> SOLD (or PASSED).
Realized profit uses the fully settled acquisition cost and actual sale economics.
"""
from typing import Any, Dict

STATUSES = ("LEAD", "PURCHASED", "LISTED", "SOLD", "PASSED")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_flip_profit(
    cost_basis: float,
    sale_price: float,
    *,
    fee_pct: float = 13.0,
    shipping_out: float = 0.0,
    shipping_charged: float = 0.0,
) -> Dict[str, float]:
    """Return actual net proceeds, profit, margin and ROI for a completed sale."""
    cost = max(0.0, _num(cost_basis))
    sale = max(0.0, _num(sale_price))
    fee = sale * max(0.0, _num(fee_pct)) / 100.0
    outbound = max(0.0, _num(shipping_out))
    buyer_shipping = max(0.0, _num(shipping_charged))
    net_proceeds = sale + buyer_shipping - fee - outbound
    profit = net_proceeds - cost
    margin_pct = (profit / sale * 100.0) if sale else 0.0
    roi_pct = (profit / cost * 100.0) if cost else (float("inf") if profit > 0 else 0.0)
    return {
        "sale_price": round(sale, 2),
        "platform_fee": round(fee, 2),
        "shipping_out": round(outbound, 2),
        "shipping_charged": round(buyer_shipping, 2),
        "net_proceeds": round(net_proceeds, 2),
        "profit": round(profit, 2),
        "margin_pct": round(margin_pct, 2),
        "roi_pct": roi_pct,
    }


def build_flip_record(intake: Dict[str, Any], *, status: str = "PURCHASED") -> Dict[str, Any]:
    """Convert inventory intake into one canonical flip record."""
    status = str(status).upper()
    if status not in STATUSES:
        raise ValueError(f"Unsupported flip status: {status}")
    return {
        "item_name": str(intake.get("item_name") or "Untitled item"),
        "source": str(intake.get("source") or ""),
        "source_listing_id": str(intake.get("source_listing_id") or ""),
        "source_url": str(intake.get("source_url") or ""),
        "cost_basis": round(max(0.0, _num(intake.get("cost_basis"))), 2),
        "market_value": intake.get("market_value"),
        "radar_score": intake.get("radar_score"),
        "status": status,
        "list_price": 0.0,
        "sale_price": 0.0,
        "platform_fee_pct": 13.0,
        "shipping_out": 0.0,
        "shipping_charged": 0.0,
        "notes": str(intake.get("notes") or ""),
    }


def update_flip(record: Dict[str, Any], **changes: Any) -> Dict[str, Any]:
    """Return a validated updated flip record without mutating the input."""
    updated = dict(record)
    updated.update(changes)
    status = str(updated.get("status", "PURCHASED")).upper()
    if status not in STATUSES:
        raise ValueError(f"Unsupported flip status: {status}")
    updated["status"] = status
    for field in ("cost_basis", "list_price", "sale_price", "platform_fee_pct", "shipping_out", "shipping_charged"):
        updated[field] = round(max(0.0, _num(updated.get(field))), 2)
    if status == "SOLD":
        updated.update(calculate_flip_profit(
            updated["cost_basis"], updated["sale_price"],
            fee_pct=updated["platform_fee_pct"],
            shipping_out=updated["shipping_out"],
            shipping_charged=updated["shipping_charged"],
        ))
    return updated
