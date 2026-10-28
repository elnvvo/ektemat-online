"""Kundesiden: meny, handlekurv og bestilling (UC1–UC4)."""
from flask import Blueprint, render_template, request

from app.models.repositories import food_item_repository

bp = Blueprint("shop", __name__)


@bp.route("/")
def index():
    return render_template("shop/index.html")


@bp.route("/menu")
def menu():
    """US-01/US-02: publiserte retter som kort, filtrert på arrangementskategori."""
    category = request.args.get("category") or None
    repository = food_item_repository()
    return render_template(
        "shop/menu.html",
        categories=repository.list_event_categories(),
        items=repository.list_published(category),
        selected_category=category,
    )
