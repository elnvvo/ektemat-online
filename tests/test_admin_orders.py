"""Akseptansetester for US-12 (ordreliste), US-13 (ordrestatus) og US-14 (betalingsstatus)."""
import re
from datetime import date
from decimal import Decimal

import pytest

from app.models.errors import InvalidTransitionError, ValidationError
from app.models.order import (
    ORDER_TRANSITIONS,
    PAYMENT_TRANSITIONS,
    Order,
    OrderStatus,
    PaymentStatus,
)
from app.models.repositories import order_repository
from conftest import ADMIN_PASSWORD, CUSTOMER_PASSWORD, login

S = OrderStatus
P = PaymentStatus


def save_order(app, user, event_date, status=S.SUBMITTED, payment=P.NOT_PAID, guests=30, total="5670"):
    with app.app_context():
        return order_repository().save(
            Order(
                id=None,
                user_id=user.id,
                event_date=date.fromisoformat(event_date),
                guest_count=guests,
                delivery_address="Testveien 1",
                status=status,
                payment_status=payment,
                estimated_total_nok=Decimal(total),
            )
        )


def stored(app, order_id):
    with app.app_context():
        return order_repository().get(order_id)


@pytest.fixture
def admin_client(app, admin):
    client = app.test_client()
    login(client, admin.email, ADMIN_PASSWORD)
    return client


@pytest.fixture
def customer_client(app, customer):
    client = app.test_client()
    login(client, customer.email, CUSTOMER_PASSWORD)
    return client


def order_numbers(html):
    return re.findall(r'href="/admin/orders/\d+">(EM-\d{5})</a>', html)


def set_status(client, order, status, reason=None):
    data = {"status": status.value}
    if reason is not None:
        data["reason"] = reason
    return client.post(f"/admin/orders/{order.id}/status", data=data, follow_redirects=True)


# US-12

def test_admin_list_shows_all_orders_sorted_by_event_date(app, admin_client, customer):
    late = save_order(app, customer, "2027-05-01", guests=10, total="2450")
    early = save_order(app, customer, "2027-02-01", status=S.APPROVED, payment=P.DEPOSIT_PAID)

    html = admin_client.get("/admin/orders").get_data(as_text=True)

    assert order_numbers(html) == [early.number, late.number]
    for text in ("Kari Testkunde", customer.email, "01.02.2027", "5 670 kr", "2 450 kr",
                 "Godkjent", "Depositum betalt", "Sendt inn", "Ikke betalt"):
        assert text in html


def test_filter_by_status_submitted(app, admin_client, customer):
    submitted = save_order(app, customer, "2027-02-01")
    save_order(app, customer, "2027-02-02", status=S.APPROVED)
    save_order(app, customer, "2027-02-03", status=S.REJECTED)

    html = admin_client.get("/admin/orders?status=submitted").get_data(as_text=True)

    assert order_numbers(html) == [submitted.number]


def test_filter_by_date_range(app, admin_client, customer):
    save_order(app, customer, "2027-01-31")
    in_range_late = save_order(app, customer, "2027-02-28")
    in_range_early = save_order(app, customer, "2027-02-01")
    save_order(app, customer, "2027-03-01")

    html = admin_client.get("/admin/orders?from=2027-02-01&to=2027-02-28").get_data(as_text=True)

    assert order_numbers(html) == [in_range_early.number, in_range_late.number]


def test_list_all_filters_in_repository(app, customer):
    save_order(app, customer, "2027-02-01")
    save_order(app, customer, "2027-02-10", status=S.APPROVED)
    save_order(app, customer, "2027-03-10", status=S.APPROVED)

    with app.app_context():
        repository = order_repository()
        approved_in_feb = repository.list_all(S.APPROVED, date(2027, 2, 1), date(2027, 2, 28))
        everything = repository.list_all()

    assert [o.event_date.isoformat() for o in approved_in_feb] == ["2027-02-10"]
    assert len(everything) == 3
    assert everything[0].customer.name == "Kari Testkunde"


def test_admin_order_detail_shows_whole_order(app, admin_client, customer):
    order = save_order(app, customer, "2027-02-01")

    html = admin_client.get(f"/admin/orders/{order.id}").get_data(as_text=True)

    assert order.number in html
    assert "Testveien 1" in html
    assert "Kari Testkunde" in html


# US-13

def test_approve_is_visible_to_customer(app, admin_client, customer_client, customer):
    order = save_order(app, customer, "2027-02-01")

    response = set_status(admin_client, order, S.APPROVED)

    assert "Status endret til Godkjent." in response.get_data(as_text=True)
    assert stored(app, order.id).status == S.APPROVED
    assert "Godkjent" in customer_client.get("/orders").get_data(as_text=True)


def test_full_flow_to_delivered(app, admin_client, customer):
    order = save_order(app, customer, "2027-02-01")

    for status in (S.APPROVED, S.IN_PREPARATION, S.DELIVERED):
        set_status(admin_client, order, status)

    assert stored(app, order.id).status == S.DELIVERED


def test_delivered_cannot_go_back_to_submitted(app, admin_client, customer):
    order = save_order(app, customer, "2027-02-01", status=S.DELIVERED)

    response = set_status(admin_client, order, S.SUBMITTED)

    assert "Kan ikke endre status fra Levert til Sendt inn." in response.get_data(as_text=True)
    assert stored(app, order.id).status == S.DELIVERED


