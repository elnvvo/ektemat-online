"""Plassholdere for ordre og spørsmål når STORAGE=neo4j (Oblig 5, steg 1).

Ordre og spørsmål er ikke flyttet til Neo4j ennå. I SQLite peker de med fremmednøkler på
brukere og matretter som da ligger i Neo4j, så de kan ikke lagres der. Lesing gir tomme svar,
så sidene virker; skriving gir StorageNotMigratedError (vises som 501 av create_app).
"""
from app.models.repositories.base import OrderRepository, QuestionRepository


class StorageNotMigratedError(Exception):
    """Funksjonen er ikke flyttet til den valgte lagringen ennå."""

    def __init__(self, what):
        super().__init__(
            f"{what} er ikke flyttet til Neo4j ennå. Kjør med STORAGE=sqlite for å bruke dette."
        )


class NotMigratedOrderRepository(OrderRepository):
    def save(self, order):
        raise StorageNotMigratedError("Bestillinger")

    def update_status(self, order):
        raise StorageNotMigratedError("Bestillinger")

    def list_for_user(self, user_id):
        return []

    def get_for_user(self, order_id, user_id):
        return None

    def list_all(self, status=None, date_from=None, date_to=None):
        return []

    def get(self, order_id):
        return None


class NotMigratedQuestionRepository(QuestionRepository):
    def add(self, question):
        raise StorageNotMigratedError("Spørsmål")

    def save_answer(self, question):
        raise StorageNotMigratedError("Spørsmål")

    def get(self, question_id):
        return None

    def list_for_order(self, order_id):
        return []

    def list_unanswered(self):
        return []

    def list_answered(self, limit=20):
        return []

    def count_unanswered(self):
        return 0
