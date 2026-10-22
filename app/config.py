"""Innstillinger lest fra miljøet (.env lastes med python-dotenv)."""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    # Relativ til app.instance_path; settes til full sti i create_app().
    DATABASE = "ektemat.sqlite"
