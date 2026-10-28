"""Akseptansetester for US-08 (sende bestilling), US-09 (gjestegrupper) og US-10 (bekreftelse)."""
import re
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.cart import Cart
from app.models.errors import ValidationError
from app.models.food_item import Allergen, DietaryLabel, FoodItem
from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.repositories import food_item_repository, order_repository, user_repository
from app.models.repositories.sqlite_connection import get_db
from app.models.user import User
from conftest import CUSTOMER_PASSWORD, login

TOMORROW = (date.today() + timedelta(days=1)).isoformat()
NEXT_MONTH = (date.today() + timedelta(days=30)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def items(app):
    with app.app_context():
        repository = food_item_repository()
        category = repository.add_event_category("Julebord")
        for code, name in (("fish", "Fisk"), ("nuts", "Nøtter"), ("milk", "Melk")):
            repository.add_allergen(Allergen(code, name))
        for code, name in (("V", "Vegetar"), ("VG", "Vegan")):
            repository.add_dietary_label(DietaryLabel(code, name))
        soup = FoodItem(None, "Fiskesuppe", "", Decimal("189"), 10, published=True, event_categories=[category])
        lamb = FoodItem(None, "Lam fra Voss", "", Decimal("245"), 10, published=True, event_categories=[category])
        return {"Fiskesuppe": repository.add(soup), "Lam fra Voss": repository.add(lamb)}


@pytest.fixture
def shopper(client, customer, items):
    """Innlogget kunde med 30 fiskesupper i handlekurven."""
    login(client, customer.email, CUSTOMER_PASSWORD)
    client.post("/cart/add", data={"item_id": items["Fiskesuppe"].id, "quantity": "30"})
    return client


def order_form(**overrides):
    data = {
        "action": "submit",
        "event_date": NEXT_MONTH,
        "guest_count": "40",
        "delivery_address": "Testveien 1, 5003 Bergen",
        "group_count": "2",
        "group-1-size": "4",
        "group-1-labels": ["VG"],
        "group-1-notes": "",
        "group-2-size": "2",
        "group-2-allergens": ["nuts"],
        "group-2-notes": "Alvorlig allergi",
    }
    data.update(overrides)
    return data


def submit(client, **overrides):
    return client.post("/order", data=order_form(**overrides))


def order_id_from(response):
    return int(re.search(r"/orders/(\d+)", response.headers["Location"]).group(1))


def get_order(app, order_id, user_id):
    with app.app_context():
        return order_repository().get_for_user(order_id, user_id)


def order_count(app):
    with app.app_context():
        return get_db().execute("SELECT COUNT(*) FROM orders").fetchone()[0]


def session_cart(client):
    with client.session_transaction() as session:
        return session.get("cart", {})


# US-08

def test_submit_creates_order_with_status_submitted(app, shopper, customer):
    response = submit(shopper)

    assert response.status_code == 303
    order = get_order(app, order_id_from(response), customer.id)
    assert order.status == OrderStatus.SUBMITTED
    assert order.payment_status == PaymentStatus.NOT_PAID
    assert order.event_date.isoformat() == NEXT_MONTH
    assert order.guest_count == 40
    html = shopper.get(response.headers["Location"]).get_data(as_text=True)
    assert order.number in html
    assert "Sendt inn" in html


def test_cart_is_emptied_after_order(shopper):
    submit(shopper)
    assert session_cart(shopper) == {}
    assert "Handlekurv (0)" in shopper.get("/menu").get_data(as_text=True)


def test_past_event_date_is_rejected(app, shopper):
    response = submit(shopper, event_date=YESTERDAY)

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Arrangementsdatoen må være i fremtiden." in html
    assert "Testveien 1, 5003 Bergen" in html  # det kunden skrev, beholdes
    assert 'value="40"' in html
    assert order_count(app) == 0
    assert session_cart(shopper) != {}


def test_guest_count_must_be_at_least_one(app, shopper):
    response = submit(shopper, guest_count="0", group_count="0")

    assert response.status_code == 400
    assert "Antall gjester må være minst 1." in response.get_data(as_text=True)
    assert order_count(app) == 0


def test_not_logged_in_is_sent_to_login_and_cart_kept(client, customer, items):
    client.post("/cart/add", data={"item_id": items["Fiskesuppe"].id, "quantity": "30"})

    response = client.get("/order")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login?next=/order"
    assert client.post("/order", data=order_form()).status_code == 302  # POST også

    login(client, customer.email, CUSTOMER_PASSWORD, next="/order")
    assert session_cart(client) == {str(items["Fiskesuppe"].id): 30}
    assert client.get("/order").status_code == 200
    assert submit(client).status_code == 303


def test_empty_cart_redirects_to_cart(client, customer, items):
    login(client, customer.email, CUSTOMER_PASSWORD)
    response = client.get("/order")
    assert response.status_code == 302
    assert response.headers["Location"] == "/cart"


def test_order_line_copies_price(app, shopper, customer, items):
    order_id = order_id_from(submit(shopper))

    with app.app_context():
        food_item_repository().update(replace(items["Fiskesuppe"], price_nok=Decimal("250")))

    order = get_order(app, order_id, customer.id)
    assert order.lines[0].unit_price_nok == Decimal("189")
    assert order.estimated_total_nok == Decimal("5670")
    html = shopper.get(f"/orders/{order_id}").get_data(as_text=True)
    assert "189 kr" in html
    assert "250 kr" not in html


# US-08 – validering i modellen (design.md §3)

def make_cart(quantity=30, min_qty=10):
    cart = Cart()
    cart.add(FoodItem(1, "Fiskesuppe", "", Decimal("189"), 1, published=True), quantity)
    cart.lines[0].food_item.min_order_qty = min_qty  # admin har endret minimum etter at den ble lagt i kurven
    return cart


def create(cart=None, **overrides):
    values = {
        "user": User(id=7, email="k@example.test", name="K", phone=None, password_hash="x"),
        "cart": cart or make_cart(),
        "event_date": "2027-01-15",
        "guest_count": "40",
        "delivery_address": "Testveien 1",
        "guest_groups": [],
        "today": date(2027, 1, 1),
    }
    values.update(overrides)
    return Order.create_from_cart(**values)


def test_create_from_cart_sets_status_and_copies_prices():
    order = create()
    assert order.status == OrderStatus.SUBMITTED
    assert order.payment_status == PaymentStatus.NOT_PAID
    assert order.user_id == 7
    assert order.lines[0].unit_price_nok == Decimal("189")
    assert order.estimated_total_nok == Decimal("5670")


@pytest.mark.parametrize(
    ("field", "overrides"),
    [
        ("event_date", {"event_date": "2027-01-01"}),  # i dag
        ("event_date", {"event_date": "2026-12-31"}),  # i går
        ("event_date", {"event_date": "ikke-en-dato"}),
        ("guest_count", {"guest_count": "0"}),
        ("guest_count", {"guest_count": ""}),
        ("delivery_address", {"delivery_address": "  "}),
        ("cart", {"cart": Cart()}),
        ("cart", {"cart": make_cart(quantity=30, min_qty=40)}),
    ],
)
def test_create_from_cart_validation(field, overrides):
    with pytest.raises(ValidationError) as error:
        create(**overrides)
    assert field in error.value.messages


# US-09

def test_guest_groups_are_saved_and_shown(app, shopper, customer):
    order_id = order_id_from(submit(shopper))

    order = get_order(app, order_id, customer.id)
    assert [(g.size, [d.code for d in g.dietary_labels], [a.code for a in g.allergens]) for g in order.guest_groups] == [
        (4, ["VG"], []),
        (2, [], ["nuts"]),
    ]
    html = re.sub(r"\s+", " ", shopper.get(f"/orders/{order_id}").get_data(as_text=True))
    assert "4 gjester:</strong> Vegan" in html
    assert "2 gjester:</strong> Nøtter" in html
    assert "Alvorlig allergi" in html


def test_guest_group_needs_allergen_or_diet(app, shopper):
    response = submit(shopper, **{"group-1-labels": []})

    assert response.status_code == 400
    assert "Gjestegruppe 1: velg minst ett allergen eller diettmerke." in response.get_data(as_text=True)
    assert order_count(app) == 0


def test_guest_group_size_must_be_at_least_one(app, shopper):
    response = submit(shopper, **{"group-1-size": "0"})

    assert response.status_code == 400
    assert "Gjestegruppe 1: antall må være minst 1." in response.get_data(as_text=True)


def test_guest_groups_larger_than_guest_count_are_rejected(app, shopper):
    response = submit(shopper, guest_count="5")

    assert response.status_code == 400
    assert "Gjestegruppene har til sammen 6 gjester, men bestillingen har bare 5." in response.get_data(as_text=True)
    assert order_count(app) == 0


def test_blank_guest_group_is_ignored(app, shopper, customer):
    response = submit(shopper, group_count="3", **{"group-3-size": "", "group-3-notes": ""})

    assert response.status_code == 303
    assert len(get_order(app, order_id_from(response), customer.id).guest_groups) == 2


def test_add_and_remove_group_buttons_do_not_save(app, shopper):
    added = submit(shopper, action="add_group")
    assert added.status_code == 200
    html = added.get_data(as_text=True)
    assert "Gjestegruppe 3" in html
    assert "Testveien 1, 5003 Bergen" in html

    removed = submit(shopper, action="remove_group-1")
    html = removed.get_data(as_text=True)
    assert "Gjestegruppe 2" not in html
    assert 'name="group-1-allergens" value="nuts" checked' in html  # gruppe 2 er nå gruppe 1
    assert order_count(app) == 0


def test_form_never_asks_for_guest_names(app, shopper):
    html = shopper.get("/order").get_data(as_text=True)
    form = re.search(r'<form class="form order-form".*?</form>', html, re.S).group(0)
    field_names = re.findall(r'name="([^"]+)"', form)
    assert field_names
    assert not [n for n in field_names if "name" in n.lower() or "navn" in n.lower()]

    with app.app_context():
        columns = [row["name"] for row in get_db().execute("PRAGMA table_info(guest_groups)")]
    assert columns == ["id", "order_id", "size", "notes"]


# US-10

def test_confirmation_shows_order_details(shopper):
    response = submit(shopper)
    html = shopper.get(response.headers["Location"]).get_data(as_text=True)

    order_number = re.search(r"EM-\d{5}", html).group(0)
    assert f"Bestilling {order_number}" in html
    assert "Takk! Bestillingen er mottatt." in html
    event_date = date.fromisoformat(NEXT_MONTH).strftime("%d.%m.%Y")
    assert event_date in html
    assert "<dd>40</dd>" in html
    assert "Fiskesuppe" in html
    assert "5 670 kr" in html
    assert "Sendt inn" in html
    assert "Ikke betalt" in html


# NFR-06

def test_customer_cannot_see_other_customers_order(app, shopper):
    order_id = order_id_from(submit(shopper))

    with app.app_context():
        other = user_repository().add(User.register("ola@example.test", "Ola Testkunde", CUSTOMER_PASSWORD))
    other_client = app.test_client()
    login(other_client, other.email, CUSTOMER_PASSWORD)

    response = other_client.get(f"/orders/{order_id}")
    assert response.status_code == 404
    assert "Testveien" not in response.get_data(as_text=True)


def test_order_page_requires_login(app, shopper):
    order_id = order_id_from(submit(shopper))

    response = app.test_client().get(f"/orders/{order_id}")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")
