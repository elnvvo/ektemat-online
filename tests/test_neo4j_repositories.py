"""Neo4j-repositoryene mot den ekte databasen fra .env (Oblig 5).

Kjøres bare med «pytest -m neo4j», og hoppes over uten NEO4J_URI. Databasen er delt, så
testene tømmer den aldri: alt de lager har unike navn for kjøringen og slettes etterpå.
"""
import uuid
from dataclasses import replace
from decimal import Decimal

import pytest

from app import create_app
from app.config import Config
from app.models.errors import DuplicateEmailError
from app.models.food_item import Allergen, DietaryLabel, FoodItem
from app.models.repositories import food_item_repository, user_repository
from app.models.repositories.neo4j_connection import ensure_constraints, run_write
from app.models.user import User

pytestmark = pytest.mark.neo4j

# Opprydding: bare nodene denne testkjøringen har laget (gjestegruppene først, via ordrene sine).
DELETE_TEST_GUEST_GROUPS = (
    "MATCH (o:Order)-[:HAS_GUEST_GROUP]->(g:GuestGroup) WHERE o.id IN $order_ids DETACH DELETE g"
)
DELETE_TEST_NODES = (
    "MATCH (n) WHERE (n:FoodItem AND n.id IN $item_ids)"
    " OR (n:EventCategory AND n.id IN $category_ids)"
    " OR (n:Allergen AND n.code IN $codes) OR (n:DietaryLabel AND n.code IN $codes)"
    " OR (n:User AND n.email IN $emails)"
    " OR (n:Order AND n.id IN $order_ids)"
    " OR (n:Question AND n.id IN $question_ids) OR (n:Answer AND n.question_id IN $question_ids)"
    " DETACH DELETE n"
)


@pytest.fixture
def neo4j_app(tmp_path):
    missing = [key for key in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD") if not getattr(Config, key)]
    if missing:
        pytest.skip(f"{', '.join(missing)} mangler i .env")
    app = create_app(
        {"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(tmp_path / "t.sqlite"), "STORAGE": "neo4j"}
    )
    with app.app_context():
        ensure_constraints()  # IF NOT EXISTS – sletter ingenting
        yield app
    app.extensions["neo4j"].close()


@pytest.fixture
def created(neo4j_app):
    """Samler alt testen lager, og sletter akkurat det etterpå."""
    made = {
        "item_ids": [], "category_ids": [], "codes": [], "emails": [], "order_ids": [], "question_ids": [],
        "run": uuid.uuid4().hex[:8],
    }
    yield made
    run_write(DELETE_TEST_GUEST_GROUPS, order_ids=made["order_ids"])
    run_write(DELETE_TEST_NODES, **{k: v for k, v in made.items() if k != "run"})


@pytest.fixture
def catalog(created):
    repository = food_item_repository()
    run = created["run"]
    julebord = repository.add_event_category(f"Julebord-{run}")
    bryllup = repository.add_event_category(f"Bryllup-{run}")
    fish, milk = Allergen(f"fish-{run}", "Fisk"), Allergen(f"milk-{run}", "Melk")
    vegetarian = DietaryLabel(f"V-{run}", "Vegetar")
    for allergen in (fish, milk):
        repository.add_allergen(allergen)
    repository.add_dietary_label(vegetarian)
    created["category_ids"] += [julebord.id, bryllup.id]
    created["codes"] += [fish.code, milk.code, vegetarian.code]
    return {"julebord": julebord, "bryllup": bryllup, "fish": fish, "milk": milk, "V": vegetarian}


def add_item(created, catalog, name, published=True, **kwargs):
    item = food_item_repository().add(
        FoodItem(
            id=None,
            name=f"{name}-{created['run']}",
            description="Testrett",
            price_nok=Decimal("189.50"),
            min_order_qty=10,
            published=published,
            event_categories=[catalog["julebord"]],
            allergens=[catalog["fish"]],
            **kwargs,
        )
    )
    created["item_ids"].append(item.id)
    return item


def test_add_and_get_food_item_with_relations(created, catalog):
    item = add_item(created, catalog, "Fiskesuppe", dietary_labels=[catalog["V"]], origin="Bergen")

    loaded = food_item_repository().get(item.id)

    assert isinstance(loaded.id, int)
    assert loaded.name == item.name
    assert loaded.price_nok == Decimal("189.50")
    assert loaded.origin == "Bergen"
    assert [c.id for c in loaded.event_categories] == [catalog["julebord"].id]
    assert [a.code for a in loaded.allergens] == [catalog["fish"].code]
    assert [d.code for d in loaded.dietary_labels] == [catalog["V"].code]


def test_list_published_filters_category_and_hides_unpublished_and_archived(created, catalog):
    repository = food_item_repository()
    shown = add_item(created, catalog, "Synlig")
    hidden = add_item(created, catalog, "Upublisert", published=False)
    archived = add_item(created, catalog, "Arkivert")
    repository.archive(archived.id)

    names = [i.name for i in repository.list_published(catalog["julebord"].name)]

    assert names == [shown.name]
    assert hidden.name not in [i.name for i in repository.list_published()]
    assert repository.list_published(catalog["bryllup"].name) == []


def test_update_replaces_relations_and_keeps_archived(created, catalog):
    repository = food_item_repository()
    item = add_item(created, catalog, "Lam")

    repository.update(
        replace(
            item,
            price_nok=Decimal("245"),
            event_categories=[catalog["bryllup"]],
            allergens=[catalog["milk"]],
            dietary_labels=[catalog["V"]],
        )
    )

    loaded = repository.get(item.id)
    assert loaded.price_nok == Decimal("245")
    assert [c.id for c in loaded.event_categories] == [catalog["bryllup"].id]
    assert [a.code for a in loaded.allergens] == [catalog["milk"].code]
    assert loaded.archived is False


def test_publish_archive_restore_image_and_get_by_ids(created, catalog):
    repository = food_item_repository()
    first = add_item(created, catalog, "En", published=False)
    second = add_item(created, catalog, "To")

    repository.set_published(first.id, True)
    assert repository.get(first.id).published is True
    repository.archive(first.id)
    assert (repository.get(first.id).archived, repository.get(first.id).published) == (True, False)
    repository.restore(first.id)
    assert (repository.get(first.id).archived, repository.get(first.id).published) == (False, False)
    repository.set_image(second.id, "uploads/test.png", "Instruks")
    assert (repository.get(second.id).image_path, repository.get(second.id).image_prompt) == (
        "uploads/test.png",
        "Instruks",
    )
    assert {i.id for i in repository.get_by_ids([first.id, second.id, 999999999])} == {first.id, second.id}


def test_category_filter_is_a_parameter_not_cypher(created, catalog):
    add_item(created, catalog, "Rett")
    assert food_item_repository().list_published("' OR 1=1 //") == []
    assert food_item_repository().list_published(") RETURN f //") == []


def test_users_add_get_and_duplicate_email(created):
    repository = user_repository()
    email = f"neo4j-test-{created['run']}@example.test"
    created["emails"].append(email)

    user = repository.add(User.register(email, "Neo Testkunde", "neo4j-test-123"))

    assert isinstance(user.id, int)
    assert repository.get_by_id(user.id).email == email
    assert repository.get_by_email(email.upper()).id == user.id
    assert repository.get_by_email(email).check_password("neo4j-test-123")
    with pytest.raises(DuplicateEmailError):
        repository.add(User.register(email, "Kopi", "neo4j-test-123"))
