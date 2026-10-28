"""Handlekurv (design.md §2). Lagres ikke i databasen, bare som {id: antall} i sessionen."""
from dataclasses import dataclass
from decimal import Decimal

from app.models.errors import ValidationError
from app.models.food_item import FoodItem


@dataclass
class CartLine:
    food_item: FoodItem
    quantity: int

    @property
    def line_total_nok(self):
        return self.food_item.price_nok * self.quantity


class Cart:
    """Priser, navn og minimumsantall kommer alltid fra FoodItem-objektene, aldri fra sessionen."""

    def __init__(self):
        self._lines: dict[int, CartLine] = {}
        self.removed_names: list[str] = []

    @classmethod
    def from_session(cls, data, items):
        """data: {"<item_id>": antall} fra sessionen. items: FoodItem-objekter fra repositoryet.

        Retter som ikke lenger finnes eller er tilgjengelige tas ikke med.
        """
        cart = cls()
        by_id = {item.id: item for item in items}
        for key, quantity in (data or {}).items():
            item = by_id.get(_parse_int(key))
            qty = _parse_int(quantity)
            if item is None or qty is None:
                continue
            if not _is_available(item):
                cart.removed_names.append(item.name)
                continue
            cart._lines[item.id] = CartLine(item, qty)
        return cart

    @property
    def lines(self):
        return sorted(self._lines.values(), key=lambda line: line.food_item.name)

    @property
    def line_count(self):
        return len(self._lines)

    @property
    def is_empty(self):
        return not self._lines

    @property
    def estimated_total_nok(self):
        return sum((line.line_total_nok for line in self._lines.values()), Decimal("0"))

    def quantity_of(self, item_id):
        line = self._lines.get(item_id)
        return line.quantity if line else 0

    def add(self, item, quantity):
        """Legger til en rett, eller øker antallet hvis den allerede ligger i handlekurven (US-06)."""
        if not _is_available(item):
            raise ValidationError({"item": f"{item.name} er ikke tilgjengelig."})
        new_quantity = self.quantity_of(item.id) + _validated_int(quantity)
        _check_minimum(item, new_quantity)
        self._lines[item.id] = CartLine(item, new_quantity)

    def set_quantity(self, item_id, quantity):
        """Endrer antallet på en linje. Under minimum avvises, og handlekurven er uendret (US-07)."""
        line = self._lines.get(item_id)
        if line is None:
            raise ValidationError({"item": "Retten ligger ikke i handlekurven."})
        new_quantity = _validated_int(quantity)
        _check_minimum(line.food_item, new_quantity)
        line.quantity = new_quantity

    def remove(self, item_id):
        self._lines.pop(item_id, None)

    def to_session(self):
        """Bare id og antall – aldri pris."""
        return {str(item_id): line.quantity for item_id, line in self._lines.items()}


def _is_available(item):
    return item.published and not item.archived


def _check_minimum(item, quantity):
    if quantity < item.min_order_qty:
        raise ValidationError(
            {"quantity": f"Minimum for {item.name} er {item.min_order_qty} stk."}
        )


def _validated_int(value):
    number = _parse_int(value)
    if number is None:
        raise ValidationError({"quantity": "Antall må være et helt tall."})
    return number


def _parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
