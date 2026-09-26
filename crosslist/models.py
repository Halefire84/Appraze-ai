"""Common listing model shared by all six marketplace adapters.

A :class:`MasterListing` is the single source of truth created once in
Appraze; each adapter converts it into a marketplace-specific payload via
``format_listing()``. Nothing here performs any network or publishing
action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Condition(Enum):
    """Normalized item condition understood by every adapter."""

    NEW = "new"
    LIKE_NEW = "like_new"
    GOOD = "good"
    FAIR = "fair"
    FOR_PARTS = "for_parts"


class ValidationError(ValueError):
    """Raised when a MasterListing fails basic validation."""


@dataclass
class ShippingInfo:
    """How the item ships. ``cost`` is the buyer-facing shipping price."""

    method: str = "USPS Ground Advantage"  # human-readable carrier/service
    cost: float = 0.0  # 0.0 means free shipping
    ships_from_zip: str = ""  # TODO: default from seller profile
    handling_days: int = 1

    def validate(self) -> None:
        if self.cost < 0:
            raise ValidationError("shipping cost cannot be negative")
        if self.handling_days < 0:
            raise ValidationError("handling_days cannot be negative")


@dataclass
class MasterListing:
    """One listing to rule the six marketplaces.

    Fields map 1:1 to the task spec: title, description, price, photos,
    category, condition, shipping.
    """

    title: str
    description: str
    price: float  # USD, buyer-facing asking price
    photos: list = field(default_factory=list)  # URLs or local paths, cover first
    category: str = ""  # Appraze-internal category label
    condition: Condition = Condition.GOOD
    shipping: ShippingInfo = field(default_factory=ShippingInfo)
    # Optional enrichment fields adapters may use when available:
    brand: str = ""
    size: str = ""
    color: str = ""
    sku: str = ""  # internal inventory id, also used as eBay SKU
    quantity: int = 1

    def validate(self) -> None:
        """Validate the model; raises ValidationError on problems."""
        if not self.title or not self.title.strip():
            raise ValidationError("title is required")
        if len(self.title) > 140:
            raise ValidationError("title must be 140 characters or fewer")
        if not self.description or not self.description.strip():
            raise ValidationError("description is required")
        if self.price <= 0:
            raise ValidationError("price must be positive")
        if self.quantity < 1:
            raise ValidationError("quantity must be at least 1")
        if not self.photos:
            raise ValidationError("at least one photo is required")
        self.shipping.validate()

    def to_dict(self) -> dict:
        """Plain-dict view, handy for logging and debugging."""
        return {
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "photos": list(self.photos),
            "category": self.category,
            "condition": self.condition.value,
            "shipping": {
                "method": self.shipping.method,
                "cost": self.shipping.cost,
                "ships_from_zip": self.shipping.ships_from_zip,
                "handling_days": self.shipping.handling_days,
            },
            "brand": self.brand,
            "size": self.size,
            "color": self.color,
            "sku": self.sku,
            "quantity": self.quantity,
        }
