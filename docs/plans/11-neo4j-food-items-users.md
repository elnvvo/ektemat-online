# Plan 11: Neo4j (AuraDB) som lagring for matretter og brukere (Oblig 5, steg 1)

## Kontekst
Repository-laget ble laget for å kunne bytte SQLite med Neo4j uten å endre controllere, views eller domeneklasser (design.md §6, NFR-02). Første steg i Oblig 5 er å flytte **matretter** (med kategorier, allergener og diettmerker) og **brukere** til Neo4j AuraDB, etter grafmodellen i design.md §7. Hvilken lagring som brukes, styres av `STORAGE` i `.env`, og SQLite er standard. Bestillinger og spørsmål er **utenfor scope** i dette steget. Arbeidet skjer på branchen `neo4j`.

Planen er lagret som `docs/plans/11-neo4j-food-items-users.md`, etter regelen i CLAUDE.md.

## Filer

```
requirements.txt                                    ENDRE  + neo4j (eksakt versjon fra pip)
.env.example                                        ENDRE  STORAGE=sqlite, NEO4J_URI=, NEO4J_USERNAME=, NEO4J_PASSWORD=, NEO4J_DATABASE=
app/config.py                                       ENDRE  STORAGE og NEO4J_* fra .env
app/__init__.py                                     ENDRE  sjekker STORAGE, kobler til riktig lagring, feilsider for lagringsfeil
app/models/repositories/__init__.py                 ENDRE  fabrikkene velger implementasjon etter STORAGE; init_storage()
app/models/repositories/neo4j_connection.py         NY     driver, run_read/run_write, constraints, reset_database, next_id
app/models/repositories/neo4j_food_item_repository.py NY   Neo4jFoodItemRepository(FoodItemRepository)
app/models/repositories/neo4j_user_repository.py    NY     Neo4jUserRepository(UserRepository)
app/models/repositories/not_migrated.py             NY     plassholdere for ordre/spørsmål i Neo4j-modus (se under)
app/templates/errors/storage.html                   NY     felles feilside for lagringen (ny fil, ingen eksisterende maler endres)
seed.py                                             ENDRE  init_storage() i stedet for SQLite-spesifikk init_db; bekreftelse før Neo4j slettes
pytest.ini                                          ENDRE  markøren «neo4j», som er av som standard
tests/conftest.py                                   ENDRE  STORAGE="sqlite" i test-appen (uansett hva .env sier)
tests/test_storage.py                               NY     valg av lagring + sjekk av at Cypher bruker parametere (kjører alltid, uten nettverk)
tests/test_neo4j_repositories.py                    NY     få Neo4j-tester, bare med «pytest -m neo4j»
README.md, CLAUDE.md                                ENDRE  hvordan man kjører med Neo4j
docs/design.md §7                                   ENDRE  id-egenskapene vises i grafmodellen
```

**Ingen endringer i controllere, eksisterende templates eller domeneklasser.** Det eneste nye i `app/templates/` er én feilside (se «Det du må vite» nederst).

## Valg av lagring – `STORAGE`
- `Config.STORAGE = os.environ.get("STORAGE", "sqlite").lower()`. `create_app()` stopper med en tydelig feil hvis verdien ikke er `sqlite` eller `neo4j`.
- Med `neo4j` krever `create_app()` at `NEO4J_URI`, `NEO4J_USERNAME` og `NEO4J_PASSWORD` finnes. Driveren lages én gang (`GraphDatabase.driver(...)`), legges i `app.extensions["neo4j"]` og lukkes når prosessen avsluttes. `NEO4J_DATABASE` er valgfri; uten den brukes standarddatabasen.
- Fabrikkene i `repositories/__init__.py` (`food_item_repository()`, `user_repository()`, …) leser `current_app.config["STORAGE"]` og returnerer SQLite- eller Neo4j-klassen. Controllerne kaller de samme fabrikkene som før.
- SQLite brukes fortsatt for ordre og spørsmål, også i Neo4j-modus (se under).

