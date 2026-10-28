"""SQLite-implementasjon av QuestionRepository."""
import sqlite3
from dataclasses import replace
from datetime import datetime

from app.models.errors import AlreadyAnsweredError
from app.models.question import Answer, Question
from app.models.repositories.base import QuestionRepository
from app.models.repositories.sqlite_connection import get_db
from app.models.user import Role, User

_SELECT = (
    "SELECT q.id, q.order_id, q.user_id, q.text, q.asked_at,"
    " a.text AS answer_text, a.answered_at, a.user_id AS answer_user_id,"
    " u.email AS customer_email, u.name AS customer_name, u.phone AS customer_phone,"
    " u.role AS customer_role"
    " FROM questions q"
    " LEFT JOIN answers a ON a.question_id = q.id"
    " LEFT JOIN users u ON u.id = q.user_id"
)


class SqliteQuestionRepository(QuestionRepository):
    def add(self, question):
        db = get_db()
        cursor = db.execute(
            "INSERT INTO questions (order_id, user_id, text, asked_at) VALUES (?, ?, ?, ?)",
            (question.order_id, question.user_id, question.text, _store(question.asked_at)),
        )
        db.commit()
        return replace(question, id=cursor.lastrowid)

    def get(self, question_id):
        row = get_db().execute(_SELECT + " WHERE q.id = ?", (question_id,)).fetchone()
        return _to_question(row) if row else None

    def list_for_order(self, order_id):
        rows = get_db().execute(
            _SELECT + " WHERE q.order_id = ? ORDER BY q.asked_at, q.id", (order_id,)
        )
        return [_to_question(row) for row in rows]

    def list_unanswered(self):
        rows = get_db().execute(
            _SELECT + " WHERE a.question_id IS NULL ORDER BY q.asked_at, q.id"
        )
        return [_to_question(row) for row in rows]

    def list_answered(self, limit=20):
        rows = get_db().execute(
            _SELECT + " WHERE a.question_id IS NOT NULL ORDER BY a.answered_at DESC, q.id DESC LIMIT ?",
            (limit,),
        )
        return [_to_question(row) for row in rows]

    def save_answer(self, question):
        answer = question.answer
        db = get_db()
        try:
            db.execute(
                "INSERT INTO answers (question_id, user_id, text, answered_at) VALUES (?, ?, ?, ?)",
                (question.id, answer.user_id, answer.text, _store(answer.answered_at)),
            )
        except sqlite3.IntegrityError as error:
            # question_id er primærnøkkel: maks ett svar, også om to svarer samtidig.
            db.rollback()
            raise AlreadyAnsweredError() from error
        db.commit()

    def count_unanswered(self):
        return get_db().execute(
            "SELECT COUNT(*) FROM questions q"
            " WHERE NOT EXISTS (SELECT 1 FROM answers a WHERE a.question_id = q.id)"
        ).fetchone()[0]


def _to_question(row):
    answer = None
    if row["answer_text"] is not None:
        answer = Answer(
            text=row["answer_text"],
            answered_at=datetime.fromisoformat(row["answered_at"]),
            user_id=row["answer_user_id"],
        )
    customer = None
    if row["customer_email"] is not None:
        customer = User(
            id=row["user_id"],
            email=row["customer_email"],
            name=row["customer_name"],
            phone=row["customer_phone"],
            password_hash="",
            role=Role(row["customer_role"]),
        )
    return Question(
        id=row["id"],
        order_id=row["order_id"],
        user_id=row["user_id"],
        text=row["text"],
        asked_at=datetime.fromisoformat(row["asked_at"]),
        answer=answer,
        customer=customer,
    )


def _store(moment):
    """Lokal tid som ISO-tekst (sorterbar), f.eks. 2026-10-28 11:05:00."""
    return moment.isoformat(sep=" ", timespec="seconds")
