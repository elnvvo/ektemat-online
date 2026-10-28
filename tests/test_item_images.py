"""Akseptansetester for US-05 (bilde på matretten: opplasting eller bildeinstruks, med forhåndsvisning)."""
import io
import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.errors import ValidationError
from app.models.food_item import FoodItem
from app.models.item_image import MAX_IMAGE_BYTES, validate_image
from app.models.repositories import food_item_repository
from app.services.image_service import ApiImageService, DummyImageService, get_image_service
from conftest import ADMIN_PASSWORD, login

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64


@pytest.fixture
def item(app):
    with app.app_context():
        repository = food_item_repository()
        category = repository.add_event_category("Julebord")
        return repository.add(
            FoodItem(
                None, "Fiskesuppe", "", Decimal("189"), 10, published=True,
                image_path="img/placeholder.svg", event_categories=[category],
            )
        )


@pytest.fixture
def admin_client(app, admin):
    client = app.test_client()
    login(client, admin.email, ADMIN_PASSWORD)
    return client


def upload(client, item, data, filename="suppe.png"):
    return client.post(
        f"/admin/items/{item.id}/image/upload",
        data={"image": (io.BytesIO(data), filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def generate(client, item, prompt):
    return client.post(
        f"/admin/items/{item.id}/image/generate", data={"prompt": prompt}, follow_redirects=True
    )


def save(client, item):
    return client.post(f"/admin/items/{item.id}/image/save", follow_redirects=True)


def cancel(client, item):
    return client.post(f"/admin/items/{item.id}/image/cancel", follow_redirects=True)


def stored(app, item):
    with app.app_context():
        return food_item_repository().get(item.id)


def uploads(app):
    return Path(app.config["UPLOAD_FOLDER"])


def temp_files(app):
    folder = uploads(app) / "tmp"
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def saved_files(app):
    return sorted(p.name for p in uploads(app).iterdir() if p.is_file()) if uploads(app).exists() else []


def preview_src(html):
    match = re.search(r'id="preview-heading".*?<img src="([^"]+)"', html, re.S)
    return match.group(1) if match else None


# Opplasting med forhåndsvisning

def test_upload_png_shows_preview_but_does_not_save(app, admin_client, item):
    response = upload(admin_client, item, PNG)

    html = response.get_data(as_text=True)
    [temp] = temp_files(app)
    assert preview_src(html) == f"/static/uploads/tmp/{temp}"
    assert "Lagre" in html and "Avbryt" in html
    assert stored(app, item).image_path == "img/placeholder.svg"


def test_save_stores_image_on_food_item_and_menu_shows_it(app, admin_client, item):
    upload(admin_client, item, PNG)
    [temp] = temp_files(app)

    response = save(admin_client, item)

    assert "Nytt bilde lagret for Fiskesuppe." in response.get_data(as_text=True)
    assert stored(app, item).image_path == f"uploads/{temp}"
    assert saved_files(app) == [temp]
    assert temp_files(app) == []
    assert f'src="/static/uploads/{temp}"' in admin_client.get("/menu").get_data(as_text=True)


def test_cancel_keeps_old_image_and_removes_temp_file(app, admin_client, item):
    upload(admin_client, item, PNG)

    response = cancel(admin_client, item)

    assert "Det gamle bildet er beholdt." in response.get_data(as_text=True)
    assert stored(app, item).image_path == "img/placeholder.svg"
    assert temp_files(app) == []
    assert preview_src(response.get_data(as_text=True)) is None


def test_upload_jpg_is_accepted(app, admin_client, item):
    upload(admin_client, item, JPG, "suppe.JPEG")
    [temp] = temp_files(app)
    assert temp.endswith("_suppe.jpg")


@pytest.mark.parametrize(
    ("data", "filename"),
    [(b"bare tekst", "notat.txt"), (b"bare tekst", "forkledd.png"), (PNG, "bilde.gif"), (GIF, "bilde.gif")],
)
def test_non_image_or_wrong_type_is_rejected(app, admin_client, item, data, filename):
    response = upload(admin_client, item, data, filename)

    assert "Bare JPG- og PNG-bilder er tillatt." in response.get_data(as_text=True)
    assert temp_files(app) == []
    assert stored(app, item).image_path == "img/placeholder.svg"


def test_file_over_5_mb_is_rejected(app, admin_client, item):
    response = upload(admin_client, item, PNG + b"\x00" * (MAX_IMAGE_BYTES + 1 - len(PNG)))

    assert "Bildet er for stort (maks 5 MB)." in response.get_data(as_text=True)
    assert temp_files(app) == []


def test_request_over_max_content_length_gives_message(app, admin_client, item):
    response = admin_client.post(
        f"/admin/items/{item.id}/image/upload",
        data={"image": (io.BytesIO(b"\x00" * (7 * 1024 * 1024)), "stor.png")},
        content_type="multipart/form-data",
        headers={"Referer": f"http://localhost/admin/items/{item.id}/image"},
    )
    assert response.status_code == 302
    assert response.headers["Location"] == f"/admin/items/{item.id}/image"


def test_filename_is_secure_and_unique(app, admin_client, item):
    upload(admin_client, item, PNG, "../../evil name.png")
    first = temp_files(app)
    upload(admin_client, item, PNG, "../../evil name.png")  # erstatter det første ventende bildet
    [second] = temp_files(app)

    assert re.fullmatch(r"[0-9a-f]{32}_evil_name\.png", first[0])
    assert re.fullmatch(r"[0-9a-f]{32}_evil_name\.png", second)
    assert first[0] != second
    assert not any(".." in p.name for p in uploads(app).rglob("*"))


# Bildeinstruks (bildetjenesten)

def test_prompt_generates_preview_with_dummy_service(app, admin_client, item):
    response = generate(admin_client, item, "Fiskesuppe i dyp tallerken, rustikt trebord")

    html = response.get_data(as_text=True)
    [temp] = temp_files(app)
    assert preview_src(html) == f"/static/uploads/tmp/{temp}"
    assert "Avvis" in html
    assert "Demo-modus" in html
    assert (uploads(app) / "tmp" / temp).read_bytes().startswith(b"\x89PNG")
    assert stored(app, item).image_prompt is None


def test_accept_generated_image_saves_path_and_prompt(app, admin_client, item):
    generate(admin_client, item, "Fiskesuppe, ovenfra")
    [temp] = temp_files(app)

    save(admin_client, item)

    saved = stored(app, item)
    assert saved.image_path == f"uploads/{temp}"
    assert saved.image_prompt == "Fiskesuppe, ovenfra"


def test_reject_generated_image_changes_nothing(app, admin_client, item):
    generate(admin_client, item, "Fiskesuppe, ovenfra")

    cancel(admin_client, item)

    saved = stored(app, item)
    assert saved.image_path == "img/placeholder.svg"
    assert saved.image_prompt is None
    assert temp_files(app) == []


@pytest.mark.parametrize("prompt", ["", "   "])
def test_empty_prompt_is_rejected(app, admin_client, item, prompt):
    response = generate(admin_client, item, prompt)

    assert "Skriv en bildeinstruks." in response.get_data(as_text=True)
    assert temp_files(app) == []


def test_dummy_images_differ_by_prompt():
    first = DummyImageService().generate("Fiskesuppe")
    second = DummyImageService().generate("Lam fra Voss")
    assert first.extension == "png"
    assert first.data.startswith(b"\x89PNG") and first.data != second.data


def test_get_image_service_uses_dummy_without_key(app):
    with app.app_context():
        assert isinstance(get_image_service(), DummyImageService)


def test_get_image_service_uses_api_with_key(app):
    app.config.update(IMAGE_API_KEY="test-nøkkel", IMAGE_API_URL="http://bilder.invalid/generate")
    with app.app_context():
        service = get_image_service()
    assert isinstance(service, ApiImageService)
    assert service.api_url == "http://bilder.invalid/generate"


def test_api_key_is_not_in_source_code():
    root = Path(__file__).resolve().parent.parent / "app"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"IMAGE_API_KEY\s*=\s*['\"][^'\"]+['\"]", text), path


# Lagring og opprydding

def test_save_replaces_and_deletes_previous_upload(app, admin_client, item):
    upload(admin_client, item, PNG, "forste.png")
    save(admin_client, item)
    first = stored(app, item).image_path

    upload(admin_client, item, JPG, "andre.jpg")
    save(admin_client, item)

    second = stored(app, item).image_path
    assert second != first and second.endswith("_andre.jpg")
    assert saved_files(app) == [second.removeprefix("uploads/")]


def test_placeholder_is_never_deleted(app, admin_client, item):
    placeholder = Path(app.static_folder) / "img" / "placeholder.svg"
    upload(admin_client, item, PNG)
    save(admin_client, item)
    assert placeholder.is_file()


def test_save_without_pending_image_does_nothing(app, admin_client, item):
    response = save(admin_client, item)

    assert "Det er ikke noe nytt bilde å lagre." in response.get_data(as_text=True)
    assert stored(app, item).image_path == "img/placeholder.svg"


def test_pending_image_belongs_to_one_item(app, admin_client, item):
    with app.app_context():
        other = food_item_repository().add(
            FoodItem(None, "Lam fra Voss", "", Decimal("245"), 10, event_categories=item.event_categories)
        )
    upload(admin_client, item, PNG)

    save(admin_client, other)

    assert stored(app, other).image_path is None
    assert stored(app, item).image_path == "img/placeholder.svg"


# Validering i modellen

def test_validate_image_unit():
    assert validate_image("a.png", PNG) == "png"
    assert validate_image("a.JPG", JPG) == "jpg"
    assert validate_image("a.jpeg", JPG) == "jpg"
    for filename, data in [("a.png", b""), ("a.png", JPG), ("a.jpg", PNG), ("a", PNG), (None, PNG)]:
        with pytest.raises(ValidationError):
            validate_image(filename, data)
