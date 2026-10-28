"""Adminpanel: matretter, bestillinger og spørsmål (UC8–UC11).

Alle ruter i denne blueprinten krever admin-rollen (US-20, NFR-06).
"""
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.controllers.auth import admin_required
from app.models.errors import ValidationError
from app.models.food_item import FoodItem
from app.models.order import REASON_REQUIRED, OrderStatus
from app.models.repositories import food_item_repository, order_repository

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@admin_required
def require_admin():
    """Kjøres før hver /admin-rute. Returnerer None (fortsett) bare for admin."""


@bp.route("/", strict_slashes=False)
@admin_required
def index():
    return render_template("admin/index.html")


# US-03 / US-04: matretter


@bp.route("/items")
@admin_required
def items():
    all_items = food_item_repository().list_all()
    return render_template(
        "admin/items.html",
        items=[item for item in all_items if not item.archived],
        archived_items=[item for item in all_items if item.archived],
    )


@bp.route("/items/new", methods=["GET", "POST"])
@admin_required
def new_item():
    return _item_form(item=None)


@bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_item(item_id):
    return _item_form(item=_get_or_404(item_id))


@bp.route("/items/<int:item_id>/publish", methods=["POST"])
@admin_required
def publish_item(item_id):
    item = _get_or_404(item_id)
    published = request.form.get("published") == "1"
    if item.archived and published:
        flash(f"{item.name} er arkivert. Gjenopprett den før du publiserer.")
        return redirect(url_for("admin.items"))
    food_item_repository().set_published(item.id, published)
    flash(f"{'Publisert' if published else 'Avpublisert'}: {item.name}")
    return redirect(url_for("admin.items"))


@bp.route("/items/<int:item_id>/archive", methods=["GET", "POST"])
@admin_required
def archive_item(item_id):
    """GET viser en bekreftelsesside (virker uten JavaScript-dialoger), POST arkiverer."""
    item = _get_or_404(item_id)
    if request.method == "GET":
        return render_template("admin/item_archive.html", item=item)
    food_item_repository().archive(item.id)
    flash(f"Fjernet fra menyen og arkivert: {item.name}")
    return redirect(url_for("admin.items"))


@bp.route("/items/<int:item_id>/restore", methods=["POST"])
@admin_required
def restore_item(item_id):
    item = _get_or_404(item_id)
    food_item_repository().restore(item.id)
    flash(f"Gjenopprettet (ikke publisert): {item.name}")
    return redirect(url_for("admin.items"))


# US-12 / US-13 / US-14: bestillinger


@bp.route("/orders")
@admin_required
def orders():
    """US-12: alle bestillinger sortert etter arrangementsdato, filtrert på status og periode."""
    filters = {
        "status": request.args.get("status", ""),
        "from": request.args.get("from", ""),
        "to": request.args.get("to", ""),
    }
    status = None
    if filters["status"]:
        try:
            status = OrderStatus(filters["status"])
        except ValueError:
            flash("Ukjent status i filteret ble ignorert.", "error")
            filters["status"] = ""
    date_from = _filter_date(filters, "from")
    date_to = _filter_date(filters, "to")

    return render_template(
        "admin/orders.html",
        orders=order_repository().list_all(status, date_from, date_to),
        filters=filters,
        statuses=list(OrderStatus),
    )


@bp.route("/orders/<int:order_id>")
@admin_required
def order_detail(order_id):
    return render_template(
        "admin/order_detail.html",
        order=_get_order_or_404(order_id),
        reason_required=REASON_REQUIRED,
    )


@bp.route("/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def order_status(order_id):
    """US-13: lovlige overganger avgjøres av tilstandsmaskinen i Order. Ved feil lagres ingenting."""
    order = _get_order_or_404(order_id)
    try:
        order.change_status(request.form.get("status", ""), request.form.get("reason"))
    except ValidationError as error:
        _flash_errors(error)
    else:
        order_repository().update_status(order)
        flash(f"Status endret til {order.status.label}.")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@bp.route("/orders/<int:order_id>/payment", methods=["POST"])
@admin_required
def order_payment(order_id):
    """US-14: betalingsstatus i sin egen tilstandsmaskin."""
    order = _get_order_or_404(order_id)
    try:
        order.change_payment_status(request.form.get("payment_status", ""))
    except ValidationError as error:
        _flash_errors(error)
    else:
        order_repository().update_status(order)
        flash(f"Betaling endret til {order.payment_status.label}.")
    return redirect(url_for("admin.order_detail", order_id=order_id))


def _filter_date(filters, key):
    if not filters[key]:
        return None
    try:
        return date.fromisoformat(filters[key])
    except ValueError:
        flash(f"Ugyldig dato «{filters[key]}» i filteret ble ignorert.", "error")
        filters[key] = ""
        return None


def _get_order_or_404(order_id):
    order = order_repository().get(order_id)
    if order is None:
        abort(404)
    return order


def _flash_errors(error):
    for message in error.messages.values():
        flash(message, "error")


def _item_form(item):
    """Felles for ny og endret rett. Validering skjer i FoodItem.from_input."""
    repository = food_item_repository()
    catalog = {
        "categories": repository.list_event_categories(),
        "allergens": repository.list_allergens(),
        "labels": repository.list_dietary_labels(),
    }
    errors = {}

    if request.method == "POST":
        form = _form_values(request.form)
        try:
            new = FoodItem.from_input(
                name=form["name"],
                description=form["description"],
                price=form["price"],
                min_order_qty=form["min_order_qty"],
                published=form["published"],
                event_categories=[c for c in catalog["categories"] if str(c.id) in form["categories"]],
                allergens=[a for a in catalog["allergens"] if a.code in form["allergens"]],
                dietary_labels=[d for d in catalog["labels"] if d.code in form["labels"]],
                id=item.id if item else None,
                image_path=item.image_path if item else None,
                image_prompt=item.image_prompt if item else None,
                origin=item.origin if item else None,
                archived=item.archived if item else False,
            )
        except ValidationError as error:
            errors = error.messages
        else:
            saved = repository.update(new) if item else repository.add(new)
            flash(f"Lagret: {saved.name}")
            return redirect(url_for("admin.items"))
    else:
        form = _form_values_from_item(item)

    status = 400 if errors else 200
    return (
        render_template("admin/item_form.html", item=item, form=form, errors=errors, **catalog),
        status,
    )


def _form_values(data):
    return {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "price": data.get("price", ""),
        "min_order_qty": data.get("min_order_qty", ""),
        "published": data.get("published") == "1",
        "categories": set(data.getlist("categories")),
        "allergens": set(data.getlist("allergens")),
        "labels": set(data.getlist("labels")),
    }


def _form_values_from_item(item):
    if item is None:
        return {
            "name": "",
            "description": "",
            "price": "",
            "min_order_qty": "1",
            "published": False,
            "categories": set(),
            "allergens": set(),
            "labels": set(),
        }
    return {
        "name": item.name,
        "description": item.description,
        "price": str(item.price_nok),
        "min_order_qty": str(item.min_order_qty),
        "published": item.published,
        "categories": {str(c.id) for c in item.event_categories},
        "allergens": {a.code for a in item.allergens},
        "labels": {d.code for d in item.dietary_labels},
    }


def _get_or_404(item_id):
    item = food_item_repository().get(item_id)
    if item is None:
        abort(404)
    return item
