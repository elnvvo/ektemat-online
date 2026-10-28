# Plan: US-03 og US-04 – admin håndterer matretter (A1)

## Kontekst
Kundene ser menyen (US-01/02), og adminpanelet er beskyttet (US-20, `01ea2a3`), men det er bare en plassholder. Menyen endrer seg med sesongen, og kjøkkensjefen vil endre den selv (INT-M). US-03 (legge til, endre og fjerne retter) og US-04 (publisere og avpublisere) dekker krav A1. Bilder (US-05) er **utenfor scope**, så plassholderbildet beholdes.

Planen kopieres til `docs/plans/us-03-04-admin-items.md` som første steg etter godkjenning.

## Arkivering i stedet for sletting
- `schema.sql`: `food_items` får `archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))`. `FoodItem` får `archived: bool = False`. Jeg legger også `archived: bool` inn i klassediagrammet i `docs/design.md` §2, slik at dokumentasjonen stemmer med koden.
- «Fjern» setter `archived = 1` og `published = 0`. Raden og koblingene blir liggende, så `order_lines` (som peker på `food_items.id`) fortsatt kan vise hva som ble bestilt.
- `list_published` filtrerer også bort arkiverte retter (`archived = 0`), så de aldri vises på menyen.
- Arkiverte retter vises i en egen seksjon «Arkiverte retter» nederst i adminlisten, med knappen «Gjenopprett». Gjenopprettede retter er upubliserte til admin publiserer dem.
- Fordi skjemaet endres, må `python seed.py` kjøres på nytt (databasen lages da på nytt).

## Modell – validering i `FoodItem` (`app/models/food_item.py`)
`FoodItem.from_input(name, description, price, min_order_qty, published, event_categories, allergens, dietary_labels, id=None, image_path=None)` tar imot råverdier fra skjemaet og gjør dette:
- `name`: påkrevd («Navn må fylles ut.»)
- `price`: tolkes som `Decimal` (godtar komma, f.eks. «189,50»). Ugyldig tall gir «Pris må være et tall.», og negativt tall gir **«Pris kan ikke være negativ.»**
- `min_order_qty`: heltall. Under 1 gir **«Minimumsantall må være minst 1.»**
- `event_categories`: minst én («Velg minst én arrangementskategori.»), siden klassediagrammet har `suits 1..*`
- Kaster `ValidationError({felt: melding})` fra `app/models/errors.py` (finnes fra før). Meldingene nevner alltid feltet.

Controlleren gjør ingen validering. Den slår bare opp valgte kategorier, allergener og merker i katalogene fra repositoryet og sender dem videre.

## Repository – `FoodItemRepository`
Nye abstrakte metoder i `base.py`, implementert i `sqlite_food_item_repository.py` (gjenbruker `_with_relations` og `_to_food_item`):
- `get(item_id) -> FoodItem | None` (også arkiverte)
- `list_all() -> list[FoodItem]`: alle retter, også upubliserte og arkiverte, sortert på navn (admin)
- `update(item) -> FoodItem`: oppdaterer feltene og erstatter koblingene i én transaksjon
- `set_published(item_id, published)`, `archive(item_id)`, `restore(item_id)`
- `list_allergens()`, `list_dietary_labels()` (til avkrysningsboksene)
- `list_published`: legger til `AND f.archived = 0`

## Controller – `app/controllers/admin.py`
Alle rutene er allerede beskyttet av `before_request` + `@admin_required`. Jeg legger likevel `@admin_required` eksplisitt på hver rute også, som du ba om.

| Rute | Metode | Hva |
|---|---|---|
| `/admin/items` | GET | tabell over aktive retter + seksjon med arkiverte |
| `/admin/items/new` | GET, POST | skjema for ny rett |
| `/admin/items/<id>/edit` | GET, POST | skjema for å endre en rett |
| `/admin/items/<id>/publish` | POST | `published=1/0` – publiser/avpubliser direkte fra listen (US-04) |
| `/admin/items/<id>/archive` | POST | «Fjern» = arkiver (med `confirm()` i nettleseren) |
| `/admin/items/<id>/restore` | POST | gjenopprett arkivert rett |

