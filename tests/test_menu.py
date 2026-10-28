"""Akseptansetester for US-01 (meny etter arrangement) og US-02 (allergener og diettmerker)."""
import re
from decimal import Decimal

import pytest

from app.models.food_item import Allergen, DietaryLabel, FoodItem
from app.models.repositories import food_item_repository


@pytest.fixture
def menu(app):
    """Syntetiske retter: to publiserte i ulike kategorier og én upublisert julebordrett."""
    with app.app_context():
        repository = food_item_repository()
        julebord = repository.add_event_category("Julebord")
        bursdag = repository.add_event_category("Bursdag")
        fish, gluten, milk = Allergen("fish", "Fisk"), Allergen("gluten", "Gluten"), Allergen("milk", "Melk")
        vegetarian = DietaryLabel("V", "Vegetar")
        for allergen in (fish, gluten, milk):
            repository.add_allergen(allergen)
        repository.add_dietary_label(vegetarian)

        repository.add(
            FoodItem(
                id=None,
                name="Lutefisk med bacon",
                description="Testrett",
                price_nok=Decimal("189"),
                min_order_qty=10,
                published=True,
                image_path="img/placeholder.svg",
                event_categories=[julebord],
                allergens=[fish, gluten],
            )
        )
        repository.add(
            FoodItem(
                id=None,
                name="Grønnsakslasagne",
                description="Testrett",
                price_nok=Decimal("165"),
                min_order_qty=12,
                published=True,
                image_path="img/placeholder.svg",
                event_categories=[bursdag],
                allergens=[gluten, milk],
                dietary_labels=[vegetarian],
            )
        )
        repository.add(
            FoodItem(
                id=None,
                name="Rakfisk",
                description="Sesongrett, ikke publisert",
                price_nok=Decimal("210"),
                min_order_qty=8,
                published=False,
                event_categories=[julebord],
                allergens=[fish],
            )
        )


def card(html, name):
    """Returnerer HTML-en til kortet som inneholder rettens navn."""
    for article in re.findall(r"<article class=\"card\">.*?</article>", html, re.S):
        if name in article:
            return article
    raise AssertionError(f"Fant ikke kort for {name!r}")


# US-01

def test_category_filter_shows_only_published_items_in_category(client, menu):
    html = client.get("/menu?category=Julebord").get_data(as_text=True)

    lutefisk = card(html, "Lutefisk med bacon")
    assert "<img" in lutefisk
    assert "189 kr" in lutefisk
    assert "Minimum 10 stk" in lutefisk
    assert "Grønnsakslasagne" not in html
    assert "Rakfisk" not in html


def test_unpublished_item_is_not_shown(client, menu):
    for url in ("/menu", "/menu?category=Julebord"):
        response = client.get(url)
        assert response.status_code == 200
        assert "Rakfisk" not in response.get_data(as_text=True)


def test_menu_without_filter_shows_all_published_items(client, menu):
    html = client.get("/menu").get_data(as_text=True)
    assert "Lutefisk med bacon" in html
    assert "Grønnsakslasagne" in html


def test_menu_lists_event_categories(client, menu):
    html = client.get("/menu").get_data(as_text=True)
    assert "/menu?category=Julebord" in html
    assert "/menu?category=Bursdag" in html


def test_unknown_category_shows_message(client, menu):
    html = client.get("/menu?category=Finnes-ikke").get_data(as_text=True)
    assert "Ingen retter i denne kategorien" in html


def test_list_published_filters_by_category(app, menu):
    with app.app_context():
        repository = food_item_repository()
        assert [item.name for item in repository.list_published("Julebord")] == ["Lutefisk med bacon"]
        assert {item.name for item in repository.list_published()} == {"Lutefisk med bacon", "Grønnsakslasagne"}


# US-02

def test_card_shows_allergens_fish_and_gluten(client, menu):
    html = client.get("/menu").get_data(as_text=True)
    lutefisk = card(html, "Lutefisk med bacon")
    assert "Fisk" in lutefisk
    assert "Gluten" in lutefisk


def test_vegetarian_label_shown(client, menu):
    html = client.get("/menu").get_data(as_text=True)
    lasagne = card(html, "Grønnsakslasagne")
    assert ">V</abbr>" in lasagne
    assert "Vegetar" in lasagne
    assert "Vegetar" not in card(html, "Lutefisk med bacon")
