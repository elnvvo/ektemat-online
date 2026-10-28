"""Akseptansetester for US-06 (handlekurv med estimert total) og US-07 (minimumsantall)."""
import re
from dataclasses import replace
from decimal import Decimal

import pytest

from app.models.cart import Cart
from app.models.errors import ValidationError
from app.models.food_item import FoodItem
from app.models.repositories import food_item_repository
from conftest import CUSTOMER_PASSWORD, login


def make_item(item_id, name, price, min_qty, published=True):
    return FoodItem(
        id=item_id,
        name=name,
        description="",
        price_nok=Decimal(price),
        min_order_qty=min_qty,
        published=published,
    )


@pytest.fixture
def items(app):
    """Fiskesuppe (189 kr, min. 10), Lam fra Voss (245 kr, min. 10) og en upublisert rett."""
    with app.app_context():
        repository = food_item_repository()
        category = repository.add_event_category("Julebord")
        added = {}
        for name, price, published in (
            ("Fiskesuppe", "189", True),
            ("Lam fra Voss", "245", True),
            ("Rakfisk", "210", False),
        ):
            item = make_item(None, name, price, 10, published)
            item.event_categories = [category]
            added[name] = repository.add(item)
        return added


def add(client, item, quantity):
    return client.post("/cart/add", data={"item_id": item.id, "quantity": quantity, "next": "/menu"})


def cart_html(client):
    return client.get("/cart").get_data(as_text=True)


def session_cart(client):
    with client.session_transaction() as session:
        return session.get("cart", {})


def total(html):
    return re.search(r'class="num total"[^>]*>(.*?)</td>', html).group(1)


# US-06 – modellen

def test_cart_total_30_fish_soup_is_5670():
    cart = Cart()
    cart.add(make_item(1, "Fiskesuppe", "189", 10), 30)
    assert cart.estimated_total_nok == Decimal("5670")


def test_cart_change_and_remove_update_total():
    soup, lamb = make_item(1, "Fiskesuppe", "189", 10), make_item(2, "Lam fra Voss", "245", 10)
    cart = Cart()
    cart.add(soup, 30)
    cart.add(lamb, 10)
    assert cart.estimated_total_nok == Decimal("8120")

    cart.set_quantity(1, 40)
    assert cart.estimated_total_nok == Decimal("10010")

    cart.remove(2)
    assert cart.estimated_total_nok == Decimal("7560")
    assert cart.line_count == 1


# US-06 – gjennom nettsiden (uten innlogging)

def test_add_to_cart_shows_estimated_total(client, items):
    response = add(client, items["Fiskesuppe"], "30")

    assert response.status_code == 302
    html = cart_html(client)
    assert "Fiskesuppe" in html
    assert "189 kr" in html
    assert total(html) == "5 670 kr"


def test_change_quantity_updates_total(client, items):
    add(client, items["Fiskesuppe"], "30")

    client.post("/cart/update", data={"item_id": items["Fiskesuppe"].id, "quantity": "40"})

    assert total(cart_html(client)) == "7 560 kr"


def test_remove_line_updates_total(client, items):
    add(client, items["Fiskesuppe"], "30")
    add(client, items["Lam fra Voss"], "10")
    assert total(cart_html(client)) == "8 120 kr"

    client.post("/cart/remove", data={"item_id": items["Fiskesuppe"].id})

    html = cart_html(client)
    assert total(html) == "2 450 kr"
    assert "Fiskesuppe" not in html


def test_cart_works_without_login(client, items):
    assert client.get("/cart").status_code == 200
    assert add(client, items["Fiskesuppe"], "10").status_code == 302
    assert "Lam fra Voss" not in cart_html(client)
    assert session_cart(client) == {str(items["Fiskesuppe"].id): 10}


def test_session_stores_only_ids_and_quantities(client, items):
    add(client, items["Fiskesuppe"], "30")
    assert session_cart(client) == {str(items["Fiskesuppe"].id): 30}


def test_price_comes_from_repository(app, client, items):
    add(client, items["Fiskesuppe"], "30")
    with app.app_context():
        food_item_repository().update(replace(items["Fiskesuppe"], price_nok=Decimal("200")))

    assert total(cart_html(client)) == "6 000 kr"


def test_nav_shows_cart_line_count(client, items):
    assert "Handlekurv (0)" in client.get("/menu").get_data(as_text=True)
    add(client, items["Fiskesuppe"], "30")
    add(client, items["Lam fra Voss"], "10")
    assert "Handlekurv (2)" in client.get("/menu").get_data(as_text=True)


def test_menu_card_has_add_form_prefilled_with_minimum(client, items):
    html = client.get("/menu").get_data(as_text=True)
    assert "Legg i handlekurv" in html
    assert f'id="qty-{items["Fiskesuppe"].id}"' in html
    assert 'value="10"' in html


def test_unavailable_item_is_dropped_from_cart(app, client, items):
    add(client, items["Fiskesuppe"], "30")
    with app.app_context():
        food_item_repository().archive(items["Fiskesuppe"].id)

    html = cart_html(client)
    assert "ikke lenger tilgjengelig" in html
    assert "Handlekurven er tom" in html


# US-07

def test_quantity_below_minimum_is_rejected(client, items):
    response = add(client, items["Fiskesuppe"], "8")

    assert response.status_code == 302
    html = client.get("/menu").get_data(as_text=True)
    assert "Minimum for Fiskesuppe er 10 stk." in html
    assert session_cart(client) == {}


def test_minimum_quantity_is_accepted(client, items):
    add(client, items["Fiskesuppe"], "10")
    assert session_cart(client) == {str(items["Fiskesuppe"].id): 10}


def test_update_below_minimum_keeps_cart_unchanged(client, items):
    add(client, items["Fiskesuppe"], "30")

    client.post("/cart/update", data={"item_id": items["Fiskesuppe"].id, "quantity": "8"})

    html = cart_html(client)
    assert "Minimum for Fiskesuppe er 10 stk." in html
    assert session_cart(client) == {str(items["Fiskesuppe"].id): 30}
    assert total(html) == "5 670 kr"


@pytest.mark.parametrize("quantity", ["8", "0", "-5", "ti", ""])
def test_cart_validation_lives_in_model(quantity):
    soup = make_item(1, "Fiskesuppe", "189", 10)
    cart = Cart()

    with pytest.raises(ValidationError):
        cart.add(soup, quantity)
    assert cart.is_empty

    cart.add(soup, 30)
    with pytest.raises(ValidationError):
        cart.set_quantity(1, quantity)
    assert cart.quantity_of(1) == 30


def test_minimum_error_message_names_the_minimum():
    cart = Cart()
    with pytest.raises(ValidationError) as error:
        cart.add(make_item(1, "Fiskesuppe", "189", 10), 8)
    assert error.value.messages["quantity"] == "Minimum for Fiskesuppe er 10 stk."


def test_unpublished_item_cannot_be_added(client, items):
    add(client, items["Rakfisk"], "10")

    assert "Rakfisk er ikke tilgjengelig" in client.get("/menu").get_data(as_text=True)
    assert session_cart(client) == {}


def test_cart_is_kept_after_login(client, items, customer):
    add(client, items["Fiskesuppe"], "30")
    login(client, customer.email, CUSTOMER_PASSWORD)

    assert session_cart(client) == {str(items["Fiskesuppe"].id): 30}
