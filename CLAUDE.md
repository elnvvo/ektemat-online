# Ekte Mat Online
Flask-app for bestilling av catering (INFO212 Oblig 4). Kun syntetiske data.
Krav: docs/backlog.md. Design: docs/design.md.

## Struktur (MVC)
- app/models/ – domeneklasser (validering ligger her, ikke i controllerne)
- app/models/repositories/ – ENESTE sted som rører databasen (SQLite nå, Neo4j i Oblig 5)
- app/controllers/ – Flask-blueprints: shop, account, admin (+ auth.py med @login_required/@admin_required)
- app/services/ – det som ikke er database: bildetjeneste og lagring av bildefiler (US-05)
- app/templates/ – Jinja2-maler (views)

## Kjøring
python -m venv .venv
.venv\Scripts\activate        (Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env        (Mac: cp .env.example .env) – fyll inn SECRET_KEY og seed-passordene
python seed.py                (sletter og lager databasen på nytt)
flask run
pytest

## Regler
- Planlegg større funksjoner i plan mode, lagre planen i docs/plans/ som NN-navn.md (neste nummer er 11)
- Aldri hemmeligheter i koden; bruk .env (som ligger i .gitignore). IMAGE_API_KEY er valgfri
- Ingen gjestenavn i datamodellen (GDPR); allergier lagres per gjestegruppe
- Hver Must-story skal ha minst én test
- Henvis til user story-ID (US-xx) i commit-meldinger
