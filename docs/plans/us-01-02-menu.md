# Plan: US-01 og US-02 – meny gruppert etter arrangement, med allergener og diettmerker

## Kontekst
Skjelettet (`a9edd07`) har tabellene for matretter i `schema.sql`, men ingen domeneklasser, ingen repository-metoder og ingen meny. US-01 (bla i menyen etter arrangement) og US-02 (allergener og diettmerker på kortet) er de første Must-storyene for kundesiden (C1). Handlekurv, innlogging og admin er **utenfor scope**.

Planen kopieres til `docs/plans/us-01-02-menu.md` som første steg etter godkjenning.

## Filer

```
app/models/food_item.py                          NY    domeneklasser
app/models/repositories/base.py                  ENDRE FoodItemRepository får abstrakte metoder
app/models/repositories/sqlite_food_item_repository.py  NY  SQLite-implementasjon
app/models/repositories/__init__.py              ENDRE food_item_repository() – eneste sted som velger implementasjon
app/controllers/shop.py                          ENDRE GET /menu
app/__init__.py                                  ENDRE Jinja-filter «nok» (189 → «189 kr», 5670 → «5 670 kr»)
app/templates/shop/menu.html                     NY    filterlenker + kortrutenett
app/templates/shop/index.html, base.html         ENDRE lenke til /menu («Meny» i navigasjonen)
app/static/css/style.css                         ENDRE kort, rutenett og merker (fungerer på 360 px)
app/static/img/placeholder.svg                   NY    eget enkelt SVG-plassholderbilde (ingen ekstern kilde)
seed.py                                          ENDRE kategorier, allergener, diettmerker, 4 retter
tests/test_menu.py                               NY    akseptansetester US-01 og US-02
```

## Domeneklasser – `app/models/food_item.py`
Dataklasser etter klassediagrammet i design.md §2:
- `EventCategory(id, name)`
- `Allergen(code, name)` og `DietaryLabel(code, name)`
- `FoodItem(id, name, description, price_nok: Decimal, min_order_qty, published, image_path, image_prompt, origin, event_categories: list, allergens: list, dietary_labels: list)`

Ingen databasekode her.

## Repository
`base.py` – `FoodItemRepository` får disse abstrakte metodene:
- `list_published(category_name=None) -> list[FoodItem]`: bare `published = 1`, filtrert på kategori hvis den er gitt, sortert på navn, med kategorier, allergener og diettmerker fylt inn
- `list_event_categories() -> list[EventCategory]`
- `add(item) -> FoodItem`, `add_event_category(name) -> EventCategory`, `add_allergen(allergen)`, `add_dietary_label(label)`: brukes av seed og tester nå, og av admin i US-03 senere

`sqlite_food_item_repository.py` – `SqliteFoodItemRepository(FoodItemRepository)` bruker `get_db()` fra `sqlite_connection.py`. Én spørring henter rettene, og tre spørringer mot koblingstabellene fyller inn listene (unngår N+1). Pris leses som `Decimal`.

`repositories/__init__.py` – `food_item_repository()` returnerer `SqliteFoodItemRepository()`. Controllerne kaller bare denne, så Neo4j kan byttes inn i Oblig 5 på ett sted (NFR-02).

## Controller og view
`shop.py` – `GET /menu?category=<navn>`: henter `list_event_categories()` og `list_published(category)` og rendrer `shop/menu.html`. Ukjent kategori gir tom liste med meldingen «Ingen retter i denne kategorien». `/` beholdes som forside med lenke til menyen.

`shop/menu.html`:
- Filterlenker: «Alle» + én per kategori; den valgte er markert (`aria-current`)
- Ett `<article class="card">` per rett med bilde (`image_path` eller plassholder, `alt` = navn), navn, beskrivelse, pris («189 kr»), «Minimum 10 stk», allergener («Inneholder: Fisk, Melk») og diettmerker som merke med kode og fullt navn (`V` · «Vegetar»), synlig uten å åpne kortet (US-02)

## Seed-data (syntetisk)
- **Kategorier:** Bryllup, Konfirmasjon, Bursdag, Konferanse, Julebord
- **Allergener** (fra høstmenyen): fish/Fisk, milk/Melk, gluten/Gluten, nuts/Nøtter, celery/Selleri, mustard/Sennep
- **Diettmerker:** V/Vegetar, VG/Vegan, GF/Glutenfri

| Rett | Pris | Min. | Allergener | Diett | Kategorier | Publisert |
|---|---|---|---|---|---|---|
| Fiskesuppe | 189 | 10 | fisk, melk, selleri | – | Konferanse, Konfirmasjon, Julebord | ja |
| Lam fra Voss (origin «Voss») | 245 | 10 | selleri, sennep | GF | Bryllup, Konfirmasjon, Julebord | ja |
| Rødbete- og kikertsalat | 165 | 10 | sennep | V | Bryllup, Konfirmasjon, Bursdag, Konferanse | ja |
| Rakfisk | 210 | 8 | fisk, gluten, melk (lefse og rømme) | – | Julebord | **nei** |

Rakfisk seedes som **ikke publisert** fordi menyen sier «seasonal, Nov only». Dette viser samtidig akseptansekriteriet om upubliserte retter. Alle rettene bruker `img/placeholder.svg`. Seed går gjennom `food_item_repository()` og skriver ikke SQL selv.

## Tester – `tests/test_menu.py`
Testene lager egne data gjennom repositoryet i en fixture, så de ikke avhenger av seed.py:
- **US-01** `test_category_filter_shows_only_published_items_in_category`: `/menu?category=Julebord` viser de publiserte julebordrettene med bilde (`<img`), pris i NOK og minimumsantall, og viser ikke retter fra andre kategorier
- **US-01** `test_unpublished_item_is_not_shown`: en upublisert rett vises verken på `/menu` eller med kategorifilter
- **US-01** `test_menu_lists_event_categories`: alle kategoriene vises som filterlenker
- **US-02** `test_card_shows_allergens_fish_and_gluten`: kortet viser «Fisk» og «Gluten»
- **US-02** `test_vegetarian_label_shown`: kortet viser «V» / «Vegetar»
- `test_list_published_filters_by_category`: enhetstest av repositoryet

## Verifisering
1. `pytest` → alle tester grønne (smoketest + nye)
2. `python seed.py` (krever `.env`) og så `flask run` → åpne `/menu` i nettleservinduet. Sjekk tre kort (ikke rakfisk), filteret «Julebord» (fiskesuppe + lam) og visningen på 360 px bredde
3. `grep sqlite3` treffer bare `app/models/repositories/`
4. Commit (når du ber om det) med en melding som nevner US-01 og US-02
