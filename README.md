# Ekte Mat Online

Flask-app for bestilling av catering hos Ekte Mat (INFO212 Oblig 4). Appen bruker bare syntetiske data.

- Krav: [docs/backlog.md](docs/backlog.md)
- Design: [docs/design.md](docs/design.md)
- Planer: [docs/plans/](docs/plans/)

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

Åpne `.env` og fyll inn `SECRET_KEY`, `SEED_ADMIN_PASSWORD` og `SEED_CUSTOMER_PASSWORD`. Du kan lage en nøkkel med:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`.env` ligger i `.gitignore` og skal aldri committes.

## Seed, kjør og test (Windows og Mac, med aktivert venv)

| Steg | Kommando | Hva skjer |
|---|---|---|
| Seed | `python seed.py` | Lager `instance/ektemat.sqlite` på nytt med én admin (`admin@ektemat.test`) og to testkunder (`kunde1@example.test`, `kunde2@example.test`) |
| Kjør | `flask run` | Starter appen på http://127.0.0.1:5000 (`/`, `/login`, `/admin`) |
| Test | `pytest` | Kjører testene i `tests/` |

## Mappestruktur (MVC)

```
app/
├── __init__.py            create_app(), registrerer blueprints
├── config.py              innstillinger fra .env
├── controllers/           C: shop.py, account.py, admin.py (blueprints)
├── models/                M: domeneklasser
│   └── repositories/      M: base.py (grensesnitt), sqlite_connection.py, schema.sql
├── templates/             V: base.html, shop/, account/, admin/
└── static/css/
seed.py                    syntetiske testdata
tests/                     pytest
```

Bare `app/models/repositories/` rører databasen (NFR-02), slik at SQLite kan byttes ut med Neo4j i Oblig 5.