## Grafmodell (design.md §7) og id-er
```
(:FoodItem {id, name, description, price_nok, min_order_qty, published, archived, image_path, image_prompt, origin})
   -[:SUITS]->(:EventCategory {id, name})
   -[:CONTAINS_ALLERGEN]->(:Allergen {code, name})
   -[:HAS_LABEL]->(:DietaryLabel {code, name})
(:User {id, email, name, phone, password_hash, role})
(:Sequence {name, value})      teller som gir nye heltalls-id-er
```
- **Egne id-er, ikke Neo4js interne id-er.** `FoodItem.id`, `User.id` og `EventCategory.id` er heltall fra en teller: `MERGE (s:Sequence {name: $name}) ON CREATE SET s.value = 0 SET s.value = s.value + 1 RETURN s.value`, i samme skrivetransaksjon som noden lages. Heltall trengs fordi URL-ene bruker `<int:item_id>` og sessionen lagrer bruker-id-en.
- **Unikhets-constraints** (`CREATE CONSTRAINT … IF NOT EXISTS`): `User.email` og `FoodItem.id`, som du ba om, og i tillegg `User.id`, `EventCategory.id`, `EventCategory.name`, `Allergen.code`, `DietaryLabel.code` og `Sequence.name`.
- **Pris** lagres som tekst (`"189"`, `"189.50"`). Neo4j har ikke desimaltall, og flyttall kan gi avrundingsfeil i kroner. Den leses tilbake som `Decimal`.
- Allergener, diettmerker og kategorier er **delte noder**. Rettene peker på dem og har ingen egne kopier.

## Repositoryene
**`neo4j_connection.py`**
- `get_driver()`, `run_read(query, **params)` og `run_write(query, **params)` bruker `driver.execute_query(..., database_=…, routing_=READ/WRITE)`.
- `write_transaction(fn)` brukes når flere spørringer må gå samlet.
- `ensure_constraints()`, `reset_database()` (`MATCH (n) DETACH DELETE n` og så constraints) og `next_id(tx, name)`.
- **Alle verdier sendes som parametere (`$navn`).** Ingen verdi settes inn i Cypher-teksten, og en test sjekker dette.

**`Neo4jFoodItemRepository`** implementerer alle metodene i `FoodItemRepository` (`base.py`):
- `list_published`, `list_all`, `get` og `get_by_ids` bruker én spørring hver, med mønsterforståelse (`[(f)-[:SUITS]->(c) | c {.id, .name}]` osv.), så det blir ingen N+1. Sorteringen er den samme som i SQLite (navn, kategori, allergen og kode), så sidene ser like ut.
- `list_published(category_name)`: `WHERE f.published AND NOT f.archived AND ($category IS NULL OR EXISTS { (f)-[:SUITS]->(:EventCategory {name: $category}) })`
- `add` og `update` lager eller erstatter relasjonene med `UNWIND $category_ids … MATCH … MERGE`, i én transaksjon.
- `set_published`, `archive`, `restore` og `set_image` setter egenskaper på `FoodItem`.
- `add_event_category`, `add_allergen` og `add_dietary_label`, og `list_*` for katalogene

**`Neo4jUserRepository`**: `get_by_id`, `get_by_email` (normalisert e-post, som i SQLite) og `add`. `ConstraintError` på e-post blir `DuplicateEmailError`, som før.

## Ordre og spørsmål i Neo4j-modus
Ordre og spørsmål blir i SQLite i dette steget. Der peker de med fremmednøkler på `users` og `food_items`, og ordrelinjene henter navnet på retten med en join mot `food_items`. **I Neo4j-modus finnes ikke brukerne og rettene i SQLite**, så å lagre en ordre ville feile på fremmednøkkelen, og ordresidene ville mangle navn.

Derfor returnerer fabrikkene i Neo4j-modus foreløpig **plassholder-repositoryer** (`not_migrated.py`):
- **Lesing** gir tomme svar: lister blir `[]`, `count_unanswered()` blir 0, og `get…` gir `None`, som blir 404. «Mine bestillinger», admin-ordrelisten og admin-menyen virker da, men viser ingenting.
- **Skriving** (`save`, `add`, `update_status`, `save_answer`) kaster `StorageNotMigratedError`. `create_app` viser den på `errors/storage.html` med statuskode 501: «Bestillinger og spørsmål er ikke flyttet til Neo4j ennå. Kjør med STORAGE=sqlite for å bestille.»

Meny, handlekurv, registrering, innlogging og admin for matretter og bilder virker fullt ut med Neo4j. Neste steg er `Neo4jOrderRepository` og `Neo4jQuestionRepository`, med relasjonene `PLACED`, `CONTAINS`, `HAS_GUEST_GROUP`, `ASKED`, `ABOUT` og `ANSWERS` fra §7, og da forsvinner plassholderne.

