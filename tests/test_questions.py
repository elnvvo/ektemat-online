"""Akseptansetester for US-16 (spørre om en bestilling), US-17 (svare) og US-18 (antall ubesvarte)."""
import re
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.models.errors import AlreadyAnsweredError, ValidationError
from app.models.order import Order
from app.models.question import Question
from app.models.repositories import order_repository, question_repository, user_repository
from app.models.user import User
from conftest import ADMIN_PASSWORD, CUSTOMER_PASSWORD, login


@pytest.fixture
def order(app, customer):
    with app.app_context():
        return order_repository().save(
            Order(None, customer.id, date(2027, 3, 15), 30, "Testveien 1", estimated_total_nok=Decimal("5670"))
        )


@pytest.fixture
def customer_client(app, customer):
    client = app.test_client()
    login(client, customer.email, CUSTOMER_PASSWORD)
    return client


@pytest.fixture
def admin_client(app, admin):
    client = app.test_client()
    login(client, admin.email, ADMIN_PASSWORD)
    return client


def ask(client, order, text):
    return client.post(f"/orders/{order.id}/questions", data={"text": text}, follow_redirects=True)


def add_question(app, order, customer, text, asked_at):
    with app.app_context():
        return question_repository().add(Question.ask(order, customer, text, now=asked_at))


def questions_for(app, order):
    with app.app_context():
        return question_repository().list_for_order(order.id)


def answer(client, question, text, next_url=None):
    data = {"text": text}
    if next_url:
        data["next"] = next_url
    return client.post(f"/admin/questions/{question.id}/answer", data=data, follow_redirects=True)


def section(html, heading):
    """HTML-en fra en <h2> til neste <h2> (eller slutten av <main>)."""
    match = re.search(rf"<h2[^>]*>{heading}.*?</h2>(.*?)(?=<h2|</main>)", html, re.S)
    return match.group(1) if match else ""


# US-16

def test_customer_asks_question_shown_with_time_and_unanswered(app, customer_client, order):
    response = ask(customer_client, order, "Hva er avbestillingsvilkårene?")

    html = response.get_data(as_text=True)
    assert "Spørsmålet er sendt." in html
    assert "Hva er avbestillingsvilkårene?" in html
    assert "Ubesvart" in html
    [question] = questions_for(app, order)
    assert question.asked_at.strftime("%d.%m.%Y kl. %H:%M") in html


def test_answer_is_shown_under_question_and_marked_answered(app, customer_client, admin_client, order, customer):
    question = add_question(app, order, customer, "Kan dere levere kl. 11?", datetime(2027, 1, 5, 9, 0))

    answer(admin_client, question, "Ja, vi leverer kl. 11.")

    html = customer_client.get(f"/orders/{order.id}").get_data(as_text=True)
    item = re.search(rf'id="question-{question.id}">(.*?)</li>', html, re.S).group(1)
    assert "Besvart" in item
    assert "Kan dere levere kl. 11?" in item
    assert "Svar fra Ekte Mat" in item
    assert item.index("Kan dere levere kl. 11?") < item.index("Ja, vi leverer kl. 11.")


def test_customer_can_ask_new_question_after_answer(app, customer_client, admin_client, order, customer):
    first = add_question(app, order, customer, "Første spørsmål", datetime(2026, 1, 5, 9, 0))  # før «nå»
    answer(admin_client, first, "Første svar")

    ask(customer_client, order, "Andre spørsmål")

    assert [(q.text, q.is_answered) for q in questions_for(app, order)] == [
        ("Første spørsmål", True),
        ("Andre spørsmål", False),
    ]


@pytest.mark.parametrize("text", ["", "   \n  "])
def test_empty_question_is_rejected(app, customer_client, order, text):
    response = ask(customer_client, order, text)

    assert "Skriv et spørsmål." in response.get_data(as_text=True)
    assert questions_for(app, order) == []


def test_cannot_ask_about_other_customers_order(app, order):
    with app.app_context():
        other = user_repository().add(User.register("ola@example.test", "Ola Testkunde", CUSTOMER_PASSWORD))
    client = app.test_client()
    login(client, other.email, CUSTOMER_PASSWORD)

    response = client.post(f"/orders/{order.id}/questions", data={"text": "Hei"})

    assert response.status_code == 404
    assert questions_for(app, order) == []


def test_ask_requires_login(app, order):
    response = app.test_client().post(f"/orders/{order.id}/questions", data={"text": "Hei"})

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")
    assert questions_for(app, order) == []


