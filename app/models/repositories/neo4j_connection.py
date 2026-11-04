"""Neo4j AuraDB-tilkobling (Oblig 5). Bare repository-laget skal importere denne modulen.

Alle Cypher-spørringer er konstanter, og alle verdier sendes som parametere ($navn) –
aldri satt inn i teksten (se tests/test_storage.py).
"""
import atexit
from urllib.parse import urlsplit

from flask import current_app
from neo4j import GraphDatabase, RoutingControl
from neo4j.exceptions import AuthError, ServiceUnavailable, SessionExpired

# Feil som betyr at databasen ikke svarer (f.eks. en Aura Free-instans som er satt på pause).
CONNECTION_ERRORS = (ServiceUnavailable, SessionExpired, AuthError)

_REQUIRED_SETTINGS = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")

# Unikhets-constraints. Etiketter kan ikke være parametere, så hver står skrevet ut.
CONSTRAINTS = (
    "CREATE CONSTRAINT food_item_id IF NOT EXISTS FOR (f:FoodItem) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT user_email IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE",
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
    "CREATE CONSTRAINT event_category_id IF NOT EXISTS FOR (c:EventCategory) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT event_category_name IF NOT EXISTS FOR (c:EventCategory) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT allergen_code IF NOT EXISTS FOR (a:Allergen) REQUIRE a.code IS UNIQUE",
    "CREATE CONSTRAINT dietary_label_code IF NOT EXISTS FOR (d:DietaryLabel) REQUIRE d.code IS UNIQUE",
    "CREATE CONSTRAINT sequence_name IF NOT EXISTS FOR (s:Sequence) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:Order) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE q.id IS UNIQUE",
    # Maks ett svar per spørsmål (design.md §2: Question 1 *-- 0..1 Answer).
    "CREATE CONSTRAINT answer_question_id IF NOT EXISTS FOR (a:Answer) REQUIRE a.question_id IS UNIQUE",
)

DELETE_EVERYTHING = "MATCH (n) DETACH DELETE n"

# Egne heltalls-id-er (ikke Neo4js interne id-er). Låsen på telleren gjør økningen trygg.
NEXT_ID = (
    "MERGE (s:Sequence {name: $name}) "
    "ON CREATE SET s.value = 0 "
    "SET s.value = s.value + 1 "
    "RETURN s.value AS value"
)


def init_app(app):
    """Lager driveren én gang. Den kobler ikke til før første spørring."""
    missing = [key for key in _REQUIRED_SETTINGS if not app.config.get(key)]
    if missing:
        raise RuntimeError(
            f"STORAGE=neo4j, men {', '.join(missing)} mangler i .env (se .env.example)."
        )
    driver = GraphDatabase.driver(
        app.config["NEO4J_URI"],
        auth=(app.config["NEO4J_USERNAME"], app.config["NEO4J_PASSWORD"]),
    )
    app.extensions["neo4j"] = driver
    atexit.register(driver.close)


def get_driver():
    return current_app.extensions["neo4j"]


def _database():
    return current_app.config.get("NEO4J_DATABASE") or None


def run_read(query, **params):
    """Leser og returnerer en liste med records."""
    return get_driver().execute_query(
        query, parameters_=params, routing_=RoutingControl.READ, database_=_database()
    ).records


def run_write(query, **params):
    return get_driver().execute_query(
        query, parameters_=params, routing_=RoutingControl.WRITE, database_=_database()
    ).records


def write_transaction(work):
    """Kjører work(tx) i én skrivetransaksjon (alt eller ingenting)."""
    with get_driver().session(database=_database()) as session:
        return session.execute_write(work)


def next_id(tx, name):
    return tx.run(NEXT_ID, name=name).single()["value"]


def ensure_constraints():
    for statement in CONSTRAINTS:
        run_write(statement)


def reset_database():
    """Sletter ALT i databasen og lager constraints. Bare for seed.py (delt testdatabase)."""
    run_write(DELETE_EVERYTHING)
    ensure_constraints()


def describe_target(config=None):
    """Hvilken Neo4j-database som brukes – aldri med brukernavn eller passord."""
    config = config if config is not None else current_app.config
    parts = urlsplit(config.get("NEO4J_URI") or "")
    host = parts.hostname or "?"
    address = f"{parts.scheme}://{host}" + (f":{parts.port}" if parts.port else "")
    return f"{address} ({config.get('NEO4J_DATABASE') or 'standarddatabasen'})"
