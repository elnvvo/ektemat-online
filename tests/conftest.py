import pytest

from app import create_app
from app.models.repositories import user_repository
from app.models.repositories.sqlite_connection import init_db
from app.models.user import User

# Syntetiske testpassord, bare brukt i den midlertidige testdatabasen.
CUSTOMER_PASSWORD = "kunde-test-123"
ADMIN_PASSWORD = "admin-test-123"


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "DATABASE": str(tmp_path / "test.sqlite"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"),
            "IMAGE_API_KEY": None,
            # Alltid SQLite, uansett STORAGE i .env: testene skal aldri røre den delte Neo4j-databasen.
            "STORAGE": "sqlite",
        }
    )
    with app.app_context():
        init_db()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def customer(app):
    with app.app_context():
        return user_repository().add(
            User.register("kari@example.test", "Kari Testkunde", CUSTOMER_PASSWORD)
        )


@pytest.fixture
def admin(app):
    with app.app_context():
        return user_repository().add(
            User.create_admin("admin@ektemat.test", "Admin Testesen", ADMIN_PASSWORD)
        )


def login(client, email, password, **extra):
    return client.post("/login", data={"email": email, "password": password, **extra})
