"""Kundesiden: meny, handlekurv og bestilling (UC1–UC4)."""
from datetime import date, timedelta

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from app.controllers.auth import is_safe_next, login_required
from app.models.cart import Cart
from app.models.errors import ValidationError
from app.models.order import Order
from app.models.repositories import food_item_repository, order_repository

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


# US-08 / US-09: bestilling (design.md §3)


@bp.route("/order", methods=["GET", "POST"])
@login_required
def order():
    cart = _load_cart()
    if cart.is_empty:
        flash("Handlekurven er tom. Legg til retter før du bestiller.", "error")
        return redirect(url_for("shop.cart"))

    repository = food_item_repository()
    catalog = {"allergens": repository.list_allergens(), "labels": repository.list_dietary_labels()}
    errors = {}
    action = request.form.get("action", "submit")

    if request.method == "GET":
        form = {"event_date": "", "guest_count": "", "delivery_address": "", "groups": [_blank_group()]}
    else:
        form = _order_form_values(request.form)
        if action == "add_group":
            form["groups"].append(_blank_group())
        elif action.startswith("remove_group-"):
            index = int(action.removeprefix("remove_group-")) - 1
            if 0 <= index < len(form["groups"]):
                form["groups"].pop(index)
        else:
            try:
                new_order = Order.create_from_cart(
                    user=g.user,
                    cart=cart,
                    event_date=form["event_date"],
                    guest_count=form["guest_count"],
                    delivery_address=form["delivery_address"],
                    guest_groups=[_guest_group_input(group, catalog) for group in form["groups"]],
                )
            except ValidationError as error:
                errors = error.messages
            else:
                saved = order_repository().save(new_order)
                session["cart"] = {}
                flash(f"Takk! Bestillingen er mottatt. Bestillingsnummeret ditt er {saved.number}.")
                return redirect(url_for("account.order_detail", order_id=saved.id), code=303)

    return (
        render_template(
            "shop/order_form.html",
            cart=cart,
            form=form,
            errors=errors,
            min_date=(date.today() + timedelta(days=1)).isoformat(),
            **catalog,
        ),
        400 if errors else 200,
    )


def _blank_group():
    return {"size": "", "allergens": set(), "labels": set(), "notes": ""}


def _order_form_values(data):
    count = data.get("group_count", "0")
    count = int(count) if count.isdigit() else 0
    groups = [
        {
            "size": data.get(f"group-{i}-size", ""),
            "allergens": set(data.getlist(f"group-{i}-allergens")),
            "labels": set(data.getlist(f"group-{i}-labels")),
            "notes": data.get(f"group-{i}-notes", ""),
        }
        for i in range(1, min(count, 50) + 1)
    ]
    return {
        "event_date": data.get("event_date", ""),
        "guest_count": data.get("guest_count", ""),
        "delivery_address": data.get("delivery_address", ""),
        "groups": groups,
    }


def _guest_group_input(group, catalog):
    """Slår opp valgte koder i de samme listene som matrettene bruker."""
    return {
        "size": group["size"],
        "allergens": [a for a in catalog["allergens"] if a.code in group["allergens"]],
        "dietary_labels": [d for d in catalog["labels"] if d.code in group["labels"]],
        "notes": group["notes"],
    }


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
