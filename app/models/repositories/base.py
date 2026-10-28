"""Repository-grensesnitt.

Controllers avhenger bare av disse klassene. SQLite-implementasjonene (sqlite_*.py)
kommer nå, og Neo4j-implementasjonene i Oblig 5. Metodene legges til sammen med
user storyene som trenger dem.
"""
from abc import ABC, abstractmethod
from datetime import date

from app.models.food_item import Allergen, DietaryLabel, EventCategory, FoodItem
from app.models.order import Order, OrderStatus
from app.models.question import Question
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
        """Publiserte, ikke-arkiverte retter sortert på navn, eventuelt i én kategori (US-01)."""

    @abstractmethod
    def list_all(self) -> list[FoodItem]:
        """Alle retter, også upubliserte og arkiverte, sortert på navn (admin, US-03)."""

    @abstractmethod
    def get(self, item_id: int) -> FoodItem | None:
        """Retten med denne id-en (også arkivert), eller None."""

    @abstractmethod
    def get_by_ids(self, item_ids: list[int]) -> list[FoodItem]:
        """Rettene med disse id-ene (også upubliserte og arkiverte); ukjente id-er hoppes over."""

    @abstractmethod
    def list_event_categories(self) -> list[EventCategory]:
        """Alle arrangementskategorier sortert på navn."""

    @abstractmethod
    def list_allergens(self) -> list[Allergen]:
        """Alle allergener sortert på navn."""

    @abstractmethod
    def list_dietary_labels(self) -> list[DietaryLabel]:
        """Alle diettmerker sortert på kode."""

    @abstractmethod
    def add(self, item: FoodItem) -> FoodItem:
        """Lagrer en ny rett med koblinger og returnerer den med id."""

    @abstractmethod
    def update(self, item: FoodItem) -> FoodItem:
        """Oppdaterer feltene og erstatter koblingene. Endrer ikke archived."""

    @abstractmethod
    def set_image(self, item_id: int, image_path: str, image_prompt: str | None) -> None:
        """Lagrer bildestien (relativt til static) og bildeinstruksen (US-05)."""

    @abstractmethod
    def set_published(self, item_id: int, published: bool) -> None:
        """Publiserer eller avpubliserer en rett (US-04)."""

    @abstractmethod
    def archive(self, item_id: int) -> None:
        """«Fjerner» en rett: arkiverer og avpubliserer, sletter aldri (US-03)."""

    @abstractmethod
    def restore(self, item_id: int) -> None:
        """Henter en arkivert rett tilbake som upublisert."""

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

    @abstractmethod
    def save(self, order: Order) -> Order:
        """Lagrer en ny bestilling med linjer og gjestegrupper i én transaksjon (US-08)."""

    @abstractmethod
    def list_for_user(self, user_id: int) -> list[Order]:
        """Kundens bestillinger sortert etter arrangementsdato, uten linjer og grupper (US-11)."""

    @abstractmethod
    def get_for_user(self, order_id: int, user_id: int) -> Order | None:
        """Bestillingen hvis den tilhører denne kunden, ellers None (NFR-06)."""

    @abstractmethod
    def list_all(
        self,
        status: OrderStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Order]:
        """Alle bestillinger med kunde, sortert etter arrangementsdato, filtrert (admin, US-12)."""

    @abstractmethod
    def get(self, order_id: int) -> Order | None:
        """Hele bestillingen med kunde, linjer og gjestegrupper (admin)."""

    @abstractmethod
    def update_status(self, order: Order) -> None:
        """Lagrer status, status_reason og payment_status (validert i modellen, US-13/14)."""


class QuestionRepository(ABC):
    """Spørsmål om bestillinger og svar fra Ekte Mat."""

    @abstractmethod
    def add(self, question: Question) -> Question:
        """Lagrer et nytt spørsmål og returnerer det med id (US-16)."""

    @abstractmethod
    def get(self, question_id: int) -> Question | None:
        """Spørsmålet med svar, eller None."""

    @abstractmethod
    def list_for_order(self, order_id: int) -> list[Question]:
        """Spørsmålene om en bestilling med svar, i rekkefølgen de ble stilt."""

    @abstractmethod
    def list_unanswered(self) -> list[Question]:
        """Ubesvarte spørsmål med kunde, eldste først (US-17)."""

    @abstractmethod
    def list_answered(self, limit: int = 20) -> list[Question]:
        """Besvarte spørsmål med kunde og svar, nyeste svar først."""

    @abstractmethod
    def save_answer(self, question: Question) -> None:
        """Lagrer svaret. Kaster AlreadyAnsweredError hvis det allerede finnes et."""

    @abstractmethod
    def count_unanswered(self) -> int:
        """Antall ubesvarte spørsmål (US-18)."""
