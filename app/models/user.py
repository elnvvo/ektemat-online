"""Brukere og roller (design.md §2, US-19, US-20, NFR-03)."""
from dataclasses import dataclass
from enum import Enum

from werkzeug.security import check_password_hash, generate_password_hash

from app.models.errors import ValidationError

MIN_PASSWORD_LENGTH = 8


class Role(str, Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"


@dataclass
class User:
    id: int | None
    email: str
    name: str
    phone: str | None
    password_hash: str
    role: Role = Role.CUSTOMER

    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @classmethod
    def register(cls, email, name, password, phone=None):
        """Ny kunde fra registreringsskjemaet. Rollen er alltid CUSTOMER."""
        return cls._create(email, name, password, phone, Role.CUSTOMER)

    @classmethod
    def create_admin(cls, email, name, password):
        """Bare for seed.py – admin kan ikke registreres via nettsiden (US-20)."""
        return cls._create(email, name, password, None, Role.ADMIN)

    @classmethod
    def _create(cls, email, name, password, phone, role):
        email = normalize_email(email)
        name = (name or "").strip()
        password = password or ""

        errors = {}
        if not name:
            errors["name"] = "Skriv inn navnet ditt."
        if "@" not in email or "." not in email.split("@")[-1]:
            errors["email"] = "Skriv inn en gyldig e-postadresse."
        if len(password) < MIN_PASSWORD_LENGTH:
            errors["password"] = f"Passordet må ha minst {MIN_PASSWORD_LENGTH} tegn."
        if errors:
            raise ValidationError(errors)

        return cls(
            id=None,
            email=email,
            name=name,
            phone=phone,
            password_hash=generate_password_hash(password),
            role=role,
        )


def normalize_email(email):
    return (email or "").strip().lower()
