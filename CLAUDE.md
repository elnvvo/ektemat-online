# Ekte Mat Online
Flask-app for bestilling av catering (INFO212 Oblig 4). Kun syntetiske data.
Krav: docs/backlog.md. Design: docs/design.md.

## Struktur (MVC)
- app/models/ – domeneklasser
- app/models/repositories/ – ENESTE sted som rører databasen (SQLite nå, Neo4j i Oblig 5)
- app/controllers/ – Flask-blueprints: shop, account, admin
- app/templates/ – Jinja2-maler (views)

## Kjøring
python -m venv .venv
.venv\Scripts\activate        (Mac: source .venv/bin/activate)
pip install -r requirements.txt
python seed.py
flask run
pytest

## Regler
- Planlegg større funksjoner i plan mode, lagre planen i docs/plans/
- Aldri hemmeligheter i koden; bruk .env (som ligger i .gitignore)
- Ingen gjestenavn i datamodellen (GDPR); allergier lagres per gjestegruppe
- Hver Must-story skal ha minst én test
- Henvis til user story-ID (US-xx) i commit-meldinger