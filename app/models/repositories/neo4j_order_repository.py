"""Neo4j-implementasjon av OrderRepository (design.md §7).

(:User)-[:PLACED]->(:Order)-[:CONTAINS {quantity, unit_price_nok}]->(:FoodItem)
(:Order)-[:HAS_GUEST_GROUP]->(:GuestGroup {position, size, notes})-[:AVOIDS]->(:Allergen), -[:NEEDS]->(:DietaryLabel)
Gjestegruppene har ingen navn (NFR-04). Beløp lagres som tekst for å være eksakte.
"""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from app.models.food_item import Allergen, DietaryLabel
from app.models.order import GuestGroup, Order, OrderLine, OrderStatus, PaymentStatus
from app.models.repositories import neo4j_connection as db
from app.models.repositories.base import OrderRepository
from app.models.user import Role, User

CREATE_ORDER = (
    "MATCH (u:User {id: $user_id})"
    " CREATE (u)-[:PLACED]->(o:Order {id: $id}) SET o += $props"
    " RETURN o.id AS id"
)
ADD_LINES = (
    "MATCH (o:Order {id: $id}) UNWIND $lines AS line"
    " MATCH (f:FoodItem {id: line.food_item_id})"
    " CREATE (o)-[:CONTAINS {quantity: line.quantity, unit_price_nok: line.unit_price_nok}]->(f)"
    " RETURN count(*) AS created"
)
ADD_GUEST_GROUP = (
    "MATCH (o:Order {id: $id})"
    " CREATE (o)-[:HAS_GUEST_GROUP]->(g:GuestGroup {position: $position, size: $size, notes: $notes})"
    " WITH g OPTIONAL MATCH (a:Allergen) WHERE a.code IN $allergen_codes"
    " WITH g, collect(a) AS allergens OPTIONAL MATCH (d:DietaryLabel) WHERE d.code IN $label_codes"
    " WITH g, allergens, collect(d) AS labels"
    " FOREACH (a IN allergens | CREATE (g)-[:AVOIDS]->(a))"
    " FOREACH (d IN labels | CREATE (g)-[:NEEDS]->(d))"
    " RETURN size(allergens) AS allergens, size(labels) AS labels"
)

_CUSTOMER = " u {.id, .email, .name, .phone, .role} AS customer"
_DETAILS = (
    " RETURN o {.*} AS order, u.id AS user_id," + _CUSTOMER + ","
    " [(o)-[c:CONTAINS]->(f:FoodItem) | {food_item_id: f.id, name: f.name,"
    " quantity: c.quantity, unit_price_nok: c.unit_price_nok}] AS lines,"
    " [(o)-[:HAS_GUEST_GROUP]->(g:GuestGroup) | {position: g.position, size: g.size, notes: g.notes,"
    " allergens: [(g)-[:AVOIDS]->(a:Allergen) | a {.code, .name}],"
    " labels: [(g)-[:NEEDS]->(d:DietaryLabel) | d {.code, .name}]}] AS groups"
)
_SUMMARY = " RETURN o {.*} AS order, u.id AS user_id," + _CUSTOMER + " ORDER BY o.event_date, o.id"

GET = "MATCH (o:Order {id: $id}) OPTIONAL MATCH (u:User)-[:PLACED]->(o)" + _DETAILS
GET_FOR_USER = "MATCH (u:User {id: $user_id})-[:PLACED]->(o:Order {id: $id})" + _DETAILS
LIST_FOR_USER = "MATCH (u:User {id: $user_id})-[:PLACED]->(o:Order)" + _SUMMARY
LIST_ALL = (
    "MATCH (o:Order)"
    " WHERE ($status IS NULL OR o.status = $status)"
    " AND ($date_from IS NULL OR o.event_date >= $date_from)"
    " AND ($date_to IS NULL OR o.event_date <= $date_to)"
    " OPTIONAL MATCH (u:User)-[:PLACED]->(o)" + _SUMMARY
)
UPDATE_STATUS = (
    "MATCH (o:Order {id: $id})"
    " SET o.status = $status, o.status_reason = $status_reason, o.payment_status = $payment_status"
)