- Ved valideringsfeil rendres skjemaet på nytt med status 400. Det viser verdiene som ble skrevet inn og meldingen ved feltet, og ingenting blir lagret.
- Når lagringen går bra: redirect til `/admin/items` med en flash-melding («Lagret: Fiskesuppe»).
- Ukjent id gir 404. Å endre en arkivert rett er lov (så den kan rettes før den gjenopprettes).
- Ved endring beholdes `image_path` som den er.

## Views
- `admin/items.html`: tabell med navn, pris (`nok`-filteret), minimumsantall, kategorier og status («Publisert»/«Ikke publisert»). Hver rad har knappene «Publiser»/«Avpubliser», «Endre» og «Fjern», og over tabellen er det en knapp for «Ny matrett». Tabellen ligger i en container med `overflow-x: auto`, så den fungerer på mobil.
- `admin/item_form.html`: brukes både for ny og endret rett. Feltene er navn, beskrivelse (textarea), pris, minimumsantall, avkrysningsbokser for kategorier, allergener og diettmerker (i `<fieldset>`) og publisert (avkrysningsboks). Feilmeldingene står ved feltene, med `aria-invalid`.
- `admin/index.html`: lenke til «Matretter».
- `style.css`: tabell, knapper i rader og fieldset med avkrysningsbokser.

## Tester – `tests/test_admin_items.py`
Fixtures: `admin_client` (innlogget admin) og katalogdata via repositoryet.

**US-03**
- `test_admin_creates_item_and_it_appears_in_list`: alle påkrevde felt gir 302, og retten vises på `/admin/items`
- `test_negative_price_is_rejected`: 400, meldingen nevner «Pris», og ingen ny rett lagres
- `test_min_order_below_one_is_rejected`: 0 gir 400, meldingen nevner «Minimumsantall», og ingenting lagres
- `test_validation_lives_in_model`: enhetstest av `FoodItem.from_input` direkte (ValidationError med feltnøkkelen)
- `test_admin_edits_item`: pris og kategorier endres
- `test_remove_archives_item_instead_of_deleting`: lager en ordre med en ordrelinje som peker på retten (direkte SQL i testen, siden OrderRepository ikke finnes ennå). Etter «Fjern» finnes retten fortsatt (`get` gir `archived=True`), ordrelinjen kan fortsatt kobles til navnet, og retten vises verken på `/menu` eller blant de aktive i adminlisten
- `test_admin_list_shows_unpublished_items`

**US-04**
- `test_publish_makes_item_visible_on_menu`: upublisert rett → POST publish → vises på `/menu`
- `test_unpublish_hides_item_from_menu`

**NFR-06** – `test_every_admin_route_requires_admin_role` i `test_auth.py` endres så den bruker rutens egen metode (POST for rutene som bare tar imot POST). Ellers gir Flask 405 før tilgangssjekken kjører. Da dekker testen automatisk alle de nye rutene.

## Verifisering
1. `pytest` → alle tester grønne
2. `python seed.py` og `flask run`: logg inn som admin (passordet fra `.env`) og åpne `/admin/items`. Der skal jeg legge til en rett, prøve negativ pris (melding), endre en rett, publisere rakfisk (vises på `/menu`) og fjerne en rett (borte fra menyen, synlig under «Arkiverte»). Hvis jeg ikke kjenner admin-passordet ditt, lager jeg i stedet en midlertidig database med et eget testpassord for denne sjekken.
3. `grep sqlite3` treffer bare `app/models/repositories/` (og testen som lager ordrelinjen)
4. Commit (når du ber om det) med en melding som nevner US-03 og US-04
