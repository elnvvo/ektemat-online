"""Lager databasetabellene og legger inn syntetiske brukere og høstmenyen.

Kjør: python seed.py   (sletter og lager databasen på nytt)
"""
import os
import sys
from decimal import Decimal

from werkzeug.security import generate_password_hash

from app import create_app
from app.models.food_item import Allergen, DietaryLabel, FoodItem
from app.models.repositories import food_item_repository
from app.models.repositories.sqlite_connection import init_db, seed_users

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

    return [
        {
            "email": "admin@ektemat.test",
            "name": "Admin Testesen",
            "phone": None,
            "password_hash": generate_password_hash(admin_password),
            "role": "admin",
        },
        {
            "email": "kunde1@example.test",
            "name": "Kari Testkunde",
            "phone": "40000001",
            "password_hash": generate_password_hash(customer_password),
            "role": "customer",
        },
        {
            "email": "kunde2@example.test",
            "name": "Ola Testkunde",
            "phone": "40000002",
            "password_hash": generate_password_hash(customer_password),
            "role": "customer",
        },
    ]


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


def main():
    users = build_users()

    app = create_app()
    with app.app_context():
        init_db()
        seed_users(users)
        items = seed_menu()

    print(f"Database laget: {app.config['DATABASE']}")
    for user in users:
        print(f"  {user['role']:<8} {user['email']}")
    for item in items:
        status = "publisert" if item.published else "ikke publisert"
        print(f"  rett     {item.name} ({item.price_nok} kr, {status})")


if __name__ == "__main__":
    main()
