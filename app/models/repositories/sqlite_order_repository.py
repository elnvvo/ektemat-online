"""SQLite-implementasjon av OrderRepository."""
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

from app.models.food_item import Allergen, DietaryLabel
from app.models.order import GuestGroup, Order, OrderLine, OrderStatus, PaymentStatus
from app.models.repositories.base import OrderRepository
from app.models.repositories.sqlite_connection import get_db
from app.models.user import Role, User


class SqliteOrderRepository(OrderRepository):
    def save(self, order):
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO orders (user_id, event_date, guest_count, delivery_address, status,"
                " payment_status, status_reason, estimated_total_nok)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    order.user_id,
                    order.event_date.isoformat(),
                    order.guest_count,
                    order.delivery_address,
                    order.status.value,
                    order.payment_status.value,
                    order.status_reason,
                    str(order.estimated_total_nok),
                ),
            )
            order_id = cursor.lastrowid
            db.executemany(
                "INSERT INTO order_lines (order_id, food_item_id, quantity, unit_price_nok)"
                " VALUES (?, ?, ?, ?)",
                [
                    (order_id, line.food_item_id, line.quantity, str(line.unit_price_nok))
                    for line in order.lines
                ],
            )
            for group in order.guest_groups:
                group_id = db.execute(
                    "INSERT INTO guest_groups (order_id, size, notes) VALUES (?, ?, ?)",
                    (order_id, group.size, group.notes),
                ).lastrowid
                db.executemany(
                    "INSERT INTO guest_group_allergens (guest_group_id, allergen_code) VALUES (?, ?)",
                    [(group_id, allergen.code) for allergen in group.allergens],
                )
                db.executemany(
                    "INSERT INTO guest_group_dietary_labels (guest_group_id, dietary_label_code)"
                    " VALUES (?, ?)",
                    [(group_id, label.code) for label in group.dietary_labels],
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
        created_at = db.execute(
            "SELECT created_at FROM orders WHERE id = ?", (order_id,)
        ).fetchone()["created_at"]
        return replace(order, id=order_id, created_at=_parse_datetime(created_at))

    def list_for_user(self, user_id):
        rows = get_db().execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY event_date, id", (user_id,)
        ).fetchall()
        return [_to_order(row) for row in rows]

    def get_for_user(self, order_id, user_id):
        row = get_db().execute(
            "SELECT * FROM orders WHERE id = ? AND user_id = ?", (order_id, user_id)
        ).fetchone()
        return _load_details(_to_order(row)) if row else None

    def list_all(self, status=None, date_from=None, date_to=None):
        sql = _WITH_CUSTOMER + " WHERE 1 = 1"
        params = []
        if status is not None:
            sql += " AND o.status = ?"
            params.append(status.value)
        if date_from is not None:
            sql += " AND o.event_date >= ?"
            params.append(date_from.isoformat())
        if date_to is not None:
            sql += " AND o.event_date <= ?"
            params.append(date_to.isoformat())
        sql += " ORDER BY o.event_date, o.id"
        return [_to_order(row) for row in get_db().execute(sql, params)]

    def get(self, order_id):
        row = get_db().execute(_WITH_CUSTOMER + " WHERE o.id = ?", (order_id,)).fetchone()
        return _load_details(_to_order(row)) if row else None

    def update_status(self, order):
        db = get_db()
        db.execute(
            "UPDATE orders SET status = ?, status_reason = ?, payment_status = ? WHERE id = ?",
            (order.status.value, order.status_reason, order.payment_status.value, order.id),
        )
        db.commit()


# Admin trenger kunden; brukes av list_all og get.
_WITH_CUSTOMER = (
    "SELECT o.*, u.email AS customer_email, u.name AS customer_name,"
    " u.phone AS customer_phone, u.role AS customer_role"
    " FROM orders o LEFT JOIN users u ON u.id = o.user_id"
)


def _load_details(order):
    """Fyller inn linjer og gjestegrupper."""
    db = get_db()

    # Navnet hentes fra matretten (finnes også når den er arkivert); prisen er kopien i ordrelinjen.
    for line in db.execute(
        "SELECT ol.food_item_id, f.name, ol.quantity, ol.unit_price_nok FROM order_lines ol"
        " JOIN food_items f ON f.id = ol.food_item_id WHERE ol.order_id = ? ORDER BY f.name",
        (order.id,),
    ):
        order.lines.append(
            OrderLine(
                food_item_id=line["food_item_id"],
                food_item_name=line["name"],
                quantity=line["quantity"],
                unit_price_nok=Decimal(str(line["unit_price_nok"])),
            )
        )

    groups = {}
    for group in db.execute(
        "SELECT id, size, notes FROM guest_groups WHERE order_id = ? ORDER BY id", (order.id,)
    ):
        groups[group["id"]] = GuestGroup(size=group["size"], notes=group["notes"])
    if groups:
        placeholders = ",".join("?" * len(groups))
        for link in db.execute(
            "SELECT ga.guest_group_id, a.code, a.name FROM guest_group_allergens ga"
            " JOIN allergens a ON a.code = ga.allergen_code"
            f" WHERE ga.guest_group_id IN ({placeholders}) ORDER BY a.name",
            list(groups),
        ):
            groups[link["guest_group_id"]].allergens.append(Allergen(link["code"], link["name"]))
        for link in db.execute(
            "SELECT gd.guest_group_id, d.code, d.name FROM guest_group_dietary_labels gd"
            " JOIN dietary_labels d ON d.code = gd.dietary_label_code"
            f" WHERE gd.guest_group_id IN ({placeholders}) ORDER BY d.code",
            list(groups),
        ):
            groups[link["guest_group_id"]].dietary_labels.append(
                DietaryLabel(link["code"], link["name"])
            )
    order.guest_groups = list(groups.values())
    return order


def _to_order(row):
    """Ordren uten linjer og gjestegrupper."""
    return Order(
        id=row["id"],
        user_id=row["user_id"],
        event_date=date.fromisoformat(row["event_date"]),
        guest_count=row["guest_count"],
        delivery_address=row["delivery_address"],
        status=OrderStatus(row["status"]),
        payment_status=PaymentStatus(row["payment_status"]),
        status_reason=row["status_reason"],
        estimated_total_nok=Decimal(str(row["estimated_total_nok"])),
        created_at=_parse_datetime(row["created_at"]),
        customer=_to_customer(row),
    )


def _to_customer(row):
    """Kunden fra en rad med customer_*-kolonner (uten passordhash), ellers None."""
    if "customer_email" not in row.keys() or row["customer_email"] is None:
        return None
    return User(
        id=row["user_id"],
        email=row["customer_email"],
        name=row["customer_name"],
        phone=row["customer_phone"],
        password_hash="",
        role=Role(row["customer_role"]),
    )


def _parse_datetime(value):
    return datetime.fromisoformat(value) if value else None
