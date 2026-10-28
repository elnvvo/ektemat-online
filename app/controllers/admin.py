"""Adminpanel: matretter, bestillinger og spørsmål (UC8–UC11).

Alle ruter i denne blueprinten krever admin-rollen (US-20, NFR-06).
"""
from flask import Blueprint, render_template

from app.controllers.auth import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@admin_required
def require_admin():
    """Kjøres før hver /admin-rute. Returnerer None (fortsett) bare for admin."""


@bp.route("/", strict_slashes=False)
def index():
    return render_template("admin/index.html")
