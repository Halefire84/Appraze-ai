"""CRTC Learning Loop: outcome tracking and conservative rule improvement.

This module does not rewrite production scoring automatically. It records
predictions/outcomes and produces measurable recommendations for future rule
changes. The goal is to learn which signals actually correlate with profitable
outcomes for CRTC instead of blindly increasing scores.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

LEARNING_VERSION = "LL-1.0"
DEFAULT_STORE = Path("data/crtc_learning.jsonl")


@dataclass
class OpportunityOutcome:
    listing_id: str
    source: str
    title: str
    predicted_score: float
    predicted_value: Optional[float] = None
    max_buy: Optional[float] = None
    decision: str = "UNDECIDED"  # BUY / PASS / WATCH
    acquisition_cost: Optional[float] = None
    resale_price: Optional[float] = None
    net_profit: Optional[float] = None
    sold: Optional[bool] = None
    signal_codes: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""

    def realized_profit(self) -> Optional[float]:
        if self.net_profit is not None:
            return float(self.net_profit)
        if self.resale_price is None or self.acquisition_cost is None:
            return None
        return float(self.resale_price - self.acquisition_cost)


def append_outcome(outcome: OpportunityOutcome, path: Path = DEFAULT_STORE) -> None:
    """Append one immutable outcome record. Creates the directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(outcome), sort_keys=True) + "\n")


def load_outcomes(path: Path = DEFAULT_STORE) -> List[OpportunityOutcome]:
    if not path.exists():
        return []
    rows: List[OpportunityOutcome] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(OpportunityOutcome(**json.loads(line)))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return rows


def signal_performance(outcomes: Iterable[OpportunityOutcome]) -> Dict[str, Dict[str, float]]:
    """Return transparent per-signal performance metrics.

    A signal is considered successful when the associated opportunity has a
    positive realized profit. This is intentionally simple and auditable.
    """
    buckets: Dict[str, Dict[str, float]] = {}
    for outcome in outcomes:
        profit = outcome.realized_profit()
        if profit is None:
            continue
        success = 1.0 if profit > 0 else 0.0
        for code in set(outcome.signal_codes):
            bucket = buckets.setdefault(code, {"observations": 0.0, "wins": 0.0, "win_rate": 0.0, "profit": 0.0})
            bucket["observations"] += 1
            bucket["wins"] += success
            bucket["profit"] += profit
    for bucket in buckets.values():
        bucket["win_rate"] = bucket["wins"] / bucket["observations"] if bucket["observations"] else 0.0
    return buckets


def learning_report(outcomes: Iterable[OpportunityOutcome]) -> Dict[str, object]:
    rows = list(outcomes)
    completed = [row for row in rows if row.realized_profit() is not None]
    profits = [row.realized_profit() for row in completed]
    positive = [profit for profit in profits if profit is not None and profit > 0]
    return {
        "version": LEARNING_VERSION,
        "total_records": len(rows),
        "completed_records": len(completed),
        "positive_outcomes": len(positive),
        "win_rate": (len(positive) / len(completed)) if completed else 0.0,
        "realized_profit": sum(profit for profit in profits if profit is not None),
        "signal_performance": signal_performance(completed),
    }
