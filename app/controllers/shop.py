"""Kundesiden: meny, handlekurv og bestilling (UC1–UC4)."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.controllers.auth import is_safe_next
from app.models.cart import Cart
from app.models.errors import ValidationError
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


# US-06 / US-07: handlekurv. Krever ikke innlogging (UC2).


@bp.route("/cart")
def cart():
    cart = _load_cart()
    _save_cart(cart)
    return render_template("shop/cart.html", cart=cart)


@bp.route("/cart/add", methods=["POST"])
def cart_add():
    cart = _load_cart()
    item = _requested_item()
    next_url = request.form.get("next", "")
    back = next_url if is_safe_next(next_url) else url_for("shop.menu")
    if item is None:
        flash("Fant ikke retten.", "error")
        return redirect(back)

    quantity = request.form.get("quantity")
    try:
        cart.add(item, quantity)
    except ValidationError as error:
        _flash_errors(error)
        return redirect(back)

    _save_cart(cart)
    flash(f"Lagt i handlekurven: {int(quantity)} × {item.name}")
    return redirect(back)


@bp.route("/cart/update", methods=["POST"])
def cart_update():
    cart = _load_cart()
    try:
        cart.set_quantity(_requested_item_id(), request.form.get("quantity"))
    except ValidationError as error:
        _flash_errors(error)
    else:
        _save_cart(cart)
        flash("Handlekurven er oppdatert.")
    return redirect(url_for("shop.cart"))


@bp.route("/cart/remove", methods=["POST"])
def cart_remove():
    cart = _load_cart()
    cart.remove(_requested_item_id())
    _save_cart(cart)
    flash("Linjen er fjernet fra handlekurven.")
    return redirect(url_for("shop.cart"))


def _load_cart():
    """Bygger handlekurven fra sessionen ({id: antall}) med priser fra repositoryet."""
    data = session.get("cart") or {}
    ids = [int(key) for key in data if str(key).isdigit()]
    cart = Cart.from_session(data, food_item_repository().get_by_ids(ids))
    for name in cart.removed_names:
        flash(f"{name} er ikke lenger tilgjengelig og er fjernet fra handlekurven.", "error")
    return cart


def _save_cart(cart):
    session["cart"] = cart.to_session()


def _requested_item_id():
    value = request.form.get("item_id", "")
    return int(value) if value.isdigit() else None


def _requested_item():
    item_id = _requested_item_id()
    return food_item_repository().get(item_id) if item_id is not None else None


def _flash_errors(error):
    for message in error.messages.values():
        flash(message, "error")
