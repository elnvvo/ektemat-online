"""Ekte Mat Online – application factory."""
import os

from flask import Flask, render_template

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

    from app.controllers.auth import load_current_user

    app.before_request(load_current_user)
    app.register_error_handler(403, forbidden)
    app.add_template_filter(format_nok, "nok")

    return app


def forbidden(error):
    return render_template("errors/403.html"), 403


def format_nok(value):
    """189 -> '189 kr', 5670 -> '5 670 kr', 189.5 -> '189,50 kr'."""
    decimals = 0 if value == int(value) else 2
    number = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return f"{number} kr"
