# Plan: Flask-skjelett for Ekte Mat Online

## Kontekst
Repoet har bare dokumentasjon (`docs/backlog.md`, `docs/design.md`), `CLAUDE.md`, en tom `README.md` og en `requirements.txt` med bare Flask. Før vi kan implementere user stories trenger vi et kjørbart MVC-skjelett som følger mappestrukturen i design.md §6, og som oppfyller NFR-02 (bare repository-laget rører databasen), NFR-03 (ingen hemmeligheter i koden, `.env` ignoreres) og NFR-09 (README med kommandoer, pytest). **Ingen user stories implementeres** – sidene er plassholdere.

Planen kopieres til `docs/plans/flask-skeleton.md` som første steg etter godkjenning (regel i CLAUDE.md).

## Filer som lages / endres

```
.env.example                        NY   SECRET_KEY=, SEED_ADMIN_PASSWORD=, SEED_CUSTOMER_PASSWORD= (tomme/plassholdere)
pytest.ini                          NY   pythonpath = . , testpaths = tests
requirements.txt                    ENDRE  + python-dotenv, pytest (låste versjoner)
README.md                           ENDRE  install / seed / run / test for Windows og Mac
seed.py                             NY
app/__init__.py                     NY   create_app(test_config=None)
app/config.py                       NY   leser .env via python-dotenv
app/controllers/__init__.py         NY
app/controllers/shop.py             NY   blueprint "shop",    GET /       -> shop/index.html
app/controllers/account.py          NY   blueprint "account", GET /login  -> account/login.html
app/controllers/admin.py            NY   blueprint "admin",   GET /admin  -> admin/index.html (url_prefix="/admin")
app/models/__init__.py              NY   (tom – domeneklasser kommer per story)
app/models/repositories/__init__.py NY
app/models/repositories/base.py     NY   tomme grensesnitt
app/models/repositories/sqlite_connection.py NY  SQLite-tilkobling + skjema
app/models/repositories/schema.sql  NY   tabeller
app/templates/base.html             NY   felles layout, nav (Meny / Logg inn / Admin), viewport-meta
app/templates/shop/index.html       NY
app/templates/account/login.html    NY   bare tekst, ikke skjema (US-19 kommer senere)
app/templates/admin/index.html      NY
app/static/css/style.css            NY   enkel, mobilvennlig CSS (NFR-08)
tests/conftest.py                   NY   app- og client-fixtures med midlertidig database
tests/test_smoke.py                 NY   forsiden svarer 200
```

## Detaljer

**`app/config.py`** – `load_dotenv()` og så en `Config`-klasse: `SECRET_KEY = os.environ.get("SECRET_KEY")`, `DATABASE` = `instance/ektemat.sqlite` (mappen `instance/` er allerede i `.gitignore`).

**`app/__init__.py` – `create_app(test_config=None)`**
- `Flask(__name__, instance_relative_config=True)`, laster `Config`, så `test_config` hvis den finnes.
- Stopper med en tydelig feilmelding hvis `SECRET_KEY` mangler (ingen innebygd fallback-nøkkel i koden).
- Lager `instance/`-mappen, kaller `sqlite_connection.init_app(app)` (registrerer teardown som lukker tilkoblingen) og registrerer de tre blueprintene.
- `flask run` finner `create_app` automatisk i pakken `app`, så vi trenger ikke `FLASK_APP`.

**Repository-laget (NFR-02)**
- `base.py`: abstrakte klasser (`abc.ABC`) `UserRepository`, `FoodItemRepository`, `OrderRepository` og `QuestionRepository` med docstring og ingen metoder ennå. Metodene (`get_by_ids`, `save`, `get_for_user`, …) legges til sammen med storyene som trenger dem.
- `sqlite_connection.py`: `get_db()` (én `sqlite3`-tilkobling per request i `flask.g`, `row_factory = sqlite3.Row`, `PRAGMA foreign_keys = ON`), `close_db()`, `init_db()` (kjører `schema.sql`) og `init_app(app)`. Tilkoblingen ligger i egen fil og ikke i `base.py`, slik at `base.py` bare har grensesnitt og kan gjenbrukes av Neo4j-implementasjonen i Oblig 5. Dette er det eneste stedet `sqlite3` importeres.
- `schema.sql`: tabellene fra klassediagrammet i design.md §2: `users` (email UNIQUE, name, phone, password_hash, role CHECK IN ('customer','admin')), `event_categories`, `allergens`, `dietary_labels`, `food_items` med koblingstabeller, `orders` (status og payment_status med CHECK), `order_lines` (unit_price_nok), `guest_groups` (size, notes, **ingen navnefelt**, NFR-04) med koblingstabeller mot allergener/dietter, `questions` og `answers`. Cart lagres ikke (ligger i sesjonen). `DROP TABLE IF EXISTS` øverst, så seed kan kjøres på nytt.

**`seed.py`** – `create_app()` → `app.app_context()` → `init_db()`, og så setter den inn én admin (`admin@ektemat.test`) og to testkunder (`kunde1@example.test`, `kunde2@example.test`, oppdiktede navn). Passord hashes med `werkzeug.security.generate_password_hash` (NFR-03). Passordene leses fra `SEED_ADMIN_PASSWORD` og `SEED_CUSTOMER_PASSWORD` i `.env`, og scriptet stopper med en melding hvis de mangler. Det skriver ut hva som ble opprettet. Innsettingen går gjennom en liten funksjon i repository-laget (`sqlite_connection`/en `add_user`-hjelper), så `seed.py` ikke skriver SQL selv.

**Tester** – `conftest.py`: en `app`-fixture med `create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": tmp_path/"test.sqlite"})` og `init_db()`, og en `client`-fixture. `test_smoke.py`: `client.get("/")` gir status 200. Ingen US-ID, fordi testen ikke dekker noen story.

**requirements.txt** – beholder de låste Flask-avhengighetene og legger til `python-dotenv` og `pytest` med eksakte versjoner fra `pip install` i `.venv`.

**README.md** – kort beskrivelse, så seksjoner for Windows og Mac: venv, aktivering, `pip install -r requirements.txt`, kopiering av `.env.example` til `.env` (`copy` / `cp`) og utfylling, `python seed.py`, `flask run` og `pytest`. Og en kort oversikt over mappestrukturen.

## Utenfor scope
Innlogging, `@admin_required`, domeneklasser, matretter i seed-data, `services/` og `static/js|uploads`. Det kommer med de enkelte storyene. Siden `/admin` er åpen inntil US-20.

## Verifisering
1. `pip install -r requirements.txt` i `.venv`
2. Opprett `.env` fra `.env.example` med testverdier, og kjør `python seed.py` → skriver ut 1 admin + 2 kunder
3. `flask run` → åpne `/`, `/login` og `/admin` i nettleservinduet og sjekk at alle gir 200 og bruker base.html
4. `pytest` → 1 passed
5. `git status` → `.env` og `instance/` vises ikke, og `grep sqlite3` treffer bare `app/models/repositories/`
6. Ingen commit uten at du ber om det
