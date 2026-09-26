"""Appraze subscription catalog and feature entitlements.

Pricing is intentionally data-driven so the product can launch with a simple
flagship plan and add higher tiers without scattering price logic through the UI.

Tier structure replaced 2026-09-22 -- the old five (Free $0, Scout $19,
Analyst $35, Appraiser $59, Operator $99, Pro $199) are retired; no plan
key or display name from that lineup should appear anywhere in the app.
New lineup, all round dollar amounts, no ".99" endings:

  Free $0 / Starter $25 / Pro $50 / Business $100 / Enterprise $200

Each tier's monthly analysis cap doubles-then-some going up the ladder
(5/50/250/1,000/5,000), and every tier keeps everything the one below it
has plus its own additions -- see PLANS below for the exact feature line.

Prepay (3-month / 6-month) is a separate, explicit total dollar amount
per tier, not a formula -- these are the exact numbers requested, roughly
30% off the monthly-equivalent total, in round numbers:

  Starter:    3mo $50  (vs $75)   / 6mo $100 (vs $150)
  Pro:        3mo $100 (vs $150)  / 6mo $200 (vs $300)
  Business:   3mo $200 (vs $300)  / 6mo $400 (vs $600)
  Enterprise: 3mo $400 (vs $600)  / 6mo $800 (vs $1,200)

Free has no prepay option (prepay_3mo/prepay_6mo are None).

Payments are manual for now (Cash App + emailed receipt, activated by
hand -- see pages/8_Pricing.py) -- deliberately no Stripe Payment Link
wiring on this catalog or the Pricing page. Google Play Billing is
planned for the Android launch, not built yet. "Email verification
required" on the Free tier is a stated policy, not an enforced
mechanic -- this repo's signup flow does not currently send or check a
verification email; nothing new was wired up here per this change's
own scope (pricing catalog + Pricing page only).
"""
from dataclasses import dataclass
from typing import FrozenSet, Optional, Tuple


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    monthly_price: int
    analyses_per_month: int
    hunt_enabled: bool
    alerts_enabled: bool
    inventory_tracking: bool
    advanced_sources: bool
    liquidation: bool
    batch_analysis: bool
    priority: bool
    financial_intelligence: bool
    team_seats: int = 1
    tagline: str = ""
    prepay_3mo: Optional[int] = None
    prepay_6mo: Optional[int] = None


PLANS: Tuple[Plan, ...] = (
    Plan(
        "free", "Free", 0, 5,
        hunt_enabled=False, alerts_enabled=False, inventory_tracking=False,
        advanced_sources=False, liquidation=False, batch_analysis=False,
        priority=False, financial_intelligence=False,
        tagline="Try Appraze -- email verification required",
    ),
    Plan(
        "starter", "Starter", 25, 50,
        hunt_enabled=True, alerts_enabled=True, inventory_tracking=True,
        advanced_sources=False, liquidation=False, batch_analysis=False,
        priority=False, financial_intelligence=False,
        tagline="For occasional sourcing",
        prepay_3mo=50, prepay_6mo=100,
    ),
    Plan(
        "pro", "Pro", 50, 250,
        hunt_enabled=True, alerts_enabled=True, inventory_tracking=True,
        advanced_sources=True, liquidation=True, batch_analysis=True,
        priority=True, financial_intelligence=False,
        tagline="For sellers ready to scale up",
        prepay_3mo=100, prepay_6mo=200,
    ),
    Plan(
        "business", "Business", 100, 1000,
        hunt_enabled=True, alerts_enabled=True, inventory_tracking=True,
        advanced_sources=True, liquidation=True, batch_analysis=True,
        priority=True, financial_intelligence=True,
        team_seats=3,
        tagline="For small teams",
        prepay_3mo=200, prepay_6mo=400,
    ),
    Plan(
        "enterprise", "Enterprise", 200, 5000,
        hunt_enabled=True, alerts_enabled=True, inventory_tracking=True,
        advanced_sources=True, liquidation=True, batch_analysis=True,
        priority=True, financial_intelligence=True,
        team_seats=10,
        tagline="For high-volume operations",
        prepay_3mo=400, prepay_6mo=800,
    ),
)

FEATURE_LABELS: FrozenSet[str] = frozenset({
    "holy_grail_hunt", "alerts", "inventory_tracking", "advanced_sources",
    "liquidation", "financial_intelligence", "batch_analysis", "priority", "team",
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
        "inventory_tracking": plan.inventory_tracking,
        "advanced_sources": plan.advanced_sources,
        "liquidation": plan.liquidation,
        "financial_intelligence": plan.financial_intelligence,
        "batch_analysis": plan.batch_analysis,
        "priority": plan.priority,
        "team": plan.team_seats > 1,
    }
    return bool(mapping.get(feature, False))
