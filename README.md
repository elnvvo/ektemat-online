# Ekte Mat Online

Flask-app for bestilling av catering hos Ekte Mat (INFO212 Oblig 4). Appen bruker bare syntetiske data.

- Krav: [docs/backlog.md](docs/backlog.md)
- Design: [docs/design.md](docs/design.md)
- Planer, én per funksjon (01–12): [docs/plans/](docs/plans/)

## Kom i gang

**Appen kjører med SQLite uten noe mer oppsett.** SQLite er standard: databasen er en fil (`instance/ektemat.sqlite`) som `python seed.py` lager. Du trenger ingen databaseserver, ingen konto og ingen Neo4j. Neo4j er valgfritt, se [Kjøre med Neo4j](#kjøre-med-neo4j-auradb).

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

Åpne `.env` og fyll inn de tre påkrevde verdiene. Resten kan stå tomme for å kjøre med SQLite:

| Variabel | Påkrevd | Hva |
|---|---|---|
| `SECRET_KEY` | ja | Nøkkel for sesjonene. Lag en med `python -c "import secrets; print(secrets.token_hex(32))"` |
| `SEED_ADMIN_PASSWORD` | ja | Passord for admin-brukeren som `seed.py` lager |
| `SEED_CUSTOMER_PASSWORD` | ja | Passord for de to testkundene (minst 8 tegn) |
| `IMAGE_API_KEY`, `IMAGE_API_URL` | nei | Bildetjeneste for «Lag bilde fra instruks». Uten dem lages et enkelt demo-bilde lokalt |
| `STORAGE` | nei | `sqlite` (standard) eller `neo4j`, se [Kjøre med Neo4j](#kjøre-med-neo4j-auradb) |
| `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` | bare med `STORAGE=neo4j` | Tilkoblingen til Neo4j AuraDB. `NEO4J_DATABASE` er valgfri |

`.env` ligger i `.gitignore` og skal aldri committes.

Eksempel på en `.env` som holder for SQLite (bruk egne verdier):

```
SECRET_KEY=<lang tilfeldig streng>
SEED_ADMIN_PASSWORD=admin-passord-123
SEED_CUSTOMER_PASSWORD=kunde-passord-123
```

Etter `python seed.py` og `flask run` kan du logge inn som `admin@ektemat.test` med `SEED_ADMIN_PASSWORD`, eller som `kunde1@example.test` med `SEED_CUSTOMER_PASSWORD`. Første linje fra `flask run` skal være `* Lagring: sqlite - …`.

## Seed, kjør og test (Windows og Mac, med aktivert venv)

| Steg | Kommando | Hva skjer |
|---|---|---|
| Seed | `python seed.py` | **Sletter** og lager `instance/ektemat.sqlite` på nytt med én admin (`admin@ektemat.test`), to testkunder (`kunde1@example.test`, `kunde2@example.test`) og høstmenyen (4 retter; rakfisk er ikke publisert) |
| Kjør | `flask run` | Starter appen på http://127.0.0.1:5000. Flask laster ikke kodeendringer automatisk; bruk `flask run --debug` under utvikling |
| Test | `pytest` | Kjører alle testene i `tests/`, alltid mot en midlertidig SQLite-database (også når `STORAGE=neo4j`) |

## Kjøre med Neo4j (AuraDB)

Oblig 5: hele appen – matretter, brukere, bestillinger (med ordrelinjer og gjestegrupper) og spørsmål med svar – kan lagres i Neo4j etter grafmodellen i [design.md §7](docs/design.md). Controllere, maler og domeneklasser er de samme; det er bare repository-implementasjonen som byttes.

Gruppens egen Aura-database og passordet til den ligger ikke i repoet. For å prøve Neo4j lager du derfor din egen gratis database. Det tar et par minutter og krever ikke kredittkort.

**1. Lag en gratis AuraDB-database**
1. Gå til [console.neo4j.io](https://console.neo4j.io) og logg inn eller lag en konto (e-post eller Google).
2. Velg **Create instance** og så **AuraDB Free**. Gi den et navn og opprett den.
3. Før instansen opprettes, vises brukernavnet og passordet **én gang**. Trykk **Download** og ta vare på filen (`Neo4j-<id>-Created-<dato>.txt`). Passordet kan ikke hentes senere; har du mistet det, må du lage en ny instans.
4. Vent til instansen står som **Running** i konsollen (ofte et par minutter).

**2. Fyll inn `.env`**

Tilkoblingsfilen har linjer som `NEO4J_URI=…`, `NEO4J_USERNAME=…` og `NEO4J_PASSWORD=…`. Kopier verdiene inn i `.env`, og sett `STORAGE=neo4j`:

```
STORAGE=neo4j
NEO4J_URI=neo4j+s://<id>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<passordet fra filen>
NEO4J_DATABASE=neo4j          (valgfri – kan stå tom)
```

- Står brukernavnet som `NEO4J_USER` i filen, skal det hete `NEO4J_USERNAME` i `.env`.
- Linjer som `AURA_INSTANCEID` og `AURA_INSTANCENAME` trengs ikke.
- `SECRET_KEY` og seed-passordene må fortsatt være fylt inn, som for SQLite.

**3. Fyll databasen og start appen**
1. `python seed.py` **sletter alt i Neo4j-databasen** i `.env` og legger inn testdataene (brukere, katalog og høstmenyen). Den skriver hvilken database det gjelder og ber deg skrive `ja` først (`python seed.py --yes` hopper over spørsmålet). En helt ny Aura-database er tom, så her mister du ingenting.
2. `flask run`. Første linje viser hvilken lagring som brukes, f.eks. `* Lagring: neo4j - neo4j+s://<id>.databases.neo4j.io (standarddatabasen)`. Står det `sqlite`, er ikke `STORAGE=neo4j` lest inn. `.env` leses bare når serveren starter, så **endrer du `STORAGE`, må serveren startes på nytt** (Ctrl+C og `flask run` igjen).

Vil du tilbake til SQLite, setter du `STORAGE=sqlite` (eller lar den stå tom) og starter serveren på nytt. SQLite-databasen og Neo4j-databasen er helt atskilt, så data du lager i den ene, vises ikke i den andre.

| Kommando | Hva |
|---|---|
| `pytest` | Vanlige tester mot SQLite. Rører aldri Aura |
| `pytest -m neo4j` | Tester Neo4j-repositoryene mot Aura-databasen i `.env`. Tømmer den ikke, men lager egne testnoder og sletter bare dem etterpå. Hoppes over uten tilkobling |

Gratisinstanser av Aura settes på pause etter noen dager uten bruk. Da viser appen «Databasen svarer ikke» til du trykker **Resume** på instansen i Aura-konsollen og venter til den står som **Running** igjen.

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
docs/                      backlog, design og planer (docs/plans/01–12)
seed.py                    syntetiske testdata
tests/                     pytest
```

Bare `app/models/repositories/` rører databasen (NFR-02). Fabrikkene i `repositories/__init__.py` velger SQLite- eller Neo4j-implementasjonen ut fra `STORAGE`.