# Approved kan bare kanselleres, ikke avvises (design.md §4).
@pytest.mark.parametrize(
    ("start", "target"),
    [(S.SUBMITTED, S.REJECTED), (S.SUBMITTED, S.CANCELLED), (S.APPROVED, S.CANCELLED)],
)
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reject_or_cancel_without_reason_is_refused(app, admin_client, customer, start, target, reason):
    order = save_order(app, customer, "2027-02-01", status=start)

    response = set_status(admin_client, order, target, reason)

    assert "Skriv en begrunnelse" in response.get_data(as_text=True)
    assert stored(app, order.id).status == start


def test_reject_with_reason_is_shown_to_customer(app, admin_client, customer_client, customer):
    order = save_order(app, customer, "2027-02-01")

    set_status(admin_client, order, S.REJECTED, "Kjøkkenet er fullt denne dagen.")

    saved = stored(app, order.id)
    assert saved.status == S.REJECTED
    assert saved.status_reason == "Kjøkkenet er fullt denne dagen."
    html = customer_client.get(f"/orders/{order.id}").get_data(as_text=True)
    assert "Avvist" in html
    assert "Kjøkkenet er fullt denne dagen." in html


def test_only_allowed_transition_buttons_are_shown(app, admin_client, customer):
    submitted = save_order(app, customer, "2027-02-01")
    delivered = save_order(app, customer, "2027-02-02", status=S.DELIVERED, payment=P.PAID)

    html = admin_client.get(f"/admin/orders/{submitted.id}").get_data(as_text=True)
    status_values = re.findall(r'name="status" value="(\w+)"', html)
    assert status_values == ["approved", "rejected", "cancelled"]
    assert "Marker som levert" not in html

    html = admin_client.get(f"/admin/orders/{delivered.id}").get_data(as_text=True)
    assert re.findall(r'name="status" value="(\w+)"', html) == []
    assert re.findall(r'name="payment_status" value="(\w+)"', html) == []
    assert "Ingen flere endringer mulig" in html


def test_order_state_machine_matches_design():
    allowed = {
        S.SUBMITTED: {S.APPROVED, S.REJECTED, S.CANCELLED},
        S.APPROVED: {S.IN_PREPARATION, S.CANCELLED},
        S.IN_PREPARATION: {S.DELIVERED},
        S.DELIVERED: set(),
        S.REJECTED: set(),
        S.CANCELLED: set(),
    }
    assert ORDER_TRANSITIONS == allowed

    for start in S:
        for target in S:
            order = Order(None, 1, date(2027, 1, 1), 10, "Testveien 1", status=start)
            if target in allowed[start]:
                order.change_status(target, reason="Testbegrunnelse")
                assert order.status == target
            else:
                with pytest.raises(InvalidTransitionError):
                    order.change_status(target, reason="Testbegrunnelse")
                assert order.status == start


def test_reason_only_kept_for_rejected_or_cancelled():
    order = Order(None, 1, date(2027, 1, 1), 10, "Testveien 1")
    order.change_status(S.APPROVED, reason="Ikke nødvendig")
    assert order.status_reason is None

    order.change_status(S.CANCELLED, reason="  Kunden avlyste  ")
    assert order.status_reason == "Kunden avlyste"

    with pytest.raises(ValidationError):
        Order(None, 1, date(2027, 1, 1), 10, "x").change_status(S.REJECTED, reason=" ")


# US-14

def test_set_deposit_paid_shown_on_order_page_and_my_orders(app, admin_client, customer_client, customer):
    order = save_order(app, customer, "2027-02-01")

    response = admin_client.post(
        f"/admin/orders/{order.id}/payment", data={"payment_status": "deposit_paid"}, follow_redirects=True
    )

    assert "Betaling endret til Depositum betalt." in response.get_data(as_text=True)
    assert stored(app, order.id).payment_status == P.DEPOSIT_PAID
    assert "Depositum betalt" in customer_client.get(f"/orders/{order.id}").get_data(as_text=True)
    assert "Depositum betalt" in customer_client.get("/orders").get_data(as_text=True)


def test_illegal_payment_change_is_refused(app, admin_client, customer):
    order = save_order(app, customer, "2027-02-01", payment=P.PAID)

    response = admin_client.post(
        f"/admin/orders/{order.id}/payment", data={"payment_status": "not_paid"}, follow_redirects=True
    )

    assert "Kan ikke endre betaling fra Betalt til Ikke betalt." in response.get_data(as_text=True)
    assert stored(app, order.id).payment_status == P.PAID


def test_payment_state_machine():
    allowed = {
        P.NOT_PAID: {P.DEPOSIT_PAID, P.INVOICED, P.PAID},
        P.DEPOSIT_PAID: {P.INVOICED},
        P.INVOICED: {P.PAID},
        P.PAID: set(),
    }
    assert PAYMENT_TRANSITIONS == allowed

    for start in P:
        for target in P:
            order = Order(None, 1, date(2027, 1, 1), 10, "Testveien 1", payment_status=start)
            if target in allowed[start]:
                order.change_payment_status(target)
                assert order.payment_status == target
            else:
                with pytest.raises(InvalidTransitionError):
                    order.change_payment_status(target)
                assert order.payment_status == start


def test_payment_and_order_status_are_independent(app, admin_client, customer):
    order = save_order(app, customer, "2027-02-01", status=S.DELIVERED)

    admin_client.post(f"/admin/orders/{order.id}/payment", data={"payment_status": "invoiced"})

    saved = stored(app, order.id)
    assert saved.status == S.DELIVERED
    assert saved.payment_status == P.INVOICED


def test_unknown_order_gives_404(admin_client):
    assert admin_client.get("/admin/orders/999").status_code == 404
