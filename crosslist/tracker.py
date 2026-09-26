"""Delist tracker stub — records where each item was listed.

In-memory stub (no persistence yet). The assisted flow depends on the
human to publish; the tracker records what the human reports so listings
can be taken down consistently later. A future version can persist this
(e.g. SQLite) and wire official delist endpoints where they exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass
class ListingRecord:
    """One record of an item's presence on one marketplace."""

    item_id: str
    marketplace_id: str
    status: str = "assisted_pending"  # assisted_pending | live | delisted
    external_id: Optional[str] = None
    created_at: str = ""
    notes: str = ""


class DelistTracker:
    """In-memory record of where each item was listed. Stub: no persistence."""

    def __init__(self) -> None:
        self._records: Dict[str, ListingRecord] = {}

    @staticmethod
    def _key(item_id: str, marketplace_id: str) -> str:
        return f"{item_id}::{marketplace_id}"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _get_or_raise(self, item_id: str, marketplace_id: str) -> ListingRecord:
        key = self._key(item_id, marketplace_id)
        if key not in self._records:
            raise KeyError(f"no listing record for {item_id!r} on {marketplace_id!r}")
        return self._records[key]

    def record(
        self, item_id: str, marketplace_id: str, *, notes: str = ""
    ) -> ListingRecord:
        """Record that a listing flow started for this item/marketplace."""
        rec = ListingRecord(
            item_id=item_id,
            marketplace_id=marketplace_id,
            created_at=self._now(),
            notes=notes,
        )
        self._records[self._key(item_id, marketplace_id)] = rec
        return rec

    def mark_live(
        self, item_id: str, marketplace_id: str, *, external_id: str = ""
    ) -> ListingRecord:
        """The human (or API) reports the listing is live; store its id."""
        rec = self._get_or_raise(item_id, marketplace_id)
        rec.status = "live"
        rec.external_id = external_id or None
        return rec

    def mark_delisted(self, item_id: str, marketplace_id: str) -> ListingRecord:
        """The human (or API) reports the listing was taken down."""
        rec = self._get_or_raise(item_id, marketplace_id)
        rec.status = "delisted"
        return rec

    def get(self, item_id: str, marketplace_id: str) -> Optional[ListingRecord]:
        return self._records.get(self._key(item_id, marketplace_id))

    def for_item(self, item_id: str) -> List[ListingRecord]:
        return [r for r in self._records.values() if r.item_id == item_id]

    def all(self) -> List[ListingRecord]:
        return list(self._records.values())
