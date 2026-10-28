"""Validering av bilder til matretter (US-05)."""
from pathlib import PurePath

from app.models.errors import ValidationError

MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Filtype -> de første bytene i en ekte fil av den typen.
_SIGNATURES = {
    "png": b"\x89PNG\r\n\x1a\n",
    "jpg": b"\xff\xd8\xff",
}
_EXTENSIONS = {"png": "png", "jpg": "jpg", "jpeg": "jpg"}


def validate_image(filename, data):
    """Godtar bare JPG og PNG under 5 MB. Sjekker både filnavnet og innholdet.

    Returnerer filtypen ("png" eller "jpg"). Kaster ValidationError({"image": ...}).
    """
    if not data:
        raise ValidationError({"image": "Velg en bildefil."})
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError({"image": "Bildet er for stort (maks 5 MB)."})

    extension = _EXTENSIONS.get(PurePath(filename or "").suffix.lower().lstrip("."))
    if extension is None or not data.startswith(_SIGNATURES[extension]):
        raise ValidationError({"image": "Bare JPG- og PNG-bilder er tillatt."})
    return extension


def validate_prompt(prompt):
    """Bildeinstruksen til bildetjenesten: påkrevd, maks 1000 tegn."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValidationError({"prompt": "Skriv en bildeinstruks."})
    if len(prompt) > 1000:
        raise ValidationError({"prompt": "Bildeinstruksen kan ikke være lengre enn 1000 tegn."})
    return prompt


def detect_extension(data):
    """Filtypen ut fra innholdet, eller None (brukes for bilder fra bildetjenesten)."""
    for extension, signature in _SIGNATURES.items():
        if data.startswith(signature):
            return extension
    return None
