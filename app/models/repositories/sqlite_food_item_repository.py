"""SQLite-implementasjon av FoodItemRepository."""
from dataclasses import replace
from decimal import Decimal

from app.models.food_item import Allergen, DietaryLabel, EventCategory, FoodItem
from app.models.repositories.base import FoodItemRepository
from app.models.repositories.sqlite_connection import get_db


class SqliteFoodItemRepository(FoodItemRepository):
    def list_published(self, category_name=None):
        sql = "SELECT * FROM food_items f WHERE f.published = 1"
        params = []
        if category_name is not None:
            sql += (
                " AND EXISTS (SELECT 1 FROM food_item_event_categories fc"
                " JOIN event_categories c ON c.id = fc.event_category_id"
                " WHERE fc.food_item_id = f.id AND c.name = ?)"
            )
            params.append(category_name)
        sql += " ORDER BY f.name"
        rows = get_db().execute(sql, params).fetchall()
        return self._with_relations(rows)

    def list_event_categories(self):
        rows = get_db().execute("SELECT id, name FROM event_categories ORDER BY name").fetchall()
        return [EventCategory(id=row["id"], name=row["name"]) for row in rows]

    def add(self, item):
        db = get_db()
        cursor = db.execute(
            "INSERT INTO food_items (name, description, price_nok, min_order_qty, published,"
            " image_path, image_prompt, origin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.name,
                item.description,
                str(item.price_nok),
                item.min_order_qty,
                int(item.published),
                item.image_path,
                item.image_prompt,
                item.origin,
            ),
        )
        item_id = cursor.lastrowid
        db.executemany(
            "INSERT INTO food_item_event_categories (food_item_id, event_category_id) VALUES (?, ?)",
            [(item_id, category.id) for category in item.event_categories],
        )
        db.executemany(
            "INSERT INTO food_item_allergens (food_item_id, allergen_code) VALUES (?, ?)",
            [(item_id, allergen.code) for allergen in item.allergens],
        )
        db.executemany(
            "INSERT INTO food_item_dietary_labels (food_item_id, dietary_label_code) VALUES (?, ?)",
            [(item_id, label.code) for label in item.dietary_labels],
        )
        db.commit()
        return replace(item, id=item_id)

    def add_event_category(self, name):
        db = get_db()
        cursor = db.execute("INSERT INTO event_categories (name) VALUES (?)", (name,))
        db.commit()
        return EventCategory(id=cursor.lastrowid, name=name)

    def add_allergen(self, allergen):
        db = get_db()
        db.execute("INSERT INTO allergens (code, name) VALUES (?, ?)", (allergen.code, allergen.name))
        db.commit()

    def add_dietary_label(self, label):
        db = get_db()
        db.execute("INSERT INTO dietary_labels (code, name) VALUES (?, ?)", (label.code, label.name))
        db.commit()

    def _with_relations(self, rows):
        """Bygger FoodItem-objekter og fyller inn koblingene med én spørring per tabell."""
        items = {row["id"]: self._to_food_item(row) for row in rows}
        if not items:
            return []
        ids = list(items)
        placeholders = ",".join("?" * len(ids))
        db = get_db()

        for row in db.execute(
            "SELECT fc.food_item_id, c.id, c.name FROM food_item_event_categories fc"
            " JOIN event_categories c ON c.id = fc.event_category_id"
            f" WHERE fc.food_item_id IN ({placeholders}) ORDER BY c.name",
            ids,
        ):
            items[row["food_item_id"]].event_categories.append(
                EventCategory(id=row["id"], name=row["name"])
            )

        for row in db.execute(
            "SELECT fa.food_item_id, a.code, a.name FROM food_item_allergens fa"
            " JOIN allergens a ON a.code = fa.allergen_code"
            f" WHERE fa.food_item_id IN ({placeholders}) ORDER BY a.name",
            ids,
        ):
            items[row["food_item_id"]].allergens.append(Allergen(code=row["code"], name=row["name"]))

        for row in db.execute(
            "SELECT fd.food_item_id, d.code, d.name FROM food_item_dietary_labels fd"
            " JOIN dietary_labels d ON d.code = fd.dietary_label_code"
            f" WHERE fd.food_item_id IN ({placeholders}) ORDER BY d.code",
            ids,
        ):
            items[row["food_item_id"]].dietary_labels.append(
                DietaryLabel(code=row["code"], name=row["name"])
            )

        return list(items.values())

    @staticmethod
    def _to_food_item(row):
        return FoodItem(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            price_nok=Decimal(str(row["price_nok"])),
            min_order_qty=row["min_order_qty"],
            published=bool(row["published"]),
            image_path=row["image_path"],
            image_prompt=row["image_prompt"],
            origin=row["origin"],
        )
