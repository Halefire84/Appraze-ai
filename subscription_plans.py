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
    Plan("free", "Free", 0, 5, False, False, False, False, False, False, False, tagline="Taste the deal math"),
    Plan("starter", "Starter", 25, 50, True, True, False, False, False, False, False, tagline="For occasional sourcing"),
    Plan("pro", "Pro", 50, 250, True, True, True, True, False, True, True, tagline="The flagship. For working resellers"),
    Plan("business", "Business", 100, 1000, True, True, True, True, True, True, True, team_seats=3, tagline="For serious volume and teams"),
    Plan("enterprise", "Enterprise", 200, 5000, True, True, True, True, True, True, True, team_seats=10, tagline="For full-time operations"),
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
