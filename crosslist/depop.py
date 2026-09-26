"""Depop adapter — STUB ONLY, awaiting partner-API approval.

Depop does not offer a public self-serve seller API suitable for this
use case. This adapter is a deliberate stub: it validates the master
listing, then refuses every operation with a clear
``DepopNotAvailableError`` until a partner-API agreement is in place.

Do NOT attempt to automate Depop's private/mobile endpoints — that is
forbidden by this project's hard rules (no reverse-engineered private
APIs, ever).
"""

from __future__ import annotations

from typing import Any, Dict

from crosslist.base import (
    FormattedListing,
    MarketplaceAdapter,
    NotConfiguredError,
)
from crosslist.models import MasterListing


class DepopNotAvailableError(NotConfiguredError):
    """Depop integration is blocked pending partner-API approval."""


class DepopStubAdapter(MarketplaceAdapter):
    """Placeholder adapter for Depop. All operations refuse."""

    marketplace_id = "depop"

    def _unavailable(self) -> DepopNotAvailableError:
        return DepopNotAvailableError(
            "Depop adapter is a stub: awaiting partner-API approval. "
            "No payload can be generated and nothing may publish. "
            "TODO: apply for Depop partner access, then implement the "
            "official partner endpoints here. Private/mobile endpoints "
            "must never be used."
        )

    def format_listing(self, master: MasterListing) -> FormattedListing:
        master.validate()
        raise self._unavailable()

    def publish(self, formatted: FormattedListing) -> Dict[str, Any]:
        self._require_enabled()
        raise self._unavailable()

    def delist(self, external_id: str) -> Dict[str, Any]:
        self._require_enabled()
        raise self._unavailable()
