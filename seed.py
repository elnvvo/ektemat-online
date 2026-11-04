"""Tømmer lagringen STORAGE peker på og legger inn syntetiske brukere og høstmenyen.

Kjør: python seed.py          (SQLite: sletter og lager databasen på nytt)
      python seed.py --yes    (Neo4j: hopper over spørsmålet før den delte databasen tømmes)
"""
import os
import sys
from decimal import Decimal

from app import create_app
from app.models.errors import ValidationError
from app.models.food_item import Allergen, DietaryLabel, FoodItem
from app.models.repositories import food_item_repository, init_storage, user_repository
from app.models.repositories.neo4j_connection import describe_target
from app.models.user import User

PLACEHOLDER_IMAGE = "img/placeholder.svg"

EVENT_CATEGORIES = ["Bryllup", "Konfirmasjon", "Bursdag", "Konferanse", "Julebord"]

# Allergenene som skal merkes ifølge høstmenyen.
ALLERGENS = [
    Allergen("fish", "Fisk"),
    Allergen("milk", "Melk"),
    Allergen("gluten", "Gluten"),
    Allergen("nuts", "Nøtter"),
    Allergen("celery", "Selleri"),
    Allergen("mustard", "Sennep"),
]

DIETARY_LABELS = [
    DietaryLabel("V", "Vegetar"),
    DietaryLabel("VG", "Vegan"),
    DietaryLabel("GF", "Glutenfri"),
]

# Høstmenyen (syntetiske data). Rakfisk er sesongvare (bare november) og er ikke publisert ennå.
FOOD_ITEMS = [
    {
        "name": "Fiskesuppe",
        "description": "Kremet suppe med torsk, laks og rotgrønnsaker.",
        "price_nok": Decimal("189"),
        "min_order_qty": 10,
        "published": True,
        "categories": ["Konferanse", "Konfirmasjon", "Julebord"],
        "allergens": ["fish", "milk", "celery"],
        "dietary_labels": [],
    },
    {
        "name": "Lam fra Voss",
        "description": "Langtidsbakt lammeskulder med rotgrønnsaker og sennepssaus.",
        "price_nok": Decimal("245"),
        "min_order_qty": 10,
        "published": True,
        "origin": "Voss",
        "categories": ["Bryllup", "Konfirmasjon", "Julebord"],
        "allergens": ["celery", "mustard"],
        "dietary_labels": ["GF"],
    },
    {
        "name": "Rødbete- og kikertsalat",
        "description": "Bakte rødbeter, kikerter og urter med sennepsvinaigrette.",
        "price_nok": Decimal("165"),
        "min_order_qty": 10,
        "published": True,
        "categories": ["Bryllup", "Konfirmasjon", "Bursdag", "Konferanse"],
        "allergens": ["mustard"],
        "dietary_labels": ["V"],
    },
    {
        "name": "Rakfisk",
        "description": "Rakfisk med lefse, rømme og rødløk. Bare i november.",
        "price_nok": Decimal("210"),
        "min_order_qty": 8,
        "published": False,
        "categories": ["Julebord"],
        "allergens": ["fish", "gluten", "milk"],
        "dietary_labels": [],
    },
]


def build_users():
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD")
    customer_password = os.environ.get("SEED_CUSTOMER_PASSWORD")
    if not admin_password or not customer_password:
        sys.exit("Sett SEED_ADMIN_PASSWORD og SEED_CUSTOMER_PASSWORD i .env (se .env.example).")

    # Admin lages bare her; den kan ikke registreres via nettsiden (US-20).
    try:
        return [
            User.create_admin("admin@ektemat.test", "Admin Testesen", admin_password),
            User.register("kunde1@example.test", "Kari Testkunde", customer_password, phone="40000001"),
            User.register("kunde2@example.test", "Ola Testkunde", customer_password, phone="40000002"),
        ]
    except ValidationError as error:
        sys.exit(f"Ugyldige seed-passord i .env: {error.messages}")


def seed_users(users):
    repository = user_repository()
    return [repository.add(user) for user in users]


def seed_menu():
    repository = food_item_repository()
    categories = {name: repository.add_event_category(name) for name in EVENT_CATEGORIES}
    allergens = {allergen.code: allergen for allergen in ALLERGENS}
    labels = {label.code: label for label in DIETARY_LABELS}
    for allergen in ALLERGENS:
        repository.add_allergen(allergen)
    for label in DIETARY_LABELS:
        repository.add_dietary_label(label)

    items = []
    for data in FOOD_ITEMS:
        items.append(
            repository.add(
                FoodItem(
                    id=None,
                    name=data["name"],
                    description=data["description"],
                    price_nok=data["price_nok"],
                    min_order_qty=data["min_order_qty"],
                    published=data["published"],
                    image_path=PLACEHOLDER_IMAGE,
                    origin=data.get("origin"),
                    event_categories=[categories[name] for name in data["categories"]],
                    allergens=[allergens[code] for code in data["allergens"]],
                    dietary_labels=[labels[code] for code in data["dietary_labels"]],
                )
            )
        )
    return items


def confirm_neo4j_reset():
    """Neo4j-databasen er delt i gruppen; ikke tøm den ved et uhell."""
    print(f"STORAGE=neo4j: ALT i {describe_target()} blir slettet og erstattet med testdata.")
    if "--yes" in sys.argv[1:]:
        return
    if input("Skriv ja for å fortsette: ").strip().lower() != "ja":
        sys.exit("Avbrutt – ingenting er endret.")


def main():
    users = build_users()

    app = create_app()
    storage = app.config["STORAGE"]
    with app.app_context():
        if storage == "neo4j":
            confirm_neo4j_reset()
        init_storage()
        users = seed_users(users)
        items = seed_menu()
        target = describe_target() if storage == "neo4j" else app.config["DATABASE"]

    print(f"Database laget ({storage}): {target}")
    for user in users:
        print(f"  {user.role.value:<8} {user.email}")
    for item in items:
        status = "publisert" if item.published else "ikke publisert"
        print(f"  rett     {item.name} ({item.price_nok} kr, {status})")


if __name__ == "__main__":
    main()
