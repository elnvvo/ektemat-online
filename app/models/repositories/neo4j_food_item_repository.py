"""Neo4j-implementasjon av FoodItemRepository (design.md §7).

(:FoodItem)-[:SUITS]->(:EventCategory), -[:CONTAINS_ALLERGEN]->(:Allergen), -[:HAS_LABEL]->(:DietaryLabel).
Kategorier, allergener og diettmerker er delte noder. Prisen lagres som tekst for å være eksakt.
"""
from dataclasses import replace
from decimal import Decimal

from app.models.food_item import Allergen, DietaryLabel, EventCategory, FoodItem
from app.models.repositories import neo4j_connection as db
from app.models.repositories.base import FoodItemRepository

# Retten med alle koblinger i én spørring (ingen N+1).
_RETURN_ITEMS = (
    " RETURN f {.*} AS item,"
    " [(f)-[:SUITS]->(c:EventCategory) | c {.id, .name}] AS categories,"
    " [(f)-[:CONTAINS_ALLERGEN]->(a:Allergen) | a {.code, .name}] AS allergens,"
    " [(f)-[:HAS_LABEL]->(d:DietaryLabel) | d {.code, .name}] AS labels"
    " ORDER BY f.name, f.id"
)

LIST_PUBLISHED = (
    "MATCH (f:FoodItem)"
    " WHERE f.published AND NOT f.archived"
    " AND ($category IS NULL OR EXISTS { (f)-[:SUITS]->(:EventCategory {name: $category}) })"
    + _RETURN_ITEMS
)
LIST_ALL = "MATCH (f:FoodItem)" + _RETURN_ITEMS
GET = "MATCH (f:FoodItem {id: $id})" + _RETURN_ITEMS
GET_BY_IDS = "MATCH (f:FoodItem) WHERE f.id IN $ids" + _RETURN_ITEMS

LIST_CATEGORIES = "MATCH (c:EventCategory) RETURN c.id AS id, c.name AS name ORDER BY c.name"
LIST_ALLERGENS = "MATCH (a:Allergen) RETURN a.code AS code, a.name AS name ORDER BY a.name"
LIST_LABELS = "MATCH (d:DietaryLabel) RETURN d.code AS code, d.name AS name ORDER BY d.code"

CREATE_ITEM = "CREATE (f:FoodItem {id: $id}) SET f += $props"
UPDATE_ITEM = "MATCH (f:FoodItem {id: $id}) SET f += $props"
REMOVE_LINKS = "MATCH (f:FoodItem {id: $id})-[r:SUITS|CONTAINS_ALLERGEN|HAS_LABEL]->() DELETE r"
LINK_CATEGORIES = (
    "MATCH (f:FoodItem {id: $id}) UNWIND $category_ids AS category_id"
    " MATCH (c:EventCategory {id: category_id}) MERGE (f)-[:SUITS]->(c)"
)
LINK_ALLERGENS = (
    "MATCH (f:FoodItem {id: $id}) UNWIND $codes AS code"
    " MATCH (a:Allergen {code: code}) MERGE (f)-[:CONTAINS_ALLERGEN]->(a)"
)
LINK_LABELS = (
    "MATCH (f:FoodItem {id: $id}) UNWIND $codes AS code"
    " MATCH (d:DietaryLabel {code: code}) MERGE (f)-[:HAS_LABEL]->(d)"
)

SET_PUBLISHED = "MATCH (f:FoodItem {id: $id}) SET f.published = $published"
SET_FLAGS = "MATCH (f:FoodItem {id: $id}) SET f.published = $published, f.archived = $archived"
SET_IMAGE = "MATCH (f:FoodItem {id: $id}) SET f.image_path = $image_path, f.image_prompt = $image_prompt"

CREATE_CATEGORY = "CREATE (c:EventCategory {id: $id, name: $name})"
CREATE_ALLERGEN = "CREATE (a:Allergen {code: $code, name: $name})"
CREATE_LABEL = "CREATE (d:DietaryLabel {code: $code, name: $name})"


