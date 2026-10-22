"""Kundesiden: meny, handlekurv og bestilling (UC1–UC4)."""
from flask import Blueprint, render_template

bp = Blueprint("shop", __name__)


@bp.route("/")
def index():
    return render_template("shop/index.html")
