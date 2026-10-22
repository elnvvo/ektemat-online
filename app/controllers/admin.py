"""Adminpanel: matretter, bestillinger og spørsmål (UC8–UC11).

Tilgangskontroll (@admin_required) kommer med US-20.
"""
from flask import Blueprint, render_template

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/", strict_slashes=False)
def index():
    return render_template("admin/index.html")
