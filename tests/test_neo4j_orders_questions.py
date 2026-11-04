"""Neo4jOrderRepository og Neo4jQuestionRepository mot den ekte databasen fra .env (Oblig 5).

Kjøres bare med «pytest -m neo4j». Gjenbruker fixturene fra test_neo4j_repositories, som lager
alt med unike navn for kjøringen og sletter akkurat det etterpå – databasen tømmes aldri.
"""
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.errors import AlreadyAnsweredError
from app.models.food_item import FoodItem
from app.models.order import GuestGroup, Order, OrderLine, OrderStatus, PaymentStatus
from app.models.question import Question
from app.models.repositories import (
    food_item_repository,
    order_repository,
    question_repository,
    user_repository,
)
from app.models.repositories.neo4j_connection import run_read
from app.models.user import User
from test_neo4j_repositories import catalog, created, neo4j_app  # noqa: F401 (fixturer)

pytestmark = pytest.mark.neo4j


@pytest.fixture
def customer(created):
    return _user(created, "kunde")


@pytest.fixture
def admin(created):
    email = f"neo4j-test-admin-{created['run']}@example.test"
    created["emails"].append(email)
    return user_repository().add(User.create_admin(email, "Neo Admin", "neo4j-test-123"))


@pytest.fixture
def dishes(created, catalog):
    repository = food_item_repository()
    made = []
    for name, price in (("Lam", "245"), ("Fiskesuppe", "189.50")):
        item = repository.add(
            FoodItem(None, f"{name}-{created['run']}", "", Decimal(price), 10, published=True,
                     event_categories=[catalog["julebord"]])
        )
        created["item_ids"].append(item.id)
        made.append(item)
    return made


def _user(created, label):
    email = f"neo4j-test-{label}-{created['run']}@example.test"
    created["emails"].append(email)
    return user_repository().add(User.register(email, f"Neo {label}", "neo4j-test-123"))


def make_order(created, user, dishes, catalog, event_date="2027-03-15", status=OrderStatus.SUBMITTED):
    lines = [OrderLine(d.id, d.name, 30 - i * 10, d.price_nok) for i, d in enumerate(dishes)]
    order = Order(
        id=None,
        user_id=user.id,
        event_date=date.fromisoformat(event_date),
        guest_count=40,
        delivery_address="Testveien 1\n5003 Bergen",
        status=status,
        estimated_total_nok=sum((line.line_total_nok for line in lines), Decimal("0")),
        lines=lines,
        guest_groups=[
            GuestGroup(size=4, dietary_labels=[catalog["V"]], notes="Første gruppe"),
            GuestGroup(size=2, allergens=[catalog["fish"], catalog["milk"]]),
        ],
    )
    saved = order_repository().save(order)
    created["order_ids"].append(saved.id)
    return saved


# Bestillinger

def test_save_and_get_order_with_lines_and_guest_groups(created, customer, dishes, catalog):
    saved = make_order(created, customer, dishes, catalog)

    order = order_repository().get_for_user(saved.id, customer.id)

    assert isinstance(order.id, int) and order.created_at is not None
    assert (order.status, order.payment_status) == (OrderStatus.SUBMITTED, PaymentStatus.NOT_PAID)
    assert order.event_date == date(2027, 3, 15)
    assert order.delivery_address == "Testveien 1\n5003 Bergen"
    assert order.estimated_total_nok == Decimal("11140")  # 30 × 245 + 20 × 189,50
    assert [(line.food_item_name, line.quantity, line.unit_price_nok) for line in order.lines] == [
        (dishes[1].name, 20, Decimal("189.50")),  # sortert etter navn: Fiskesuppe før Lam
        (dishes[0].name, 30, Decimal("245")),
    ]
    assert [(g.size, [a.code for a in g.allergens], [d.code for d in g.dietary_labels], g.notes)
            for g in order.guest_groups] == [
        (4, [], [catalog["V"].code], "Første gruppe"),
        (2, [catalog["fish"].code, catalog["milk"].code], [], ""),
    ]


def test_order_graph_has_relations_and_no_guest_names(created, customer, dishes, catalog):
    saved = make_order(created, customer, dishes, catalog)

    record = run_read(
        "MATCH (u:User)-[:PLACED]->(o:Order {id: $id})"
        " RETURN u.id AS user_id,"
        " [(o)-[c:CONTAINS]->(f:FoodItem) | c.unit_price_nok] AS prices,"
        " [(o)-[:HAS_GUEST_GROUP]->(g:GuestGroup) | keys(g)] AS group_keys,"
        " [(o)-[:HAS_GUEST_GROUP]->(:GuestGroup)-[:AVOIDS]->(a:Allergen) | a.code] AS avoids",
        id=saved.id,
    )[0]

    assert record["user_id"] == customer.id
    assert sorted(record["prices"]) == ["189.50", "245"]
    assert all(set(keys) <= {"position", "size", "notes"} for keys in record["group_keys"])
    assert sorted(record["avoids"]) == sorted([catalog["fish"].code, catalog["milk"].code])


def test_price_change_does_not_change_order_line(created, customer, dishes, catalog):
    saved = make_order(created, customer, dishes, catalog)
    food_item_repository().update(replace(dishes[0], price_nok=Decimal("999")))

    lamb = next(line for line in order_repository().get(saved.id).lines if line.food_item_id == dishes[0].id)
    assert lamb.unit_price_nok == Decimal("245")


