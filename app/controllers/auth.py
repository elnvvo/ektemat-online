"""Innlogget bruker og tilgangskontroll (US-20, NFR-06)."""
from functools import wraps

from flask import abort, g, redirect, request, session, url_for

from app.models.repositories import user_repository


def load_current_user():
    """Kjøres før hver request: setter g.user fra sesjonen (None hvis ikke innlogget)."""
    user_id = session.get("user_id")
    g.user = user_repository().get_by_id(user_id) if user_id is not None else None
    if user_id is not None and g.user is None:
        session.clear()


def is_safe_next(url):
    """Bare relative stier på dette nettstedet (hindrer open redirect)."""
    return url.startswith("/") and not url.startswith("//") and "\\" not in url


def _redirect_to_login():
    return redirect(url_for("account.login", next=request.full_path.rstrip("?")))


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return _redirect_to_login()
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Ikke innlogget → /login. Innlogget uten admin-rollen → 403."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return _redirect_to_login()
        if not g.user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped
