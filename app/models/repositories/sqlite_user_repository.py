"""SQLite-implementasjon av UserRepository."""
import sqlite3
from dataclasses import replace

from app.models.errors import DuplicateEmailError
from app.models.repositories.base import UserRepository
from app.models.repositories.sqlite_connection import get_db
from app.models.user import Role, User, normalize_email


class SqliteUserRepository(UserRepository):
    def get_by_id(self, user_id):
        row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._to_user(row) if row else None

    def get_by_email(self, email):
        row = get_db().execute(
            "SELECT * FROM users WHERE email = ?", (normalize_email(email),)
        ).fetchone()
        return self._to_user(row) if row else None

    def add(self, user):
        db = get_db()
        try:
            cursor = db.execute(
                "INSERT INTO users (email, name, phone, password_hash, role) VALUES (?, ?, ?, ?, ?)",
                (user.email, user.name, user.phone, user.password_hash, user.role.value),
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateEmailError(user.email) from error
        db.commit()
        return replace(user, id=cursor.lastrowid)

    @staticmethod
    def _to_user(row):
        return User(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            phone=row["phone"],
            password_hash=row["password_hash"],
            role=Role(row["role"]),
        )
