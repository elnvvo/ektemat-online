"""Akseptansetester for US-03 (håndtere matretter) og US-04 (publisere og avpublisere)."""
import re
from decimal import Decimal

import pytest

from app.models.errors import ValidationError
from app.models.food_item import Allergen, DietaryLabel, FoodItem
from app.models.repositories import food_item_repository
from app.models.repositories.sqlite_connection import get_db
from conftest import ADMIN_PASSWORD, login


@pytest.fixture
def catalog(app):
    with app.app_context():
        repository = food_item_repository()
        categories = {name: repository.add_event_category(name) for name in ("Julebord", "Bryllup")}
        repository.add_allergen(Allergen("fish", "Fisk"))
        repository.add_allergen(Allergen("milk", "Melk"))
        repository.add_dietary_label(DietaryLabel("V", "Vegetar"))
        return categories


@pytest.fixture
def admin_client(client, admin):
    login(client, admin.email, ADMIN_PASSWORD)
    return client


def add_item(app, catalog, name="Fiskesuppe", published=False):
    with app.app_context():
        return food_item_repository().add(
            FoodItem(
                id=None,
                name=name,
                description="Testrett",
                price_nok=Decimal("189"),
                min_order_qty=10,
                published=published,
                event_categories=[catalog["Julebord"]],
                allergens=[Allergen("fish", "Fisk")],
            )
        )


def menu_names(client):
    """Navnene på kortene på menyen (ikke flash-meldinger e.l.)."""
    return re.findall(r"<h2>(.*?)</h2>", client.get("/menu").get_data(as_text=True))


def get_item(app, item_id):
    with app.app_context():
        return food_item_repository().get(item_id)


def all_items(app):
    with app.app_context():
        return food_item_repository().list_all()


def item_form(catalog, **overrides):
    data = {
        "name": "Lam fra Voss",
        "description": "Langtidsbakt lam",
        "price": "245",
        "min_order_qty": "10",
        "categories": [str(catalog["Bryllup"].id)],
        "allergens": ["milk"],
        "labels": [],
    }
    data.update(overrides)
    return data


# US-03

def test_admin_creates_item_and_it_appears_in_list(app, admin_client, catalog):
    response = admin_client.post("/admin/items/new", data=item_form(catalog))

    assert response.status_code == 302
    [item] = all_items(app)
    assert item.name == "Lam fra Voss"
    assert item.price_nok == Decimal("245")
    assert [c.name for c in item.event_categories] == ["Bryllup"]
    assert [a.code for a in item.allergens] == ["milk"]
    assert item.published is False
    assert "Lam fra Voss" in admin_client.get("/admin/items").get_data(as_text=True)


def test_negative_price_is_rejected(app, admin_client, catalog):
    response = admin_client.post("/admin/items/new", data=item_form(catalog, price="-5"))

    assert response.status_code == 400
    assert "Pris kan ikke være negativ" in response.get_data(as_text=True)
    assert all_items(app) == []


def test_min_order_below_one_is_rejected(app, admin_client, catalog):
    response = admin_client.post("/admin/items/new", data=item_form(catalog, min_order_qty="0"))

    assert response.status_code == 400
    assert "Minimumsantall må være minst 1" in response.get_data(as_text=True)
    assert all_items(app) == []


def test_invalid_edit_is_not_saved(app, admin_client, catalog):
    item = add_item(app, catalog)

    response = admin_client.post(f"/admin/items/{item.id}/edit", data=item_form(catalog, price="-1"))

    assert response.status_code == 400
    assert get_item(app, item.id).price_nok == Decimal("189")


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("price", {"price": "-0.01"}),
        ("price", {"price": "gratis"}),
        ("min_order_qty", {"min_order_qty": "0"}),
        ("name", {"name": "  "}),
        ("event_categories", {"event_categories": []}),
    ],
)
def test_validation_lives_in_model(field, kwargs):
    values = {
        "name": "Fiskesuppe",
        "description": "",
        "price": "189",
        "min_order_qty": "10",
        "event_categories": ["Julebord"],
    }
    values.update(kwargs)

    with pytest.raises(ValidationError) as error:
        FoodItem.from_input(**values)
    assert field in error.value.messages


