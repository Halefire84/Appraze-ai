"""Provider-neutral payment adapter contracts for CRTC.

No credentials are embedded here. A future Venmo/PayPal connector can map
provider webhooks/API events into these normalized records.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PaymentEvent:
    provider: str
    transaction_id: str
    amount: float
    status: str
    payer: str = ""
    reference: str = ""
    fee: float = 0.0
    currency: str = "USD"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "transaction_id": self.transaction_id,
            "amount": round(float(self.amount), 2),
            "status": self.status,
            "payer": self.payer,
            "reference": self.reference,
            "fee": round(float(self.fee), 2),
            "currency": self.currency,
        }


def normalize_payment(payload: Dict[str, Any], provider: str) -> PaymentEvent:
    """Normalize a provider webhook/export payload without assuming its schema."""
    return PaymentEvent(
        provider=provider,
        transaction_id=str(payload.get("transaction_id") or payload.get("id") or ""),
        amount=float(payload.get("amount") or 0),
        status=str(payload.get("status") or "unknown"),
        payer=str(payload.get("payer") or payload.get("sender") or ""),
        reference=str(payload.get("reference") or payload.get("memo") or ""),
        fee=float(payload.get("fee") or 0),
        currency=str(payload.get("currency") or "USD"),
    )


def payment_net(event: PaymentEvent) -> float:
    return round(event.amount - event.fee, 2)
