"""Adminpanel: matretter, bestillinger og spørsmål (UC8–UC11).

Alle ruter i denne blueprinten krever admin-rollen (US-20, NFR-06).
"""
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from app.controllers.auth import admin_required, is_safe_next
from app.models.errors import ValidationError
from app.models.food_item import FoodItem
from app.models.item_image import validate_image, validate_prompt
from app.services import image_store
from app.services.image_service import get_image_service
from app.models.order import REASON_REQUIRED, OrderStatus
from app.models.repositories import food_item_repository, order_repository, question_repository

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@admin_required
def require_admin():
    """Kjøres før hver /admin-rute. Returnerer None (fortsett) bare for admin."""


@bp.route("/", strict_slashes=False)
@admin_required
def index():
    return render_template(
        "admin/index.html", unanswered_count=question_repository().count_unanswered()
    )


# US-17 / US-18: spørsmål fra kunder


@bp.route("/questions")
@admin_required
def questions():
    repository = question_repository()
    return render_template(
        "admin/questions.html",
        unanswered=repository.list_unanswered(),
        answered=repository.list_answered(),
    )


@bp.route("/questions/<int:question_id>/answer", methods=["POST"])
@admin_required
def answer_question(question_id):
    repository = question_repository()
    question = repository.get(question_id)
    if question is None:
        abort(404)
    try:
        question.answer_with(g.user, request.form.get("text"))
        repository.save_answer(question)
    except ValidationError as error:
        _flash_errors(error)
    else:
        flash(f"Svaret på spørsmålet om {question.order_number} er sendt.")
    next_url = request.form.get("next", "")
    return redirect(next_url if is_safe_next(next_url) else url_for("admin.questions"))


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
    order = _get_order_or_404(order_id)
    return render_template(
        "admin/order_detail.html",
        order=order,
        reason_required=REASON_REQUIRED,
        questions=question_repository().list_for_order(order.id),
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


# US-05: bilde på matretten (opplasting eller bildeinstruks, med forhåndsvisning)


@bp.route("/items/<int:item_id>/image")
@admin_required
def item_image(item_id):
    item = _get_or_404(item_id)
    pending = _pending_image(item.id)
    return render_template(
        "admin/item_image.html",
        item=item,
        pending=pending,
        pending_path=image_store.temp_url_path(pending["file"]) if pending else None,
        demo_mode=get_image_service().is_demo,
    )


@bp.route("/items/<int:item_id>/image/upload", methods=["POST"])
@admin_required
def item_image_upload(item_id):
    item = _get_or_404(item_id)
    upload = request.files.get("image")
    try:
        data = upload.read() if upload else b""
        extension = validate_image(upload.filename if upload else "", data)
    except ValidationError as error:
        _flash_errors(error)
    else:
        _set_pending(item.id, image_store.save_temp(data, upload.filename, extension), prompt=None)
        flash("Forhåndsvisning klar. Trykk «Lagre» for å bruke bildet.")
    return redirect(url_for("admin.item_image", item_id=item.id))


@bp.route("/items/<int:item_id>/image/generate", methods=["POST"])
@admin_required
def item_image_generate(item_id):
    item = _get_or_404(item_id)
    try:
        prompt = validate_prompt(request.form.get("prompt"))
        image = get_image_service().generate(prompt)
    except ValidationError as error:
        _flash_errors(error)
    else:
        _set_pending(item.id, image_store.save_temp(image.data, item.name, image.extension), prompt=prompt)
        flash("Bildet er laget. Trykk «Lagre» for å bruke det, eller «Avvis».")
    return redirect(url_for("admin.item_image", item_id=item.id))


@bp.route("/items/<int:item_id>/image/save", methods=["POST"])
@admin_required
def item_image_save(item_id):
    item = _get_or_404(item_id)
    pending = _pending_image(item.id)
    if pending is None:
        flash("Det er ikke noe nytt bilde å lagre.", "error")
        return redirect(url_for("admin.item_image", item_id=item.id))

    image_path = image_store.promote(pending["file"])
    prompt = pending["prompt"] if pending["prompt"] is not None else item.image_prompt
    food_item_repository().set_image(item.id, image_path, prompt)
    image_store.delete_saved(item.image_path)  # forrige opplastede bilde (aldri plassholderen)
    session.pop("pending_image", None)
    flash(f"Nytt bilde lagret for {item.name}.")
    return redirect(url_for("admin.item_image", item_id=item.id))


@bp.route("/items/<int:item_id>/image/cancel", methods=["POST"])
@admin_required
def item_image_cancel(item_id):
    """«Avbryt» (opplasting) eller «Avvis» (bildetjenesten): det gamle bildet blir stående."""
    item = _get_or_404(item_id)
    _clear_pending()
    flash("Det nye bildet ble forkastet. Det gamle bildet er beholdt.")
    return redirect(url_for("admin.item_image", item_id=item.id))


def _pending_image(item_id):
    """Ventende bilde for denne retten, ellers None. Ugyldige eller utdaterte rester ryddes bort."""
    pending = session.get("pending_image")
    if not pending:
        return None
    if pending.get("item_id") != item_id or not image_store.temp_exists(pending.get("file")):
        if pending.get("item_id") != item_id:
            return None  # hører til en annen rett; ryddes når den lagres/avbrytes eller blir gammel
        session.pop("pending_image", None)
        return None
    return pending


def _set_pending(item_id, temp_name, prompt):
    _clear_pending()  # bare ett ventende bilde om gangen
    session["pending_image"] = {"item_id": item_id, "file": temp_name, "prompt": prompt}


def _clear_pending():
    pending = session.pop("pending_image", None)
    if pending:
        image_store.discard(pending.get("file"))


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