def test_model_accepts_comma_decimal_price():
    item = FoodItem.from_input("Kake", "", "189,50", "1", event_categories=["Bursdag"])
    assert item.price_nok == Decimal("189.50")


def test_admin_edits_item(app, admin_client, catalog):
    item = add_item(app, catalog)

    response = admin_client.post(
        f"/admin/items/{item.id}/edit",
        data=item_form(catalog, name="Fiskesuppe", price="199", allergens=["fish", "milk"]),
    )

    assert response.status_code == 302
    edited = get_item(app, item.id)
    assert edited.price_nok == Decimal("199")
    assert [c.name for c in edited.event_categories] == ["Bryllup"]
    assert {a.code for a in edited.allergens} == {"fish", "milk"}


def test_admin_list_shows_unpublished_items(app, admin_client, catalog):
    add_item(app, catalog, name="Rakfisk", published=False)

    html = admin_client.get("/admin/items").get_data(as_text=True)

    assert "Rakfisk" in html
    assert "Ikke publisert" in html


def test_remove_archives_item_instead_of_deleting(app, admin_client, catalog, customer):
    item = add_item(app, catalog, published=True)
    with app.app_context():
        # OrderRepository finnes ikke ennå (US-08), så ordren lages direkte her.
        db = get_db()
        order_id = db.execute(
            "INSERT INTO orders (user_id, event_date, guest_count, delivery_address)"
            " VALUES (?, '2027-01-15', 30, 'Testveien 1')",
            (customer.id,),
        ).lastrowid
        db.execute(
            "INSERT INTO order_lines (order_id, food_item_id, quantity, unit_price_nok)"
            " VALUES (?, ?, 30, 189)",
            (order_id, item.id),
        )
        db.commit()

    response = admin_client.post(f"/admin/items/{item.id}/archive")

    assert response.status_code == 302
    archived = get_item(app, item.id)
    assert archived is not None
    assert archived.archived is True
    assert archived.published is False
    with app.app_context():
        row = get_db().execute(
            "SELECT f.name FROM order_lines ol JOIN food_items f ON f.id = ol.food_item_id"
            " WHERE ol.order_id = ?",
            (order_id,),
        ).fetchone()
    assert row["name"] == "Fiskesuppe"
    assert "Fiskesuppe" not in menu_names(admin_client)


def test_archived_item_cannot_be_published_until_restored(app, admin_client, catalog):
    item = add_item(app, catalog, published=True)
    admin_client.post(f"/admin/items/{item.id}/archive")

    admin_client.post(f"/admin/items/{item.id}/publish", data={"published": "1"})
    assert get_item(app, item.id).published is False

    admin_client.post(f"/admin/items/{item.id}/restore")
    restored = get_item(app, item.id)
    assert restored.archived is False
    assert restored.published is False


def test_unknown_item_gives_404(admin_client, catalog):
    assert admin_client.get("/admin/items/999/edit").status_code == 404


# US-04

def test_publish_makes_item_visible_on_menu(app, admin_client, catalog):
    item = add_item(app, catalog, name="Rakfisk", published=False)
    assert "Rakfisk" not in menu_names(admin_client)

    response = admin_client.post(f"/admin/items/{item.id}/publish", data={"published": "1"})

    assert response.status_code == 302
    assert "Rakfisk" in menu_names(admin_client)


def test_unpublish_hides_item_from_menu(app, admin_client, catalog):
    item = add_item(app, catalog, name="Rakfisk", published=True)

    admin_client.post(f"/admin/items/{item.id}/publish", data={"published": "0"})

    assert get_item(app, item.id).published is False
    assert "Rakfisk" not in menu_names(admin_client)