def test_question_model_validation(order, customer):
    with pytest.raises(ValidationError):
        Question.ask(order, customer, "  ")
    with pytest.raises(ValidationError):
        Question.ask(order, customer, "x" * 2001)

    stranger = User(id=999, email="x@example.test", name="X", phone=None, password_hash="")
    with pytest.raises(ValidationError) as error:
        Question.ask(order, stranger, "Hei")
    assert "egne bestillinger" in error.value.messages["order"]

    question = Question.ask(order, customer, "  Hei  ")
    assert question.text == "Hei"
    assert question.status_label == "Ubesvart"


# US-17

def test_unanswered_questions_oldest_first(app, admin_client, order, customer):
    newest = add_question(app, order, customer, "Nyeste", datetime(2027, 1, 7, 12, 0))
    oldest = add_question(app, order, customer, "Eldste", datetime(2027, 1, 5, 9, 0))
    middle = add_question(app, order, customer, "Midterste", datetime(2027, 1, 6, 10, 30))

    html = admin_client.get("/admin/questions").get_data(as_text=True)

    ids = [int(i) for i in re.findall(r'id="question-(\d+)"', section(html, "Ubesvarte"))]
    assert ids == [oldest.id, middle.id, newest.id]
    assert "05.01.2027 kl. 09:00" in html


def test_answer_marks_question_answered_and_removes_from_list(app, admin_client, order, customer):
    question = add_question(app, order, customer, "Kommer dere med bestikk?", datetime(2027, 1, 5, 9, 0))

    response = answer(admin_client, question, "Ja, bestikk er med.")

    html = response.get_data(as_text=True)
    assert "Svaret på spørsmålet om EM-" in html
    assert "Kommer dere med bestikk?" not in section(html, "Ubesvarte")
    assert "Kommer dere med bestikk?" in section(html, "Nylig besvart")
    with app.app_context():
        assert question_repository().list_unanswered() == []
        assert question_repository().get(question.id).answer.text == "Ja, bestikk er med."


def test_only_one_answer_per_question(app, admin_client, admin, order, customer):
    question = add_question(app, order, customer, "Spørsmål", datetime(2027, 1, 5, 9, 0))
    answer(admin_client, question, "Første svar")

    response = answer(admin_client, question, "Andre svar")

    assert "Spørsmålet er allerede besvart." in response.get_data(as_text=True)
    with app.app_context():
        repository = question_repository()
        assert repository.get(question.id).answer.text == "Første svar"

        stored = repository.get(question.id)
        with pytest.raises(AlreadyAnsweredError):
            stored.answer_with(admin, "Tredje svar")

        stale = repository.get(question.id)
        stale.answer = None  # som om to admins hadde siden åpen samtidig
        stale.answer_with(admin, "Samtidig svar")
        with pytest.raises(AlreadyAnsweredError):
            repository.save_answer(stale)


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_answer_is_rejected(app, admin_client, order, customer, text):
    question = add_question(app, order, customer, "Spørsmål", datetime(2027, 1, 5, 9, 0))

    response = answer(admin_client, question, text)

    assert "Skriv et svar." in response.get_data(as_text=True)
    with app.app_context():
        assert question_repository().get(question.id).answer is None


def test_question_links_to_order(app, admin_client, order, customer):
    add_question(app, order, customer, "Spørsmål", datetime(2027, 1, 5, 9, 0))

    html = admin_client.get("/admin/questions").get_data(as_text=True)

    assert f'href="/admin/orders/{order.id}">{order.number}</a>' in html
    assert "Kari Testkunde" in html


def test_questions_shown_on_admin_order_page_and_answer_returns_there(app, admin_client, order, customer):
    question = add_question(app, order, customer, "Kan vi hente selv?", datetime(2027, 1, 5, 9, 0))

    html = admin_client.get(f"/admin/orders/{order.id}").get_data(as_text=True)
    assert "Kan vi hente selv?" in html
    assert f'action="/admin/questions/{question.id}/answer"' in html

    response = admin_client.post(
        f"/admin/questions/{question.id}/answer",
        data={"text": "Ja.", "next": f"/admin/orders/{order.id}#questions"},
    )
    assert response.headers["Location"] == f"/admin/orders/{order.id}#questions"


# US-18

def test_admin_menu_shows_unanswered_count(app, admin_client, order, customer):
    assert "Spørsmål (0)" in admin_client.get("/admin").get_data(as_text=True)

    first = add_question(app, order, customer, "Én", datetime(2027, 1, 5, 9, 0))
    add_question(app, order, customer, "To", datetime(2027, 1, 5, 10, 0))
    assert "Spørsmål (2)" in admin_client.get("/admin").get_data(as_text=True)

    answer(admin_client, first, "Svar")
    assert "Spørsmål (1)" in admin_client.get("/admin").get_data(as_text=True)
