"""CRTC canonical flip lifecycle and profit math.

Pure logic only. A flip moves LEAD -> PURCHASED -> LISTED -> SOLD (or PASSED).
Realized profit uses the fully settled acquisition cost and actual sale economics.
"""
from typing import Any, Dict

STATUSES = ("LEAD", "PURCHASED", "LISTED", "SOLD", "PASSED")
ALLOWED_TRANSITIONS = {
    "LEAD": {"PURCHASED", "PASSED"},
    "PURCHASED": {"LISTED", "PASSED"},
    "LISTED": {"SOLD", "PASSED"},
    "SOLD": set(),
    "PASSED": set(),
}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_flip_profit(cost_basis: float, sale_price: float, *, fee_pct: float = 13.0, shipping_out: float = 0.0, shipping_charged: float = 0.0) -> Dict[str, float]:
    """Return actual net proceeds, profit, margin and ROI for a completed sale.

    fee is charged on (sale price + buyer-paid shipping), not sale price
    alone -- eBay's published fee schedule explicitly includes "item
    price, handling, buyer-paid shipping, sales tax, and other applicable
    amounts" in its percentage-fee basis (see DEAL-MATH.md), and Mercari's
    10% is likewise charged on "item price plus any buyer-paid shipping".
    Charging the fee on sale price alone understates it whenever
    shipping_charged > 0, overstating realized profit."""
    cost = max(0.0, _num(cost_basis))
    sale = max(0.0, _num(sale_price))
    outbound = max(0.0, _num(shipping_out))
    buyer_shipping = max(0.0, _num(shipping_charged))
    fee = (sale + buyer_shipping) * max(0.0, _num(fee_pct)) / 100.0
    net_proceeds = sale + buyer_shipping - fee - outbound
    profit = net_proceeds - cost
    margin_pct = (profit / sale * 100.0) if sale else 0.0
    roi_pct = (profit / cost * 100.0) if cost else (float("inf") if profit > 0 else 0.0)
    if roi_pct != float("inf"):
        roi_pct = round(roi_pct, 2)  # every other field here is rounded; this one wasn't
    return {"sale_price": round(sale, 2), "platform_fee": round(fee, 2), "shipping_out": round(outbound, 2), "shipping_charged": round(buyer_shipping, 2), "net_proceeds": round(net_proceeds, 2), "profit": round(profit, 2), "margin_pct": round(margin_pct, 2), "roi_pct": roi_pct}


def build_flip_record(intake: Dict[str, Any], *, status: str = "PURCHASED") -> Dict[str, Any]:
    """Convert inventory intake into one canonical flip record.

    image_urls is a list of already-hosted photo URLs -- this app has no
    upload/hosting mechanism of its own (no S3/Cloudinary/etc. wired up),
    so a seller pastes in URLs of photos hosted elsewhere. Carried through
    unchanged to listing_bridge.build_master_listing() -> the eBay publish
    payload; see that module's docstring for why this field's name must
    stay "image_urls" everywhere in this app's own data model."""
    status = str(status).upper()
    if status not in STATUSES:
        raise ValueError(f"Unsupported flip status: {status}")
    return {"item_name": str(intake.get("item_name") or "Untitled item"), "source": str(intake.get("source") or ""), "source_listing_id": str(intake.get("source_listing_id") or ""), "source_url": str(intake.get("source_url") or ""), "cost_basis": round(max(0.0, _num(intake.get("cost_basis"))), 2), "market_value": intake.get("market_value"), "radar_score": intake.get("radar_score"), "status": status, "list_price": 0.0, "sale_price": 0.0, "platform_fee_pct": 13.0, "shipping_out": 0.0, "shipping_charged": 0.0, "notes": str(intake.get("notes") or ""), "image_urls": list(intake.get("image_urls") or [])}


def update_flip(record: Dict[str, Any], **changes: Any) -> Dict[str, Any]:
    """Return a validated updated flip record without mutating the input."""
    updated = dict(record)
    current = str(record.get("status", "PURCHASED")).upper()
    updated.update(changes)
    status = str(updated.get("status", current)).upper()
    if status not in STATUSES:
        raise ValueError(f"Unsupported flip status: {status}")
    if status != current and status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid flip transition: {current} -> {status}")
    updated["status"] = status
    for field in ("cost_basis", "list_price", "sale_price", "platform_fee_pct", "shipping_out", "shipping_charged"):
        updated[field] = round(max(0.0, _num(updated.get(field))), 2)
    if status == "SOLD":
        if updated["sale_price"] <= 0:
            raise ValueError("A SOLD flip requires a positive sale price")
        updated.update(calculate_flip_profit(updated["cost_basis"], updated["sale_price"], fee_pct=updated["platform_fee_pct"], shipping_out=updated["shipping_out"], shipping_charged=updated["shipping_charged"]))
    return updated
