"""Konto: registrering, innlogging, mine bestillinger og spørsmål (UC3, UC5–UC7, UC12)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.controllers.auth import is_safe_next, login_required
from app.models.errors import DuplicateEmailError, ValidationError
from app.models.repositories import order_repository, user_repository
from app.models.user import User

bp = Blueprint("account", __name__)

LOGIN_FAILED = "Feil e-post eller passord."

# Sjekkes mot når e-posten ikke finnes, så svartiden ikke avslører om kontoen finnes.
_DUMMY_HASH = generate_password_hash("ikke-et-ekte-passord")


@bp.route("/register", methods=["GET", "POST"])
def register():
    """US-19: ny kunde med e-post og passord (minst 8 tegn)."""
    form = {"name": "", "email": ""}
    errors = {}
    if request.method == "POST":
        form = {"name": request.form.get("name", ""), "email": request.form.get("email", "")}
        try:
            user = User.register(form["email"], form["name"], request.form.get("password", ""))
            user = user_repository().add(user)
        except ValidationError as error:
            errors = error.messages
        except DuplicateEmailError:
            errors = {"email": "Det finnes allerede en konto med denne e-postadressen."}
        else:
            _start_session(user)
            flash(f"Velkommen, {user.name}! Kontoen din er opprettet.")
            return redirect(url_for("shop.menu"))

    status = 400 if errors else 200
    return render_template("account/register.html", form=form, errors=errors), status


@bp.route("/login", methods=["GET", "POST"])
def login():
    """US-19: samme generelle feilmelding for ukjent e-post og feil passord."""
    email = ""
    error = None
    next_url = request.values.get("next", "")
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        user = user_repository().get_by_email(email)
        if user is None:
            check_password_hash(_DUMMY_HASH, password)
            error = LOGIN_FAILED
        elif not user.check_password(password):
            error = LOGIN_FAILED
        else:
            _start_session(user)
            flash(f"Du er logget inn som {user.name}.")
            return redirect(next_url if is_safe_next(next_url) else url_for("shop.menu"))

    status = 401 if error else 200
    return (
        render_template("account/login.html", email=email, error=error, next_url=next_url),
        status,
    )


@bp.route("/orders")
@login_required
def orders():
    """US-11: den innloggede kundens egne bestillinger, sortert etter arrangementsdato."""
    return render_template(
        "account/orders.html", orders=order_repository().list_for_user(g.user.id)
    )


@bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    """US-10: bekreftelse og detaljer. Bare kundens egne bestillinger (NFR-06)."""
    order = order_repository().get_for_user(order_id, g.user.id)
    if order is None:
        abort(404)  # samme svar om ordren ikke finnes eller tilhører en annen
    return render_template("account/order_detail.html", order=order)


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Du er logget ut.")
    return redirect(url_for("shop.index"))


def _start_session(user):
    """Ny session ved innlogging (hindrer session fixation), men handlekurven beholdes."""
    cart = session.get("cart")
    session.clear()
    session["user_id"] = user.id
    if cart:
        session["cart"] = cart