def test_other_customer_cannot_get_order(created, customer, dishes, catalog):
    saved = make_order(created, customer, dishes, catalog)
    other = _user(created, "annen")

    assert order_repository().get_for_user(saved.id, other.id) is None
    assert order_repository().list_for_user(other.id) == []


def test_list_for_user_sorted_and_list_all_filters(created, customer, dishes, catalog):
    late = make_order(created, customer, dishes, catalog, "2031-06-01")
    early = make_order(created, customer, dishes, catalog, "2031-02-01", status=OrderStatus.APPROVED)

    assert [o.id for o in order_repository().list_for_user(customer.id)] == [early.id, late.id]

    approved = order_repository().list_all(OrderStatus.APPROVED, date(2031, 1, 1), date(2031, 12, 31))
    mine = [o for o in approved if o.id in (early.id, late.id)]
    assert [o.id for o in mine] == [early.id]
    assert mine[0].customer.email == customer.email
    in_period = order_repository().list_all(None, date(2031, 5, 1), date(2031, 6, 1))
    assert late.id in [o.id for o in in_period] and early.id not in [o.id for o in in_period]


def test_update_status_saves_status_reason_and_payment(created, customer, dishes, catalog):
    saved = make_order(created, customer, dishes, catalog)
    order = order_repository().get(saved.id)

    order.change_status(OrderStatus.CANCELLED, reason="Kunden avlyste")
    order.change_payment_status(PaymentStatus.INVOICED)
    order_repository().update_status(order)

    stored = order_repository().get(saved.id)
    assert (stored.status, stored.status_reason, stored.payment_status) == (
        OrderStatus.CANCELLED,
        "Kunden avlyste",
        PaymentStatus.INVOICED,
    )


def test_order_is_saved_in_one_transaction(created, customer, dishes, catalog):
    broken = Order(
        id=None,
        user_id=customer.id,
        event_date=date(2027, 3, 15),
        guest_count=10,
        delivery_address="Testveien 1",
        lines=[OrderLine(dishes[0].id, dishes[0].name, 10, dishes[0].price_nok),
               OrderLine(999_999_999, "Finnes ikke", 10, Decimal("100"))],
        guest_groups=[GuestGroup(size=2, dietary_labels=[catalog["V"]])],
    )

    with pytest.raises(LookupError):
        order_repository().save(broken)

    leftovers = run_read(
        "MATCH (u:User {id: $id}) OPTIONAL MATCH (u)-[:PLACED]->(o:Order)"
        " OPTIONAL MATCH (o)-[:HAS_GUEST_GROUP]->(g) RETURN count(o) AS orders, count(g) AS groups",
        id=customer.id,
    )[0]
    assert (leftovers["orders"], leftovers["groups"]) == (0, 0)


# Spørsmål og svar

def ask(created, order, user, text, asked_at):
    question = question_repository().add(Question.ask(order, user, text, now=asked_at))
    created["question_ids"].append(question.id)
    return question


def test_questions_unanswered_oldest_first_and_answer_once(created, customer, admin, dishes, catalog):
    order = make_order(created, customer, dishes, catalog)
    repository = question_repository()
    before = repository.count_unanswered()
    newest = ask(created, order, customer, "Nyeste", datetime(2020, 1, 7, 12, 0))
    oldest = ask(created, order, customer, "Eldste", datetime(2020, 1, 5, 9, 0))

    assert [q.text for q in repository.list_for_order(order.id)] == ["Eldste", "Nyeste"]
    mine = [q for q in repository.list_unanswered() if q.id in (newest.id, oldest.id)]
    assert [q.id for q in mine] == [oldest.id, newest.id]
    assert mine[0].customer.email == customer.email
    assert repository.count_unanswered() == before + 2

    question = repository.get(oldest.id)
    question.answer_with(admin, "Svar fra Neo4j", now=datetime(2020, 1, 6, 10, 0))
    repository.save_answer(question)

    stored = repository.get(oldest.id)
    assert stored.is_answered and stored.answer.text == "Svar fra Neo4j"
    assert stored.answer.user_id == admin.id
    assert stored.answer.answered_at == datetime(2020, 1, 6, 10, 0)
    assert repository.count_unanswered() == before + 1
    assert oldest.id in [q.id for q in repository.list_answered(limit=500)]
    assert oldest.id not in [q.id for q in repository.list_unanswered()]

    stale = repository.get(oldest.id)
    stale.answer = None  # som om to admins hadde siden åpen samtidig
    stale.answer_with(admin, "Andre svar")
    with pytest.raises(AlreadyAnsweredError):
        repository.save_answer(stale)
    assert repository.get(oldest.id).answer.text == "Svar fra Neo4j"


def test_question_graph_relations(created, customer, admin, dishes, catalog):
    order = make_order(created, customer, dishes, catalog)
    question = ask(created, order, customer, "Hei", datetime(2020, 1, 5, 9, 0))
    stored = question_repository().get(question.id)
    stored.answer_with(admin, "Hei selv")
    question_repository().save_answer(stored)

    record = run_read(
        "MATCH (u:User)-[:ASKED]->(q:Question {id: $id})-[:ABOUT]->(o:Order),"
        " (w:User)-[:WROTE]->(a:Answer)-[:ANSWERS]->(q)"
        " RETURN u.id AS asker, o.id AS order_id, w.id AS writer",
        id=question.id,
    )[0]
    assert (record["asker"], record["order_id"], record["writer"]) == (customer.id, order.id, admin.id)