## seed.py
- `init_storage()` i `repositories/__init__.py` kaller enten `sqlite_connection.init_db()` eller `neo4j_connection.reset_database()`. Etter det fyller `seed.py` lagringen med de samme repository-kallene som i dag (brukere, katalog og høstmenyen). Dermed fyller `seed.py` den lagringen `STORAGE` peker på.
- **Neo4j:** før alt slettes, skriver `seed.py` hvilken database den skal tømme (`NEO4J_URI`, uten passord) og ber deg skrive `ja`. `python seed.py --yes` hopper over spørsmålet. Databasen er delt i gruppen, så det er tryggere at den ikke kan tømmes ved et uhell.
- SQLite fungerer som før.

## Tester
- **Standard (`pytest`)**: test-appen setter alltid `STORAGE="sqlite"`, så `.env` med `STORAGE=neo4j` aldri gjør at testene rører Aura. `pytest.ini` får `markers = neo4j: …` og `addopts = -m "not neo4j"`. Alle de 166 testene som finnes, kjører uendret.
- **`tests/test_storage.py`** (kjører alltid, uten nettverk):
  - `STORAGE=neo4j` gir Neo4j-klassene, og `sqlite` eller ingen verdi gir SQLite-klassene. Driveren kobler ikke til før første spørring, så det trengs ingen database.
  - Ugyldig `STORAGE` stopper `create_app()`.
  - Neo4j-modus uten `NEO4J_URI` stopper med en tydelig melding.
  - Ingen f-strenger eller `+`/`%`/`.format` brukes til å bygge Cypher i `neo4j_*.py`, så alt går via parametere.
  - Plassholderne for ordre og spørsmål gir tomme svar ved lesing og 501 ved skriving.
- **`tests/test_neo4j_repositories.py`** (bare med `pytest -m neo4j`, og hoppes over hvis `NEO4J_URI` mangler):
  - Alt som lages, får unike navn for testkjøringen (f.eks. `test-<uuid>`). Etterpå slettes **bare** disse nodene (`DETACH DELETE` på deres id-er og koder) i en `finally`/fixture-teardown. `reset_database()` brukes aldri. Tellerne i `Sequence` går bare videre, og det er ufarlig.
  - Testene dekker: `add` og `get` med alle relasjoner, `list_published` med filtrering på kategori og uten upubliserte og arkiverte retter, at `update` erstatter relasjonene, `set_published`, `archive`, `restore`, `set_image` og `get_by_ids`, brukere (`add`, `get_by_email`, `get_by_id`, dobbel e-post gir `DuplicateEmailError`) og en kategori som `' OR 1=1 //`, som ikke treffer noe (parametere).

## README.md og CLAUDE.md
- En ny del, «Kjøre med Neo4j (AuraDB)»: lag en Aura-instans og kopier tilkoblingsdataene til `.env` (`STORAGE=neo4j` og `NEO4J_*`), kjør `python seed.py` (som tømmer Aura-databasen), `flask run`, og `pytest -m neo4j` for Neo4j-testene. Det står også hva som ikke er flyttet ennå.
- I CLAUDE.md: en kort regel om `STORAGE`, at `pytest` alltid bruker SQLite, og at Cypher alltid bruker parametere.

## Det du må vite
- **Ny mal: `app/templates/errors/storage.html`.** Ingen eksisterende maler endres, men det trengs én ny feilside. Den viser meldingen «ikke flyttet ennå» (501) og «databasen svarer ikke» (503, f.eks. hvis Aura-instansen er satt på pause, som gratisversjonen gjør etter en tid uten bruk) i stedet for en kodefeil.
- **Ordre og spørsmål virker ikke med `STORAGE=neo4j` før neste steg**, som beskrevet over.
- **`seed.py` med Neo4j tømmer hele den delte Aura-databasen.** Det er det du ba om, men med en bekreftelse først.

## Verifisering
1. `pip install -r requirements.txt` og `pytest`: alle testene er grønne, med SQLite.
2. Hvis `.env` har Neo4j-tilkoblingen: `pytest -m neo4j` (rydder etter seg selv). Jeg kjører **ikke** `python seed.py` mot Aura uten at du sier ja, siden den tømmer databasen.
3. Med `STORAGE=neo4j` og en seedet Aura: `flask run`, og sjekk menyen, filteret, handlekurven, registrering og innlogging, og admin for matretter (ny, endre, publiser, fjern, bilde). Bestilling skal gi 501-siden.
4. `grep` viser at `neo4j` bare importeres i `app/models/repositories/` (og i `app/__init__.py` for feilsiden).
5. Commit på `neo4j`-branchen (når du ber om det).
