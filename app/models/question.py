"""Spørsmål om en bestilling og svar fra Ekte Mat (design.md §2, US-16, US-17)."""
from dataclasses import dataclass
from datetime import datetime

from app.models.errors import AlreadyAnsweredError, ValidationError
from app.models.user import User

MAX_LENGTH = 2000


@dataclass
class Answer:
    text: str
    answered_at: datetime
    user_id: int | None = None


@dataclass
class Question:
    id: int | None
    order_id: int
    user_id: int | None
    text: str
    asked_at: datetime
    answer: Answer | None = None
    # User 1 -> 0..* Question («asks»). Fylles inn i adminlisten.
    customer: User | None = None

    @property
    def is_answered(self):
        return self.answer is not None

    @property
    def status_label(self):
        return "Besvart" if self.is_answered else "Ubesvart"

    @property
    def order_number(self):
        return f"EM-{self.order_id:05d}"

    @classmethod
    def ask(cls, order, user, text, now=None):
        """US-16: kunden spør om en av sine egne bestillinger."""
        if order.user_id != user.id:
            raise ValidationError({"order": "Du kan bare spørre om dine egne bestillinger."})
        return cls(
            id=None,
            order_id=order.id,
            user_id=user.id,
            text=_validated_text(text, "Skriv et spørsmål."),
            asked_at=now or datetime.now().replace(microsecond=0),
        )

    def answer_with(self, admin, text, now=None):
        """US-17: Ekte Mat svarer. Maks ett svar per spørsmål."""
        if self.is_answered:
            raise AlreadyAnsweredError()
        self.answer = Answer(
            text=_validated_text(text, "Skriv et svar."),
            answered_at=now or datetime.now().replace(microsecond=0),
            user_id=admin.id,
        )


def _validated_text(text, empty_message):
    text = (text or "").strip()
    if not text:
        raise ValidationError({"text": empty_message})
    if len(text) > MAX_LENGTH:
        raise ValidationError({"text": f"Teksten kan ikke være lengre enn {MAX_LENGTH} tegn."})
    return text