class Neo4jOrderRepository(OrderRepository):
    def save(self, order):
        """Ordre, linjer og gjestegrupper i én transaksjon: alt eller ingenting."""
        created_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)  # UTC, som SQLite

        def work(tx):
            order_id = db.next_id(tx, "Order")
            if tx.run(CREATE_ORDER, id=order_id, user_id=order.user_id, props=_properties(order, created_at)).single() is None:
                raise LookupError(f"Fant ikke kunden {order.user_id}; ordren er ikke lagret.")

            lines = [
                {
                    "food_item_id": line.food_item_id,
                    "quantity": line.quantity,
                    "unit_price_nok": str(line.unit_price_nok),
                }
                for line in order.lines
            ]
            if tx.run(ADD_LINES, id=order_id, lines=lines).single()["created"] != len(lines):
                raise LookupError("En rett i bestillingen finnes ikke; ordren er ikke lagret.")

            for position, group in enumerate(order.guest_groups, start=1):
                allergen_codes = [a.code for a in group.allergens]
                label_codes = [d.code for d in group.dietary_labels]
                result = tx.run(
                    ADD_GUEST_GROUP,
                    id=order_id,
                    position=position,
                    size=group.size,
                    notes=group.notes,
                    allergen_codes=allergen_codes,
                    label_codes=label_codes,
                ).single()
                if (result["allergens"], result["labels"]) != (len(allergen_codes), len(label_codes)):
                    raise LookupError("Et allergen eller diettmerke finnes ikke; ordren er ikke lagret.")
            return order_id

        return replace(order, id=db.write_transaction(work), created_at=created_at)

    def list_for_user(self, user_id):
        return [_to_order(r, with_customer=False) for r in db.run_read(LIST_FOR_USER, user_id=user_id)]

    def get_for_user(self, order_id, user_id):
        records = db.run_read(GET_FOR_USER, id=order_id, user_id=user_id)
        return _with_details(_to_order(records[0], with_customer=False), records[0]) if records else None

    def list_all(self, status=None, date_from=None, date_to=None):
        records = db.run_read(
            LIST_ALL,
            status=status.value if status is not None else None,
            date_from=date_from,
            date_to=date_to,
        )
        return [_to_order(r, with_customer=True) for r in records]

    def get(self, order_id):
        records = db.run_read(GET, id=order_id)
        return _with_details(_to_order(records[0], with_customer=True), records[0]) if records else None

    def update_status(self, order):
        db.run_write(
            UPDATE_STATUS,
            id=order.id,
            status=order.status.value,
            status_reason=order.status_reason,
            payment_status=order.payment_status.value,
        )


def _properties(order, created_at):
    return {
        "created_at": created_at,
        "event_date": order.event_date,
        "guest_count": order.guest_count,
        "delivery_address": order.delivery_address,
        "status": order.status.value,
        "payment_status": order.payment_status.value,
        "status_reason": order.status_reason,
        "estimated_total_nok": str(order.estimated_total_nok),
    }


def _to_order(record, with_customer):
    props = record["order"]
    return Order(
        id=props["id"],
        user_id=record["user_id"],
        event_date=_native(props["event_date"]),
        guest_count=props["guest_count"],
        delivery_address=props["delivery_address"],
        status=OrderStatus(props["status"]),
        payment_status=PaymentStatus(props["payment_status"]),
        status_reason=props.get("status_reason"),
        estimated_total_nok=Decimal(props["estimated_total_nok"]),
        created_at=_native(props.get("created_at")),
        customer=_to_customer(record["customer"]) if with_customer else None,
    )


def _with_details(order, record):
    """Linjene etter rettens navn og gruppene i rekkefølgen kunden la dem inn (som i SQLite)."""
    order.lines = [
        OrderLine(
            food_item_id=line["food_item_id"],
            food_item_name=line["name"],
            quantity=line["quantity"],
            unit_price_nok=Decimal(line["unit_price_nok"]),
        )
        for line in sorted(record["lines"], key=lambda line: line["name"])
    ]
    order.guest_groups = [
        GuestGroup(
            size=group["size"],
            notes=group["notes"] or "",
            allergens=[Allergen(a["code"], a["name"]) for a in sorted(group["allergens"], key=lambda a: a["name"])],
            dietary_labels=[
                DietaryLabel(d["code"], d["name"]) for d in sorted(group["labels"], key=lambda d: d["code"])
            ],
        )
        for group in sorted(record["groups"], key=lambda group: group["position"])
    ]
    return order


def _to_customer(props):
    if props is None:
        return None
    return User(
        id=props["id"],
        email=props["email"],
        name=props["name"],
        phone=props.get("phone"),
        password_hash="",  # passordhashen hentes aldri sammen med ordre
        role=Role(props["role"]),
    )


def _native(value):
    """neo4j.time.Date/DateTime -> datetime.date/datetime."""
    return value.to_native() if hasattr(value, "to_native") else value
