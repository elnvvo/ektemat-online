"""Repository-laget: det eneste stedet som rører databasen (NFR-02).

Controllerne henter repositoryene herfra, så implementasjonen (SQLite nå,
Neo4j i Oblig 5) byttes på ett sted.
"""


def food_item_repository():
    from app.models.repositories.sqlite_food_item_repository import SqliteFoodItemRepository

    return SqliteFoodItemRepository()


def order_repository():
    from app.models.repositories.sqlite_order_repository import SqliteOrderRepository

    return SqliteOrderRepository()


def user_repository():
    from app.models.repositories.sqlite_user_repository import SqliteUserRepository

    return SqliteUserRepository()
