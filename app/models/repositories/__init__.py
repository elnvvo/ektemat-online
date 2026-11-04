"""Repository-laget: det eneste stedet som rører databasen (NFR-02).

Controllerne henter repositoryene herfra. STORAGE i .env («sqlite» eller «neo4j»,
satt i create_app) bestemmer hvilken implementasjon de får.
"""
from flask import current_app

STORAGES = ("sqlite", "neo4j")


def _storage():
    return current_app.config["STORAGE"]


def food_item_repository():
    if _storage() == "neo4j":
        from app.models.repositories.neo4j_food_item_repository import Neo4jFoodItemRepository

        return Neo4jFoodItemRepository()
    from app.models.repositories.sqlite_food_item_repository import SqliteFoodItemRepository

    return SqliteFoodItemRepository()


def order_repository():
    if _storage() == "neo4j":
        from app.models.repositories.not_migrated import NotMigratedOrderRepository

        return NotMigratedOrderRepository()  # ikke flyttet til Neo4j ennå
    from app.models.repositories.sqlite_order_repository import SqliteOrderRepository

    return SqliteOrderRepository()


def question_repository():
    if _storage() == "neo4j":
        from app.models.repositories.not_migrated import NotMigratedQuestionRepository

        return NotMigratedQuestionRepository()  # ikke flyttet til Neo4j ennå
    from app.models.repositories.sqlite_question_repository import SqliteQuestionRepository

    return SqliteQuestionRepository()


def user_repository():
    if _storage() == "neo4j":
        from app.models.repositories.neo4j_user_repository import Neo4jUserRepository

        return Neo4jUserRepository()
    from app.models.repositories.sqlite_user_repository import SqliteUserRepository

    return SqliteUserRepository()


def init_storage():
    """Tømmer og klargjør lagringen STORAGE peker på (brukes av seed.py og testene)."""
    if _storage() == "neo4j":
        from app.models.repositories.neo4j_connection import reset_database

        reset_database()
    else:
        from app.models.repositories.sqlite_connection import init_db

        init_db()
