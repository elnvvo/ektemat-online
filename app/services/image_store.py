"""Lagring av bildefiler i UPLOAD_FOLDER (app/static/uploads). Ikke database (US-05).

Nye bilder lagres først i tmp/ til admin trykker «Lagre». Filnavnene er <uuid>_<secure_filename>.
"""
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

TEMP_DIR = "tmp"
_SAFE_NAME = re.compile(r"^[0-9a-f]{32}_[\w.-]+$")
_MAX_TEMP_AGE_SECONDS = 60 * 60


def save_temp(data, original_name, extension):
    """Lagrer et bilde midlertidig og returnerer filnavnet (ikke stien)."""
    cleanup_stale()
    stem = secure_filename(Path(original_name or "").stem)[:60] or "bilde"
    name = f"{uuid.uuid4().hex}_{stem}.{extension}"
    (_temp_dir() / name).write_bytes(data)
    return name


def temp_url_path(name):
    """Stien relativt til static, for url_for('static', ...)."""
    return f"uploads/{TEMP_DIR}/{name}"


def temp_exists(name):
    return _is_safe(name) and (_temp_dir() / name).is_file()


def promote(name):
    """Flytter et midlertidig bilde til uploads/ og returnerer image_path («uploads/<navn>»)."""
    if not temp_exists(name):
        raise FileNotFoundError(name)
    shutil.move(_temp_dir() / name, _upload_dir() / name)
    return f"uploads/{name}"


def discard(name):
    if name and temp_exists(name):
        (_temp_dir() / name).unlink()


def delete_saved(image_path):
    """Sletter et tidligere opplastet bilde. Rører aldri plassholderen eller noe utenfor uploads/."""
    if not image_path or not image_path.startswith("uploads/"):
        return
    name = image_path.removeprefix("uploads/")
    if _is_safe(name):
        path = _upload_dir() / name
        if path.is_file():
            path.unlink()


def cleanup_stale(max_age_seconds=_MAX_TEMP_AGE_SECONDS):
    """Sletter midlertidige bilder som er eldre enn max_age (forlatte forhåndsvisninger)."""
    cutoff = time.time() - max_age_seconds
    for path in _temp_dir().iterdir():
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()


def _is_safe(name):
    return bool(name) and _SAFE_NAME.match(name) is not None


def _upload_dir():
    path = Path(current_app.config["UPLOAD_FOLDER"])
    os.makedirs(path, exist_ok=True)
    return path


def _temp_dir():
    path = _upload_dir() / TEMP_DIR
    os.makedirs(path, exist_ok=True)
    return path
