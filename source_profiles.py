"""CRTC source profiles for liquidation, government surplus, and electronics hunting.

Profiles are decision/routing metadata only. Live collection must use an approved
API, public catalog, permitted feed/export, or user-provided listing data.
"""
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class HuntProfile:
    key: str
    name: str
    source_keys: Tuple[str, ...]
    preferred_categories: Tuple[str, ...]
    minimum_cpu_generation: int = 0
    max_risk: float = 1.0
    prefer_local_pickup: bool = False
    notes: str = ""


PROFILES = (
    HuntProfile(
        "modern_computers",
        "Modern Computers & Laptops",
        ("govdeals", "gsa", "publicsurplus", "municibid", "liquidation"),
        ("laptop", "desktop", "workstation", "chromebook", "tablet"),
        minimum_cpu_generation=8,
        max_risk=0.45,
        prefer_local_pickup=True,
        notes="Target Intel 8th gen or newer / equivalent AMD; penalize unknown locks and repair-only lots.",
    ),
    HuntProfile(
        "phones_tablets",
        "Phones & Tablets",
        ("govdeals", "gsa", "publicsurplus", "govplanet", "liquidation"),
        ("iphone", "android", "phone", "tablet", "ipad"),
        max_risk=0.35,
        prefer_local_pickup=True,
        notes="Strong penalties for activation lock, MDM, blacklist, cracked-screen, and unknown-account status.",
    ),
    HuntProfile(
        "amazon_returns",
        "Amazon / Retail Returns",
        ("liquidation",),
        ("consumer electronics", "computers", "phones", "tools", "home goods"),
        max_risk=0.50,
        notes="Require manifest/condition evidence when possible and include freight plus shortage risk.",
    ),
    HuntProfile(
        "government_surplus",
        "Government & Institutional Surplus",
        ("govdeals", "gsa", "publicsurplus", "govplanet", "propertyroom", "municibid"),
        ("computers", "phones", "electronics", "tools", "equipment"),
        max_risk=0.50,
        prefer_local_pickup=True,
        notes="Favor inspection-friendly local lots and transparent descriptions over mystery pallets.",
    ),
)


def get_hunt_profile(key: str) -> HuntProfile:
    for profile in PROFILES:
        if profile.key == key:
            return profile
    raise KeyError(key)


def profile_map() -> Dict[str, HuntProfile]:
    return {profile.key: profile for profile in PROFILES}
