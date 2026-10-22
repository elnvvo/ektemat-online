"""SQLite-tilkobling. Bare repository-laget skal importere denne modulen."""
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_db():
    """Én tilkobling per request, lagret i flask.g."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Sletter og lager alle tabellene på nytt."""
    db = get_db()
    db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    db.commit()


def seed_users(users):
    """Setter inn brukere for seed.py. users: dicts med email, name, phone, password_hash, role."""
    db = get_db()
    db.executemany(
        "INSERT INTO users (email, name, phone, password_hash, role)"
        " VALUES (:email, :name, :phone, :password_hash, :role)",
        users,
    )
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