class Neo4jFoodItemRepository(FoodItemRepository):
    def list_published(self, category_name=None):
        return _to_items(db.run_read(LIST_PUBLISHED, category=category_name))

    def list_all(self):
        return _to_items(db.run_read(LIST_ALL))

    def get(self, item_id):
        items = _to_items(db.run_read(GET, id=item_id))
        return items[0] if items else None

    def get_by_ids(self, item_ids):
        ids = [int(item_id) for item_id in item_ids]
        return _to_items(db.run_read(GET_BY_IDS, ids=ids)) if ids else []

    def list_event_categories(self):
        return [EventCategory(id=r["id"], name=r["name"]) for r in db.run_read(LIST_CATEGORIES)]

    def list_allergens(self):
        return [Allergen(code=r["code"], name=r["name"]) for r in db.run_read(LIST_ALLERGENS)]

    def list_dietary_labels(self):
        return [DietaryLabel(code=r["code"], name=r["name"]) for r in db.run_read(LIST_LABELS)]

    def add(self, item):
        def work(tx):
            item_id = db.next_id(tx, "FoodItem")
            tx.run(CREATE_ITEM, id=item_id, props=_properties(item, include_archived=True))
            _link(tx, item_id, item)
            return item_id

        return replace(item, id=db.write_transaction(work))

    def update(self, item):
        def work(tx):
            tx.run(UPDATE_ITEM, id=item.id, props=_properties(item, include_archived=False))
            tx.run(REMOVE_LINKS, id=item.id)
            _link(tx, item.id, item)

        db.write_transaction(work)
        return item

    def set_image(self, item_id, image_path, image_prompt):
        db.run_write(SET_IMAGE, id=item_id, image_path=image_path, image_prompt=image_prompt)

    def set_published(self, item_id, published):
        db.run_write(SET_PUBLISHED, id=item_id, published=bool(published))

    def archive(self, item_id):
        db.run_write(SET_FLAGS, id=item_id, published=False, archived=True)

    def restore(self, item_id):
        db.run_write(SET_FLAGS, id=item_id, published=False, archived=False)

    def add_event_category(self, name):
        def work(tx):
            category_id = db.next_id(tx, "EventCategory")
            tx.run(CREATE_CATEGORY, id=category_id, name=name)
            return category_id

        return EventCategory(id=db.write_transaction(work), name=name)

    def add_allergen(self, allergen):
        db.run_write(CREATE_ALLERGEN, code=allergen.code, name=allergen.name)

    def add_dietary_label(self, label):
        db.run_write(CREATE_LABEL, code=label.code, name=label.name)


def _link(tx, item_id, item):
    tx.run(LINK_CATEGORIES, id=item_id, category_ids=[c.id for c in item.event_categories])
    tx.run(LINK_ALLERGENS, id=item_id, codes=[a.code for a in item.allergens])
    tx.run(LINK_LABELS, id=item_id, codes=[d.code for d in item.dietary_labels])


def _properties(item, include_archived):
    """Egenskapene på noden. update() endrer ikke archived (samme som SQLite)."""
    props = {
        "name": item.name,
        "description": item.description,
        "price_nok": str(item.price_nok),
        "min_order_qty": item.min_order_qty,
        "published": bool(item.published),
        "image_path": item.image_path,
        "image_prompt": item.image_prompt,
        "origin": item.origin,
    }
    if include_archived:
        props["archived"] = bool(item.archived)
    return props


def _to_items(records):
    return [_to_item(record) for record in records]


def _to_item(record):
    props = record["item"]
    return FoodItem(
        id=props["id"],
        name=props["name"],
        description=props.get("description") or "",
        price_nok=Decimal(props["price_nok"]),
        min_order_qty=props["min_order_qty"],
        published=bool(props.get("published")),
        image_path=props.get("image_path"),
        image_prompt=props.get("image_prompt"),
        origin=props.get("origin"),
        archived=bool(props.get("archived")),
        event_categories=[
            EventCategory(id=c["id"], name=c["name"])
            for c in sorted(record["categories"], key=lambda c: c["name"])
        ],
        allergens=[
            Allergen(code=a["code"], name=a["name"])
            for a in sorted(record["allergens"], key=lambda a: a["name"])
        ],
        dietary_labels=[
            DietaryLabel(code=d["code"], name=d["name"])
            for d in sorted(record["labels"], key=lambda d: d["code"])
        ],
    )
