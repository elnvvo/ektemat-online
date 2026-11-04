# Ekte Mat Online

Flask-app for bestilling av catering hos Ekte Mat (INFO212 Oblig 4). Appen bruker bare syntetiske data.

- Krav: [docs/backlog.md](docs/backlog.md)
- Design: [docs/design.md](docs/design.md)
- Planer, én per funksjon (01–10): [docs/plans/](docs/plans/)

## Kom i gang

Krever Python 3.10 eller nyere. Kjør alle kommandoene fra rotmappen i repoet.

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### Mac / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Åpne `.env` og fyll inn:

| Variabel | Påkrevd | Hva |
|---|---|---|
| `SECRET_KEY` | ja | Nøkkel for sesjonene. Lag en med `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SEED_ADMIN_PASSWORD` | ja | Passord for admin-brukeren som `seed.py` lager |
| `SEED_CUSTOMER_PASSWORD` | ja | Passord for de to testkundene (minst 8 tegn) |
| `IMAGE_API_KEY`, `IMAGE_API_URL` | nei | Bildetjeneste for «Lag bilde fra instruks». Uten dem lages et enkelt demo-bilde lokalt |
| `STORAGE` | nei | `sqlite` (standard) eller `neo4j`, se [Kjøre med Neo4j](#kjøre-med-neo4j-auradb) |
| `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` | bare med `STORAGE=neo4j` | Tilkoblingen til Neo4j AuraDB. `NEO4J_DATABASE` er valgfri |

`.env` ligger i `.gitignore` og skal aldri committes.

## Seed, kjør og test (Windows og Mac, med aktivert venv)

| Steg | Kommando | Hva skjer |
|---|---|---|
| Seed | `python seed.py` | **Sletter** og lager `instance/ektemat.sqlite` på nytt med én admin (`admin@ektemat.test`), to testkunder (`kunde1@example.test`, `kunde2@example.test`) og høstmenyen (4 retter; rakfisk er ikke publisert) |
| Kjør | `flask run` | Starter appen på http://127.0.0.1:5000. Flask laster ikke kodeendringer automatisk; bruk `flask run --debug` under utvikling |
| Test | `pytest` | Kjører alle testene i `tests/`, alltid mot en midlertidig SQLite-database (også når `STORAGE=neo4j`) |

## Kjøre med Neo4j (AuraDB)

Oblig 5: hele appen – matretter, brukere, bestillinger (med ordrelinjer og gjestegrupper) og spørsmål med svar – kan lagres i Neo4j etter grafmodellen i [design.md §7](docs/design.md). Controllere, maler og domeneklasser er de samme; det er bare repository-implementasjonen som byttes.

1. Lag en Neo4j AuraDB-instans (gratisversjonen holder) og last ned tilkoblingsfilen.
2. Legg verdiene inn i `.env`, med disse navnene:
   ```
   STORAGE=neo4j
   NEO4J_URI=neo4j+s://<id>.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=<passord>
   NEO4J_DATABASE=          (valgfri)
   ```
3. `python seed.py` **sletter alt i Aura-databasen** og legger inn testdataene. Den spør først, siden databasen er delt i gruppen (`python seed.py --yes` hopper over spørsmålet).
4. `flask run`

| Kommando | Hva |
|---|---|
| `pytest` | Vanlige tester mot SQLite. Rører aldri Aura |
| `pytest -m neo4j` | Tester Neo4j-repositoryene mot Aura-databasen i `.env`. Tømmer den ikke, men lager egne testnoder og sletter bare dem etterpå. Hoppes over uten tilkobling |

Gratisinstanser av Aura settes på pause etter en tid uten bruk; da viser appen «Databasen svarer ikke» til instansen er startet igjen i Aura-konsollen.

## Hva appen kan

**Kunde** (besøkende kan bruke meny og handlekurv uten å logge inn)

| Side | Funksjon | Story |
|---|---|---|
| `/menu` | Meny som kort, filtrert på arrangement, med allergener og diettmerker | US-01, US-02 |
| `/cart` | Handlekurv med estimert total og minimumsantall | US-06, US-07 |
| `/register`, `/login` | Registrering og innlogging | US-19 |
| `/order` | Bestilling med dato, gjester, adresse og gjestegrupper (allergier og dietter, aldri navn) | US-08, US-09 |
| `/orders`, `/orders/<id>` | Mine bestillinger med status og betaling, bekreftelse og spørsmål om bestillingen | US-10, US-11, US-16 |

**Admin** (`/admin`, krever admin-rollen)

| Side | Funksjon | Story |
|---|---|---|
| `/admin/items` | Legg til, endre, publiser og arkiver matretter | US-03, US-04 |
| `/admin/items/<id>/image` | Last opp bilde eller lag bilde fra instruks, med forhåndsvisning | US-05 |
| `/admin/orders` | Alle bestillinger, filtrert på status og periode; endre ordrestatus og betaling | US-12, US-13, US-14 |
| `/admin/questions` | Ubesvarte spørsmål (eldste først), svar til kunden, antall i admin-menyen | US-17, US-18 |

## Mappestruktur (MVC)

```
app/
├── __init__.py            create_app(), registrerer blueprints
├── config.py              innstillinger fra .env
├── controllers/           C: shop.py, account.py, admin.py (blueprints), auth.py (tilgangskontroll)
├── models/                M: domeneklasser og validering (food_item, cart, order, question, user …)
│   └── repositories/      M: base.py (grensesnitt), sqlite_*.py + schema.sql, neo4j_*.py – eneste sted som rører databasen
├── services/              bildetjeneste (image_service.py) og lagring av bildefiler (image_store.py)
├── templates/             V: base.html, shop/, account/, admin/
└── static/                css/, img/ (plassholderbilde), uploads/ (opplastede bilder, ikke i Git)
docs/                      backlog, design og planer (docs/plans/01–10)
seed.py                    syntetiske testdata
tests/                     pytest
```

Bare `app/models/repositories/` rører databasen (NFR-02). Fabrikkene i `repositories/__init__.py` velger SQLite- eller Neo4j-implementasjonen ut fra `STORAGE`.
