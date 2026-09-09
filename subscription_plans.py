"""CRTC subscription catalog and feature entitlements.

Pricing is intentionally data-driven so the product can launch with a simple
flagship plan and add higher tiers without scattering price logic through the UI.
Stripe Payment Links remain deployment configuration.
"""
from dataclasses import dataclass
from typing import FrozenSet, Tuple


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    monthly_price: int
    analyses_per_month: int
    hunt_enabled: bool
    alerts_enabled: bool
    advanced_sources: bool
    liquidation: bool
    financial_intelligence: bool
    batch_analysis: bool
    priority: bool
    team_seats: int = 1
    tagline: str = ""


PLANS: Tuple[Plan, ...] = (
    Plan("free", "Free", 0, 5, False, False, False, False, False, False, False, tagline="Try CRTC"),
    Plan("scout", "Scout", 19, 50, True, True, False, False, False, False, False, tagline="For occasional sourcing"),
    Plan("hunter", "Hunter", 49, 250, True, True, True, True, True, True, True, tagline="The CRTC flagship"),
    Plan("operator", "Operator", 99, 1000, True, True, True, True, True, True, True, tagline="For serious resellers"),
    Plan("pro", "Pro", 199, 5000, True, True, True, True, True, True, True, team_seats=5, tagline="For teams and high volume"),
)

FEATURE_LABELS: FrozenSet[str] = frozenset({
    "holy_grail_hunt", "alerts", "advanced_sources", "liquidation", "financial_intelligence", "batch_analysis", "priority", "team",
})


def get_plan(key: str) -> Plan:
    for plan in PLANS:
        if plan.key == key:
            return plan
    return PLANS[0]


def feature_enabled(plan_key: str, feature: str) -> bool:
    plan = get_plan(plan_key)
    mapping = {
        "holy_grail_hunt": plan.hunt_enabled,
        "alerts": plan.alerts_enabled,
        "advanced_sources": plan.advanced_sources,
        "liquidation": plan.liquidation,
        "financial_intelligence": plan.financial_intelligence,
        "batch_analysis": plan.batch_analysis,
        "priority": plan.priority,
        "team": plan.team_seats > 1,
    }
    return bool(mapping.get(feature, False))
