"""Bestillinger, ordrelinjer og gjestegrupper (design.md §2–§5, US-08, US-09)."""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from app.models.errors import ValidationError
from app.models.food_item import Allergen, DietaryLabel


class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    IN_PREPARATION = "in_preparation"
    DELIVERED = "delivered"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

    @property
    def label(self):
        return {
            "submitted": "Sendt inn",
            "approved": "Godkjent",
            "in_preparation": "Under forberedelse",
            "delivered": "Levert",
            "rejected": "Avvist",
            "cancelled": "Kansellert",
        }[self.value]


class PaymentStatus(str, Enum):
    NOT_PAID = "not_paid"
    DEPOSIT_PAID = "deposit_paid"
    INVOICED = "invoiced"
    PAID = "paid"

    @property
    def label(self):
        return {
            "not_paid": "Ikke betalt",
            "deposit_paid": "Depositum betalt",
            "invoiced": "Fakturert",
            "paid": "Betalt",
        }[self.value]


@dataclass
class OrderLine:
    food_item_id: int
    food_item_name: str
    quantity: int
    # Kopieres fra matretten ved bestilling, så senere prisendringer ikke endrer gamle ordre.
    unit_price_nok: Decimal

    @property
    def line_total_nok(self):
        return self.unit_price_nok * self.quantity


@dataclass
class GuestGroup:
    """Allergier og dietter per gruppe. Ingen navn på gjester (GDPR, NFR-04)."""

    size: int
    allergens: list[Allergen] = field(default_factory=list)
    dietary_labels: list[DietaryLabel] = field(default_factory=list)
    notes: str = ""


@dataclass
class Order:
    id: int | None
    user_id: int
    event_date: date
    guest_count: int
    delivery_address: str
    status: OrderStatus = OrderStatus.SUBMITTED
    payment_status: PaymentStatus = PaymentStatus.NOT_PAID
    status_reason: str | None = None
    estimated_total_nok: Decimal = Decimal("0")
    created_at: datetime | None = None
    lines: list[OrderLine] = field(default_factory=list)
    guest_groups: list[GuestGroup] = field(default_factory=list)

    @property
    def number(self):
        return f"EM-{self.id:05d}" if self.id is not None else ""

    @property
    def guest_group_total(self):
        return sum(group.size for group in self.guest_groups)

    @classmethod
    def create_from_cart(
        cls, user, cart, event_date, guest_count, delivery_address, guest_groups, today=None
    ):
        """Lager en ny bestilling fra handlekurven (design.md §3). All validering skjer her.

        guest_groups: liste med dicts {"size", "allergens", "dietary_labels", "notes"} fra
        skjemaet, i samme rekkefølge som i skjemaet. Helt tomme grupper hoppes over.
        Kaster ValidationError({felt: melding}).
        """
        today = today or date.today()
        errors = {}

        if cart.is_empty:
            errors["cart"] = "Handlekurven er tom."
        for line in cart.lines:
            item = line.food_item
            if line.quantity < item.min_order_qty:
                errors["cart"] = f"Minimum for {item.name} er {item.min_order_qty} stk."

        parsed_date = _parse_date(event_date)
        if parsed_date is None:
            errors["event_date"] = "Velg en gyldig arrangementsdato."
        elif parsed_date <= today:
            errors["event_date"] = "Arrangementsdatoen må være i fremtiden."

        guests = _parse_int(guest_count)
        if guests is None or guests < 1:
            errors["guest_count"] = "Antall gjester må være minst 1."

        address = (delivery_address or "").strip()
        if not address:
            errors["delivery_address"] = "Skriv inn leveringsadressen."

        groups = []
        for index, data in enumerate(guest_groups, start=1):
            if _is_blank_group(data):
                continue
            size = _parse_int(data.get("size"))
            problems = []
            if size is None or size < 1:
                problems.append("antall må være minst 1")
            if not data.get("allergens") and not data.get("dietary_labels"):
                problems.append("velg minst ett allergen eller diettmerke")
            if problems:
                errors[f"guest_group-{index}"] = f"Gjestegruppe {index}: {' og '.join(problems)}."
                continue
            groups.append(
                GuestGroup(
                    size=size,
                    allergens=list(data.get("allergens") or []),
                    dietary_labels=list(data.get("dietary_labels") or []),
                    notes=(data.get("notes") or "").strip(),
                )
            )

        group_total = sum(group.size for group in groups)
        if guests is not None and guests >= 1 and group_total > guests:
            errors["guest_groups"] = (
                f"Gjestegruppene har til sammen {group_total} gjester, "
                f"men bestillingen har bare {guests}."
            )

        if errors:
            raise ValidationError(errors)

        lines = [
            OrderLine(
                food_item_id=line.food_item.id,
                food_item_name=line.food_item.name,
                quantity=line.quantity,
                unit_price_nok=line.food_item.price_nok,
            )
            for line in cart.lines
        ]
        return cls(
            id=None,
            user_id=user.id,
            event_date=parsed_date,
            guest_count=guests,
            delivery_address=address,
            status=OrderStatus.SUBMITTED,
            payment_status=PaymentStatus.NOT_PAID,
            estimated_total_nok=sum((line.line_total_nok for line in lines), Decimal("0")),
            lines=lines,
            guest_groups=groups,
        )


def _is_blank_group(data):
    return (
        not str(data.get("size") or "").strip()
        and not data.get("allergens")
        and not data.get("dietary_labels")
        and not (data.get("notes") or "").strip()
    )


def _parse_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def _parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
