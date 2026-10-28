"""Innstillinger lest fra miljøet (.env lastes med python-dotenv)."""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    # Sesjonscookien er HttpOnly som standard i Flask; Lax hindrer at den sendes med fra andre nettsteder.
    SESSION_COOKIE_SAMESITE = "Lax"
    # Relativ til app.instance_path; settes til full sti i create_app().
    DATABASE = "ektemat.sqlite"

    # US-05: opplastede bilder ligger under static, så de kan vises direkte.
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
    # Stopper store opplastinger før de leses inn; modellen sjekker selve grensen på 5 MB.
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    # Bildetjenesten. Uten nøkkel brukes DummyImageService (aldri nøkler i koden, NFR-03).
    IMAGE_API_KEY = os.environ.get("IMAGE_API_KEY") or None
    IMAGE_API_URL = os.environ.get("IMAGE_API_URL") or None
