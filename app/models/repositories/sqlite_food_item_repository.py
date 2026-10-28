"""SQLite-implementasjon av FoodItemRepository."""
from dataclasses import replace
from decimal import Decimal

from app.models.food_item import Allergen, DietaryLabel, EventCategory, FoodItem
from app.models.repositories.base import FoodItemRepository
from app.models.repositories.sqlite_connection import get_db


class SqliteFoodItemRepository(FoodItemRepository):
    def list_published(self, category_name=None):
        sql = "SELECT * FROM food_items f WHERE f.published = 1 AND f.archived = 0"
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

    def list_all(self):
        rows = get_db().execute("SELECT * FROM food_items ORDER BY name").fetchall()
        return self._with_relations(rows)

    def get(self, item_id):
        row = get_db().execute("SELECT * FROM food_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return None
        return self._with_relations([row])[0]

    def get_by_ids(self, item_ids):
        ids = [int(item_id) for item_id in item_ids]
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        rows = get_db().execute(
            f"SELECT * FROM food_items WHERE id IN ({placeholders}) ORDER BY name", ids
        ).fetchall()
        return self._with_relations(rows)

    def list_event_categories(self):
        rows = get_db().execute("SELECT id, name FROM event_categories ORDER BY name").fetchall()
        return [EventCategory(id=row["id"], name=row["name"]) for row in rows]

    def list_allergens(self):
        rows = get_db().execute("SELECT code, name FROM allergens ORDER BY name").fetchall()
        return [Allergen(code=row["code"], name=row["name"]) for row in rows]

    def list_dietary_labels(self):
        rows = get_db().execute("SELECT code, name FROM dietary_labels ORDER BY code").fetchall()
        return [DietaryLabel(code=row["code"], name=row["name"]) for row in rows]

    def add(self, item):
        db = get_db()
        cursor = db.execute(
            "INSERT INTO food_items (name, description, price_nok, min_order_qty, published,"
            " archived, image_path, image_prompt, origin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.name,
                item.description,
                str(item.price_nok),
                item.min_order_qty,
                int(item.published),
                int(item.archived),
                item.image_path,
                item.image_prompt,
                item.origin,
            ),
        )
        item_id = cursor.lastrowid
        self._insert_relations(item_id, item)
        db.commit()
        return replace(item, id=item_id)

    def update(self, item):
        db = get_db()
        db.execute(
            "UPDATE food_items SET name = ?, description = ?, price_nok = ?, min_order_qty = ?,"
            " published = ?, image_path = ?, image_prompt = ?, origin = ? WHERE id = ?",
            (
                item.name,
                item.description,
                str(item.price_nok),
                item.min_order_qty,
                int(item.published),
                item.image_path,
                item.image_prompt,
                item.origin,
                item.id,
            ),
        )
        for table in ("food_item_event_categories", "food_item_allergens", "food_item_dietary_labels"):
            db.execute(f"DELETE FROM {table} WHERE food_item_id = ?", (item.id,))
        self._insert_relations(item.id, item)
        db.commit()
        return item

    def set_image(self, item_id, image_path, image_prompt):
        db = get_db()
        db.execute(
            "UPDATE food_items SET image_path = ?, image_prompt = ? WHERE id = ?",
            (image_path, image_prompt, item_id),
        )
        db.commit()

    def set_published(self, item_id, published):
        self._set_flags(item_id, published=published)

    def archive(self, item_id):
        self._set_flags(item_id, published=False, archived=True)

    def restore(self, item_id):
        self._set_flags(item_id, published=False, archived=False)

    def _set_flags(self, item_id, published, archived=None):
        db = get_db()
        if archived is None:
            db.execute("UPDATE food_items SET published = ? WHERE id = ?", (int(published), item_id))
        else:
            db.execute(
                "UPDATE food_items SET published = ?, archived = ? WHERE id = ?",
                (int(published), int(archived), item_id),
            )
        db.commit()

    def _insert_relations(self, item_id, item):
        db = get_db()
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
            archived=bool(row["archived"]),
            image_path=row["image_path"],
            image_prompt=row["image_prompt"],
            origin=row["origin"],
        )
