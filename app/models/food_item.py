"""Matretter og tilhørende kataloger (design.md §2)."""
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class EventCategory:
    id: int | None
    name: str


@dataclass
class Allergen:
    code: str
    name: str


@dataclass
class DietaryLabel:
    code: str
    name: str


@dataclass
class FoodItem:
    id: int | None
    name: str
    description: str
    price_nok: Decimal
    min_order_qty: int
    published: bool = False
    image_path: str | None = None
    image_prompt: str | None = None
    origin: str | None = None
    event_categories: list[EventCategory] = field(default_factory=list)
    allergens: list[Allergen] = field(default_factory=list)
    dietary_labels: list[DietaryLabel] = field(default_factory=list)
