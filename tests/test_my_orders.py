"""Akseptansetester for US-11 (Mine bestillinger) og NFR-06 (bare egne bestillinger)."""
import re
from datetime import date
from decimal import Decimal

import pytest

from app.models.order import Order, OrderStatus, PaymentStatus
from app.models.repositories import order_repository, user_repository
from app.models.user import User
from conftest import ADMIN_PASSWORD, CUSTOMER_PASSWORD, login


def save_order(app, user, event_date, total="5670", guests=30, **kwargs):
    with app.app_context():
        return order_repository().save(
            Order(
                id=None,
                user_id=user.id,
                event_date=date.fromisoformat(event_date),
                guest_count=guests,
                delivery_address="Testveien 1",
                estimated_total_nok=Decimal(total),
                **kwargs,
            )
        )


@pytest.fixture
def other_customer(app):
    with app.app_context():
        return user_repository().add(
            User.register("ola@example.test", "Ola Testkunde", CUSTOMER_PASSWORD)
        )


@pytest.fixture
def customer_client(client, customer):
    login(client, customer.email, CUSTOMER_PASSWORD)
    return client


def order_rows(html):
    """(nummer, resten av raden) for hver bestilling i tabellen, i visningsrekkefølge."""
    rows = re.findall(r"<tr>\s*<td data-label=\"Bestilling\">(.*?)</tr>", html, re.S)
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)).strip() for row in rows]


def test_my_orders_lists_all_three_sorted_by_event_date(app, customer_client, customer):
    december = save_order(app, customer, "2027-12-10", total="2450", guests=10)
    june = save_order(app, customer, "2027-06-01", total="5670", guests=30)
    march = save_order(app, customer, "2027-03-15", total="10010", guests=40)

    html = customer_client.get("/orders").get_data(as_text=True)

    assert order_rows(html) == [
        f"{march.number} 15.03.2027 40 10 010 kr Sendt inn Ikke betalt",
        f"{june.number} 01.06.2027 30 5 670 kr Sendt inn Ikke betalt",
        f"{december.number} 10.12.2027 10 2 450 kr Sendt inn Ikke betalt",
    ]


def test_status_labels_are_norwegian(app, customer_client, customer):
    save_order(app, customer, "2027-03-15")
    save_order(
        app,
        customer,
        "2027-04-15",
        status=OrderStatus.APPROVED,
        payment_status=PaymentStatus.DEPOSIT_PAID,
    )

    html = customer_client.get("/orders").get_data(as_text=True)

    for label in ("Sendt inn", "Ikke betalt", "Godkjent", "Depositum betalt"):
        assert label in html
    assert "submitted" not in re.sub(r'class="[^"]*"', "", html)


def test_each_order_links_to_detail_page(app, customer_client, customer):
    first = save_order(app, customer, "2027-03-15")
    second = save_order(app, customer, "2027-04-15")

    html = customer_client.get("/orders").get_data(as_text=True)

    for order in (first, second):
        assert f'href="/orders/{order.id}"' in html
        assert customer_client.get(f"/orders/{order.id}").status_code == 200


def test_customer_only_sees_own_orders(app, customer_client, customer, other_customer):
    mine = save_order(app, customer, "2027-03-15")
    theirs = save_order(app, other_customer, "2027-03-16")

    html = customer_client.get("/orders").get_data(as_text=True)

    assert mine.number in html
    assert theirs.number not in html
    assert customer_client.get(f"/orders/{theirs.id}").status_code == 404


def test_list_for_user_only_returns_own_orders(app, customer, other_customer):
    save_order(app, customer, "2027-03-15")
    save_order(app, other_customer, "2027-03-16")
    save_order(app, customer, "2027-01-02")

    with app.app_context():
        orders = order_repository().list_for_user(customer.id)

    assert [o.event_date.isoformat() for o in orders] == ["2027-01-02", "2027-03-15"]
    assert {o.user_id for o in orders} == {customer.id}


def test_no_orders_shows_text_and_menu_link(customer_client):
    html = customer_client.get("/orders").get_data(as_text=True)

    assert "Du har ingen bestillinger ennå." in html
    assert 'href="/menu"' in html


def test_my_orders_requires_login(client):
    response = client.get("/orders")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login?next=/orders"


def test_nav_link_only_for_logged_in_customer(app, client, customer, admin):
    assert "Mine bestillinger" not in client.get("/menu").get_data(as_text=True)

    login(client, customer.email, CUSTOMER_PASSWORD)
    assert "Mine bestillinger" in client.get("/menu").get_data(as_text=True)
    client.post("/logout")

    login(client, admin.email, ADMIN_PASSWORD)
    assert "Mine bestillinger" not in client.get("/menu").get_data(as_text=True)
