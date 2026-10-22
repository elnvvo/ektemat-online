"""Repository-grensesnitt.

Controllers avhenger bare av disse klassene. SQLite-implementasjonene (sqlite_*.py)
kommer nå, og Neo4j-implementasjonene i Oblig 5. Metodene legges til sammen med
user storyene som trenger dem.
"""
from abc import ABC


class UserRepository(ABC):
    """Kunder og administratorer."""


class FoodItemRepository(ABC):
    """Matretter med eventkategorier, allergener og dietter."""


class OrderRepository(ABC):
    """Bestillinger med ordrelinjer og gjestegrupper."""


class QuestionRepository(ABC):
    """Spørsmål om bestillinger og svar fra Ekte Mat."""
