"""Ekte Mat Online – application factory."""
import os

from urllib.parse import urlsplit

from flask import Flask, current_app, flash, redirect, render_template, request, session, url_for

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

    from app.models.repositories import STORAGES, sqlite_connection

    if app.config.get("STORAGE") not in STORAGES:
        raise RuntimeError(
            f"STORAGE={app.config.get('STORAGE')!r} er ugyldig. Bruk 'sqlite' eller 'neo4j' i .env."
        )
    # SQLite kobles alltid til: ordre og spørsmål ligger der til de er flyttet (Oblig 5).
    sqlite_connection.init_app(app)
    if app.config["STORAGE"] == "neo4j":
        from app.models.repositories import neo4j_connection

        neo4j_connection.init_app(app)
        for error_class in neo4j_connection.CONNECTION_ERRORS:
            app.register_error_handler(error_class, storage_unavailable)

    from app.models.repositories.not_migrated import StorageNotMigratedError

    app.register_error_handler(StorageNotMigratedError, storage_not_migrated)

    from app.controllers.account import bp as account_bp
    from app.controllers.admin import bp as admin_bp
    from app.controllers.shop import bp as shop_bp

    app.register_blueprint(shop_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp)

    from app.controllers.auth import load_current_user

    app.before_request(load_current_user)
    app.register_error_handler(403, forbidden)
    app.register_error_handler(413, too_large)
    app.add_template_filter(format_nok, "nok")
    app.add_template_filter(format_date_no, "date_no")
    app.add_template_filter(format_datetime_no, "datetime_no")
    app.context_processor(cart_context)

    return app


def cart_context():
    """Antall linjer i handlekurven til toppmenyen (leser bare sessionen, ingen database)."""
    return {"cart_line_count": len(session.get("cart") or {})}


def forbidden(error):
    return render_template("errors/403.html"), 403


def storage_not_migrated(error):
    """Oblig 5: funksjonen er ikke flyttet til Neo4j ennå."""
    return render_template("errors/storage.html", title="Ikke tilgjengelig ennå", message=str(error)), 501


def storage_unavailable(error):
    """Neo4j svarer ikke (f.eks. en Aura Free-instans som er satt på pause)."""
    current_app.logger.warning("Neo4j svarer ikke: %s", error)
    message = "Databasen svarer ikke akkurat nå. Prøv igjen om litt."
    return render_template("errors/storage.html", title="Databasen svarer ikke", message=message), 503


def too_large(error):
    """US-05: opplastingen er større enn MAX_CONTENT_LENGTH."""
    from app.controllers.auth import is_safe_next

    flash("Filen er for stor. Bilder kan være maks 5 MB.", "error")
    back = urlsplit(request.referrer or "").path  # bare stien, aldri en annen vert
    return redirect(back if is_safe_next(back) else url_for("shop.index"))


def format_date_no(value):
    """date(2027, 1, 15) -> '15.01.2027'. Bare dato, siden created_at lagres i UTC."""
    return value.strftime("%d.%m.%Y") if value else ""


def format_datetime_no(value):
    """datetime(2026, 10, 28, 11, 5) -> '28.10.2026 kl. 11:05' (lokal tid)."""
    return value.strftime("%d.%m.%Y kl. %H:%M") if value else ""


def format_nok(value):
    """189 -> '189 kr', 5670 -> '5 670 kr', 189.5 -> '189,50 kr'."""
    decimals = 0 if value == int(value) else 2
    number = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return f"{number} kr"
