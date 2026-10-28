"""Bildetjeneste for matretter (US-05).

Uten IMAGE_API_KEY i .env brukes DummyImageService, som lager et enkelt PNG lokalt,
så appen virker uten nøkkel. Nøkkelen leses bare fra miljøet (NFR-03).
"""
import hashlib
import json
import struct
import urllib.error
import urllib.request
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass

from flask import current_app

from app.models.errors import ValidationError
from app.models.item_image import MAX_IMAGE_BYTES, detect_extension


@dataclass
class GeneratedImage:
    data: bytes
    extension: str  # "png" eller "jpg"


class ImageService(ABC):
    is_demo = False

    @abstractmethod
    def generate(self, prompt: str, current_image: bytes | None = None) -> GeneratedImage:
        """Lager (eller endrer) et bilde ut fra en instruks."""


class DummyImageService(ImageService):
    """Lokalt plassholderbilde: fargen avhenger av instruksen."""

    is_demo = True
    WIDTH, HEIGHT = 400, 300

    def generate(self, prompt, current_image=None):
        digest = hashlib.sha256(prompt.encode("utf-8")).digest()
        return GeneratedImage(_striped_png(self.WIDTH, self.HEIGHT, digest[:3], digest[3:6]), "png")


class ApiImageService(ImageService):
    """Generisk HTTP-tjeneste. Må tilpasses leverandøren dere velger.

    POST {"prompt": ...} til IMAGE_API_URL med «Authorization: Bearer <IMAGE_API_KEY>»;
    svaret forventes å være selve bildet (PNG eller JPG).
    """

    TIMEOUT_SECONDS = 30

    def __init__(self, api_key, api_url):
        self.api_key = api_key
        self.api_url = api_url

    def generate(self, prompt, current_image=None):
        if not self.api_url:
            raise ValidationError({"prompt": "IMAGE_API_URL mangler i .env."})
        request = urllib.request.Request(
            self.api_url,
            data=json.dumps({"prompt": prompt}).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.TIMEOUT_SECONDS) as response:
                data = response.read(MAX_IMAGE_BYTES + 1)
        except (urllib.error.URLError, TimeoutError) as error:
            raise ValidationError(
                {"prompt": "Bildetjenesten svarte ikke. Prøv igjen eller last opp et bilde."}
            ) from error
        extension = detect_extension(data)
        if extension is None or len(data) > MAX_IMAGE_BYTES:
            raise ValidationError({"prompt": "Bildetjenesten ga ikke et gyldig JPG- eller PNG-bilde."})
        return GeneratedImage(data, extension)


def get_image_service():
    """DummyImageService uten nøkkel, ellers ApiImageService."""
    api_key = current_app.config.get("IMAGE_API_KEY")
    if not api_key:
        return DummyImageService()
    return ApiImageService(api_key, current_app.config.get("IMAGE_API_URL"))


def _striped_png(width, height, color_a, color_b):
    """Et gyldig PNG (RGB) med diagonale striper, laget uten eksterne pakker."""
    rows = []
    for y in range(height):
        row = bytearray(b"\x00")  # filtertype 0 for hver rad
        for x in range(width):
            row += color_a if ((x + y) // 40) % 2 == 0 else color_b
        rows.append(bytes(row))

    def chunk(kind, payload):
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )
