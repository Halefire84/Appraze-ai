"""Appraze subscription catalog and feature entitlements.

Pricing is intentionally data-driven so the product can launch with a simple
flagship plan and add higher tiers without scattering price logic through the UI.
Stripe Payment Links remain deployment configuration.

Tier structure updated 2026-09-21 (see COMPETITIVE-GAPS.md for the pricing
research this is based on): the flagship tier was renamed from "Hunter" to
"Appraiser" (ties directly to the product name and reads as professional/
credentialed rather than the "hunting" theme it replaces), and a new
"Analyst" tier was added between Scout and Appraiser to cover the price gap
most competitors also have between their entry and flagship tiers. Round-
dollar pricing ($19/$35/$59/$99/$199, no ".99" endings) is a deliberate
choice -- the ".99" convention every competitor in COMPETITIVE-GAPS.md uses
reads as a discount-bin signal, which cuts against the "this is a premium
program, not a cheap web app" positioning. $59 for the flagship (Appraiser)
sits at Vendoo Pro's exact price and below List Perfectly Pro ($69) and
Nifty AI ($69.99) -- market parity for the entry to "serious tool" tier,
not the cheapest and not the most expensive, matching the deliberate
"don't leave money on the table, don't overcharge before we've proven
ourselves" positioning.
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
    Plan("free", "Free", 0, 5, False, False, False, False, False, False, False, tagline="Try Appraze"),
    Plan("scout", "Scout", 19, 50, True, True, False, False, False, False, False, tagline="For occasional sourcing"),
    Plan("analyst", "Analyst", 35, 120, True, True, True, False, False, False, False, tagline="For sellers ready to scale up"),
    Plan("appraiser", "Appraiser", 59, 250, True, True, True, True, True, True, True, tagline="The Appraze flagship"),
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
