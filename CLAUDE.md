# Ekte Mat Online
Flask-app for bestilling av catering (INFO212 Oblig 4). Kun syntetiske data.
Krav: docs/backlog.md. Design: docs/design.md.

## Struktur (MVC)
- app/models/ – domeneklasser (validering ligger her, ikke i controllerne)
- app/models/repositories/ – ENESTE sted som rører databasen. STORAGE=sqlite (standard) eller neo4j i .env velger implementasjon
  (sqlite_*.py og neo4j_*.py dekker alle fire: matretter, brukere, bestillinger og spørsmål)
- app/controllers/ – Flask-blueprints: shop, account, admin (+ auth.py med @login_required/@admin_required)
- app/services/ – det som ikke er database: bildetjeneste og lagring av bildefiler (US-05)
- app/templates/ – Jinja2-maler (views)

## Kjøring
python -m venv .venv
.venv\Scripts\activate        (Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env        (Mac: cp .env.example .env) – fyll inn SECRET_KEY og seed-passordene
python seed.py                (sletter og lager databasen STORAGE peker på; Neo4j: spør først, --yes hopper over)
flask run
pytest                        (alltid SQLite – rører aldri den delte Aura-databasen)
pytest -m neo4j               (Neo4j-testene; lager og sletter bare egne testnoder)

Neo4j: STORAGE=neo4j og NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD (NEO4J_DATABASE valgfri) i .env

## Regler
- Planlegg større funksjoner i plan mode, lagre planen i docs/plans/ som NN-navn.md (neste nummer er 13)
- Aldri hemmeligheter i koden; bruk .env (som ligger i .gitignore). IMAGE_API_KEY er valgfri
- Cypher: alltid $parametere, aldri strengsammenslåing; egne id-egenskaper, ikke Neo4js interne id-er
- Tester må aldri tømme Neo4j-databasen (den er delt); Neo4j-tester merkes @pytest.mark.neo4j
- Ingen gjestenavn i datamodellen (GDPR); allergier lagres per gjestegruppe
- Hver Must-story skal ha minst én test
- Henvis til user story-ID (US-xx) i commit-meldinger
