"""Marketplace adapter interface: format_listing / publish / delist.

Every adapter converts a :class:`MasterListing` (pure, offline
``format_listing``) and exposes ``publish`` / ``delist``. In this
scaffold ``publish``/``delist`` refuse to run unless the feature flag is
on — and even then each adapter raises a clearly-marked
``NotConfiguredError`` until its real integration is wired. Nothing
goes live from this scaffold.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

from crosslist.config import crosslisting_enabled
from crosslist.models import MasterListing


class CrosslistDisabledError(RuntimeError):
    """Raised when cross-listing runs while the feature flag is OFF."""


class NotConfiguredError(RuntimeError):
    """Raised when an adapter's real integration is not wired yet (TODO)."""


@dataclass
class FormattedListing:
    """Adapter output: a marketplace-ready payload plus review metadata."""

    marketplace_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    # For assisted adapters: the human-facing helpers (deep link etc.).
    assist: Dict[str, Any] = field(default_factory=dict)


class MarketplaceAdapter(ABC):
    """One adapter per marketplace.

    Contract:
      * ``format_listing(master)`` -> FormattedListing — pure, no network.
      * ``publish(formatted)``      -> dict — creates/activates the listing.
      * ``delist(external_id)``     -> dict — removes/deactivates the listing.

    Scaffold defaults: ``publish``/``delist`` raise
    ``CrosslistDisabledError`` when the flag is off and
    ``NotConfiguredError`` when the integration is not wired yet.
    """

    marketplace_id: str = ""

    # -- internal guard --------------------------------------------------
    def _require_enabled(self) -> None:
        if not crosslisting_enabled():
            raise CrosslistDisabledError(
                "Cross-listing is disabled (APPRAZE_CROSSLIST is not set). "
                "Scaffold is 'Coming Soon' — nothing may publish."
            )

    # -- interface -------------------------------------------------------
    @abstractmethod
    def format_listing(self, master: MasterListing) -> FormattedListing:
        """Convert a MasterListing into a marketplace-specific payload."""
        raise NotImplementedError

    def publish(self, formatted: FormattedListing) -> Dict[str, Any]:
        """Publish the listing. Scaffold default: refuse (nothing goes live)."""
        self._require_enabled()
        raise NotConfiguredError(
            f"{self.marketplace_id}: publish() not wired in scaffold. TODO."
        )

    def delist(self, external_id: str) -> Dict[str, Any]:
        """Remove/deactivate a listing. Scaffold default: refuse."""
        self._require_enabled()
        raise NotConfiguredError(
            f"{self.marketplace_id}: delist() not wired in scaffold. TODO."
        )
