"""Konto: registrering, innlogging, mine bestillinger og spørsmål (UC3, UC5–UC7, UC12)."""
from flask import Blueprint, render_template

bp = Blueprint("account", __name__)


@bp.route("/login")
def login():
    return render_template("account/login.html")
