"""Matretter og tilhørende kataloger (design.md §2)."""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.models.errors import ValidationError


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
    # «Fjernede» retter arkiveres og slettes aldri, så gamle bestillinger kan vise dem (US-03).
    archived: bool = False

    @classmethod
    def from_input(
        cls,
        name,
        description,
        price,
        min_order_qty,
        published=False,
        event_categories=(),
        allergens=(),
        dietary_labels=(),
        id=None,
        image_path=None,
        image_prompt=None,
        origin=None,
        archived=False,
    ):
        """Bygger en rett fra skjemaverdier (tekst). Kaster ValidationError som nevner feltet (US-03)."""
        name = (name or "").strip()
        errors = {}

        if not name:
            errors["name"] = "Navn må fylles ut."

        price_nok = _parse_price(price)
        if price_nok is None:
            errors["price"] = "Pris må være et tall i NOK."
        elif price_nok < 0:
            errors["price"] = "Pris kan ikke være negativ."

        qty = _parse_int(min_order_qty)
        if qty is None:
            errors["min_order_qty"] = "Minimumsantall må være et helt tall."
        elif qty < 1:
            errors["min_order_qty"] = "Minimumsantall må være minst 1."

        if not event_categories:
            errors["event_categories"] = "Velg minst én arrangementskategori."

        if errors:
            raise ValidationError(errors)

        return cls(
            id=id,
            name=name,
            description=(description or "").strip(),
            price_nok=price_nok,
            min_order_qty=qty,
            published=bool(published) and not archived,  # arkiverte retter er aldri publisert
            image_path=image_path,
            image_prompt=image_prompt,
            origin=origin,
            event_categories=list(event_categories),
            allergens=list(allergens),
            dietary_labels=list(dietary_labels),
            archived=archived,
        )


def _parse_price(value):
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    text = str(value if value is not None else "").strip().replace(" ", "").replace(",", ".")
    try:
        price = Decimal(text)
    except InvalidOperation:
        return None
    return price if price.is_finite() else None


def _parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
