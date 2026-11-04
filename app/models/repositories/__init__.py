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
        from app.models.repositories.neo4j_order_repository import Neo4jOrderRepository

        return Neo4jOrderRepository()
    from app.models.repositories.sqlite_order_repository import SqliteOrderRepository

    return SqliteOrderRepository()


def question_repository():
    if _storage() == "neo4j":
        from app.models.repositories.neo4j_question_repository import Neo4jQuestionRepository

        return Neo4jQuestionRepository()
    from app.models.repositories.sqlite_question_repository import SqliteQuestionRepository

    return SqliteQuestionRepository()


def user_repository():
    if _storage() == "neo4j":
        from app.models.repositories.neo4j_user_repository import Neo4jUserRepository

        return Neo4jUserRepository()
    from app.models.repositories.sqlite_user_repository import SqliteUserRepository

    return SqliteUserRepository()


def describe_storage(config):
    """Hvilken lagring appen bruker, til oppstartsmeldingen – uten passord."""
    if config["STORAGE"] == "neo4j":
        from app.models.repositories.neo4j_connection import describe_target

        return f"neo4j - {describe_target(config)}"
    return f"sqlite - {config['DATABASE']}"


def init_storage():
    """Tømmer og klargjør lagringen STORAGE peker på (brukes av seed.py og testene)."""
    if _storage() == "neo4j":
        from app.models.repositories.neo4j_connection import reset_database

        reset_database()
    else:
        from app.models.repositories.sqlite_connection import init_db

        init_db()
