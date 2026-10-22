"""Lager databasetabellene og legger inn syntetiske brukere.

Kjør: python seed.py   (sletter og lager databasen på nytt)
"""
import os
import sys

from werkzeug.security import generate_password_hash

from app import create_app
from app.models.repositories.sqlite_connection import init_db, seed_users


def main():
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD")
    customer_password = os.environ.get("SEED_CUSTOMER_PASSWORD")
    if not admin_password or not customer_password:
        sys.exit("Sett SEED_ADMIN_PASSWORD og SEED_CUSTOMER_PASSWORD i .env (se .env.example).")

    users = [
        {
            "email": "admin@ektemat.test",
            "name": "Admin Testesen",
            "phone": None,
            "password_hash": generate_password_hash(admin_password),
            "role": "admin",
        },
        {
            "email": "kunde1@example.test",
            "name": "Kari Testkunde",
            "phone": "40000001",
            "password_hash": generate_password_hash(customer_password),
            "role": "customer",
        },
        {
            "email": "kunde2@example.test",
            "name": "Ola Testkunde",
            "phone": "40000002",
            "password_hash": generate_password_hash(customer_password),
            "role": "customer",
        },
    ]

    app = create_app()
    with app.app_context():
        init_db()
        seed_users(users)

    print(f"Database laget: {app.config['DATABASE']}")
    for user in users:
        print(f"  {user['role']:<8} {user['email']}")


if __name__ == "__main__":
    main()
