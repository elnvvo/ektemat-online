"""Repository-grensesnitt.

Controllers avhenger bare av disse klassene. SQLite-implementasjonene (sqlite_*.py)
kommer nå, og Neo4j-implementasjonene i Oblig 5. Metodene legges til sammen med
user storyene som trenger dem.
"""
from abc import ABC, abstractmethod

from app.models.food_item import Allergen, DietaryLabel, EventCategory, FoodItem
from app.models.user import User


class UserRepository(ABC):
    """Kunder og administratorer. Eneste sted som leser og skriver brukere."""

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None:
        """Brukeren med denne id-en, eller None."""

    @abstractmethod
    def get_by_email(self, email: str) -> User | None:
        """Brukeren med denne e-postadressen (normalisert), eller None."""

    @abstractmethod
    def add(self, user: User) -> User:
        """Lagrer en ny bruker og returnerer den med id. Kaster DuplicateEmailError."""


class FoodItemRepository(ABC):
    """Matretter med eventkategorier, allergener og dietter."""

    @abstractmethod
    def list_published(self, category_name: str | None = None) -> list[FoodItem]:
        """Publiserte retter sortert på navn, eventuelt bare i én kategori (US-01)."""

    @abstractmethod
    def list_event_categories(self) -> list[EventCategory]:
        """Alle arrangementskategorier sortert på navn."""

    @abstractmethod
    def add(self, item: FoodItem) -> FoodItem:
        """Lagrer en ny rett med koblinger og returnerer den med id."""

    @abstractmethod
    def add_event_category(self, name: str) -> EventCategory:
        """Lagrer en ny kategori og returnerer den med id."""

    @abstractmethod
    def add_allergen(self, allergen: Allergen) -> None:
        """Lagrer et allergen."""

    @abstractmethod
    def add_dietary_label(self, label: DietaryLabel) -> None:
        """Lagrer et diettmerke."""


class OrderRepository(ABC):
    """Bestillinger med ordrelinjer og gjestegrupper."""


class QuestionRepository(ABC):
    """Spørsmål om bestillinger og svar fra Ekte Mat."""
