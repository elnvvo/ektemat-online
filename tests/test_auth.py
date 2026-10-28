"""Akseptansetester for US-19 (registrere og logge inn), US-20 (egen admintilgang), NFR-03 og NFR-06."""
import re
import subprocess
from pathlib import Path

import pytest

from app.models.repositories import user_repository
from app.models.user import Role
from conftest import ADMIN_PASSWORD, CUSTOMER_PASSWORD, login

ROOT = Path(__file__).resolve().parent.parent


def register(client, email="ny@example.test", password="passord1", name="Nora Testkunde", **extra):
    return client.post(
        "/register", data={"name": name, "email": email, "password": password, **extra}
    )


def get_user(app, email):
    with app.app_context():
        return user_repository().get_by_email(email)


# US-19

def test_register_creates_account_and_logs_in(app, client):
    response = register(client, password="12345678")  # nøyaktig 8 tegn

    assert response.status_code == 302
    assert get_user(app, "ny@example.test") is not None
    html = client.get("/menu").get_data(as_text=True)
    assert "Nora Testkunde" in html
    assert "Logg ut" in html


def test_register_rejects_short_password(app, client):
    response = register(client, password="1234567")

    assert response.status_code == 400
    assert "minst 8 tegn" in response.get_data(as_text=True)
    assert get_user(app, "ny@example.test") is None


def test_register_rejects_duplicate_email(client, customer):
    response = register(client, email="KARI@example.test")

    assert response.status_code == 400
    assert "finnes allerede en konto" in response.get_data(as_text=True)


def test_register_cannot_create_admin(app, client):
    register(client, role="admin")

    assert get_user(app, "ny@example.test").role == Role.CUSTOMER
    assert client.get("/admin").status_code == 403


def test_login_with_correct_password(client, customer):
    response = login(client, customer.email, CUSTOMER_PASSWORD)

    assert response.status_code == 302
    assert "Kari Testkunde" in client.get("/menu").get_data(as_text=True)


def test_wrong_password_gives_generic_message(client, customer):
    wrong_password = login(client, customer.email, "feil-passord")
    unknown_email = login(client, "finnes.ikke@example.test", "feil-passord")

    assert wrong_password.status_code == unknown_email.status_code == 401
    message = re.compile(r'<p class="error" role="alert">(.*?)</p>')
    wrong_text = message.search(wrong_password.get_data(as_text=True)).group(1)
    unknown_text = message.search(unknown_email.get_data(as_text=True)).group(1)
    assert wrong_text == unknown_text == "Feil e-post eller passord."
    assert "Kari Testkunde" not in client.get("/menu").get_data(as_text=True)


def test_logout(client, customer):
    login(client, customer.email, CUSTOMER_PASSWORD)

    response = client.post("/logout")

    assert response.status_code == 302
    html = client.get("/menu").get_data(as_text=True)
    assert "Kari Testkunde" not in html
    assert "Logg inn" in html


def test_login_redirects_to_next(client, admin):
    response = login(client, admin.email, ADMIN_PASSWORD, next="/admin")
    assert response.headers["Location"] == "/admin"


def test_login_ignores_external_next(client, customer):
    response = login(client, customer.email, CUSTOMER_PASSWORD, next="//evil.example/")
    assert response.headers["Location"] == "/menu"


# US-20 / NFR-06

def test_customer_gets_403_on_admin(client, customer):
    login(client, customer.email, CUSTOMER_PASSWORD)
    assert client.get("/admin").status_code == 403


def test_anonymous_is_redirected_to_login(client):
    response = client.get("/admin")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login?next=/admin")


def test_admin_can_open_admin(client, admin):
    login(client, admin.email, ADMIN_PASSWORD)
    assert client.get("/admin").status_code == 200


def test_admin_link_only_for_admin(client, customer, admin):
    assert 'href="/admin/"' not in client.get("/menu").get_data(as_text=True)

    login(client, customer.email, CUSTOMER_PASSWORD)
    assert 'href="/admin/"' not in client.get("/menu").get_data(as_text=True)
    client.post("/logout")

    login(client, admin.email, ADMIN_PASSWORD)
    assert 'href="/admin/"' in client.get("/menu").get_data(as_text=True)


def admin_urls(app):
    """Én URL per /admin-rute, med 1 som verdi for alle parametere."""
    urls = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith("admin."):
            urls.append(rule.build({arg: 1 for arg in rule.arguments})[1])
    return urls


def test_every_admin_route_requires_admin_role(app, customer):
    urls = admin_urls(app)
    assert urls, "fant ingen admin-ruter"

    anonymous = app.test_client()
    for url in urls:
        response = anonymous.get(url)
        assert response.status_code == 302, url
        assert response.headers["Location"].startswith("/login"), url

    customer_client = app.test_client()
    login(customer_client, customer.email, CUSTOMER_PASSWORD)
    for url in urls:
        assert customer_client.get(url).status_code == 403, url


# NFR-03

def test_password_is_stored_as_salted_hash(app, client):
    register(client, email="a@example.test", password="samme-passord")
    register(app.test_client(), email="b@example.test", password="samme-passord")

    hash_a = get_user(app, "a@example.test").password_hash
    hash_b = get_user(app, "b@example.test").password_hash
    assert "samme-passord" not in hash_a
    assert hash_a.startswith("scrypt:")
    assert hash_a != hash_b  # ulikt salt


def test_env_file_is_git_ignored_and_example_has_no_values():
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", ".env"], cwd=ROOT, check=False
        )
    except FileNotFoundError:
        pytest.skip("git er ikke installert")
    assert result.returncode == 0, ".env må ligge i .gitignore"

    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            key, _, value = line.partition("=")
            assert value.strip() == "", f"{key} i .env.example skal ikke ha en verdi"
