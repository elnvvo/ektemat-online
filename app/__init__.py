"""Ekte Mat Online – application factory."""
import os

from flask import Flask

from app.config import Config


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config["DATABASE"] = os.path.join(app.instance_path, app.config["DATABASE"])
    if test_config is not None:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY mangler. Kopier .env.example til .env og fyll inn en verdi."
        )

    os.makedirs(app.instance_path, exist_ok=True)

    from app.models.repositories import sqlite_connection

    sqlite_connection.init_app(app)

    from app.controllers.account import bp as account_bp
    from app.controllers.admin import bp as admin_bp
    from app.controllers.shop import bp as shop_bp

    app.register_blueprint(shop_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp)

    return app
