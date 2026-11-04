"""Valg av lagring med STORAGE (Oblig 5). Kjører alltid og trenger ingen Neo4j-database."""
import ast
import re
from pathlib import Path

import pytest

from app import create_app
from app.models.repositories import (
    food_item_repository,
    order_repository,
    question_repository,
    user_repository,
)
from app.models.repositories.neo4j_connection import describe_target
from app.models.repositories.neo4j_food_item_repository import Neo4jFoodItemRepository
from app.models.repositories.neo4j_user_repository import Neo4jUserRepository
from app.models.repositories.neo4j_order_repository import Neo4jOrderRepository
from app.models.repositories.neo4j_question_repository import Neo4jQuestionRepository
from app.models.repositories.sqlite_food_item_repository import SqliteFoodItemRepository
from app.models.repositories.sqlite_order_repository import SqliteOrderRepository
from app.models.repositories.sqlite_user_repository import SqliteUserRepository

REPOSITORIES = Path(__file__).resolve().parent.parent / "app" / "models" / "repositories"

# Driveren kobler ikke til før første spørring, så en adresse som ikke finnes er nok her.
NEO4J_SETTINGS = {
    "NEO4J_URI": "neo4j+s://ingen-database.invalid",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "ikke-et-ekte-passord",
}


def make_app(tmp_path, **settings):
    return create_app(
        {"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(tmp_path / "t.sqlite"), **settings}
    )


def test_sqlite_is_used_by_default(app):
    assert app.config["STORAGE"] == "sqlite"
    with app.app_context():
        assert isinstance(food_item_repository(), SqliteFoodItemRepository)
        assert isinstance(user_repository(), SqliteUserRepository)
        assert isinstance(order_repository(), SqliteOrderRepository)


def test_neo4j_storage_selects_neo4j_repositories(tmp_path):
    app = make_app(tmp_path, STORAGE="neo4j", **NEO4J_SETTINGS)
    with app.app_context():
        assert isinstance(food_item_repository(), Neo4jFoodItemRepository)
        assert isinstance(user_repository(), Neo4jUserRepository)
        assert isinstance(order_repository(), Neo4jOrderRepository)
        assert isinstance(question_repository(), Neo4jQuestionRepository)
    app.extensions["neo4j"].close()


def test_invalid_storage_stops_create_app(tmp_path):
    with pytest.raises(RuntimeError, match="STORAGE='mongodb' er ugyldig"):
        make_app(tmp_path, STORAGE="mongodb")


def test_neo4j_without_connection_settings_stops_create_app(tmp_path):
    with pytest.raises(RuntimeError, match="NEO4J_URI"):
        make_app(tmp_path, STORAGE="neo4j", NEO4J_URI=None, NEO4J_USERNAME="neo4j", NEO4J_PASSWORD="x")


def test_startup_shows_sqlite_storage(tmp_path, capsys):
    make_app(tmp_path, STORAGE="sqlite", TESTING=False)

    line = capsys.readouterr().err.strip()
    assert line == f"* Lagring: sqlite - {tmp_path / 't.sqlite'}"


def test_startup_shows_neo4j_storage_without_credentials(tmp_path, capsys):
    app = make_app(
        tmp_path,
        STORAGE="neo4j",
        TESTING=False,
        NEO4J_URI="neo4j+s://abc123.databases.neo4j.io",
        NEO4J_USERNAME="neo4j",
        NEO4J_PASSWORD="hemmelig",
        NEO4J_DATABASE="neo4j",
    )

    line = capsys.readouterr().err.strip()
    assert line == "* Lagring: neo4j - neo4j+s://abc123.databases.neo4j.io (neo4j)"
    assert "hemmelig" not in line
    app.extensions["neo4j"].close()


def test_describe_target_never_shows_userinfo():
    config = {"NEO4J_URI": "bolt://bruker:hemmelig@localhost:7687", "NEO4J_DATABASE": None}
    assert describe_target(config) == "bolt://localhost:7687 (standarddatabasen)"


def test_tests_do_not_print_storage_line(tmp_path, capsys):
    make_app(tmp_path)
    assert "Lagring:" not in capsys.readouterr().err


CYPHER = re.compile(r"\b(MATCH|CREATE|MERGE|SET|DELETE|RETURN|WHERE|UNWIND)\b")


def _is_cypher_text(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and CYPHER.search(node.value)


@pytest.mark.parametrize("path", sorted(REPOSITORIES.glob("neo4j_*.py")), ids=lambda p: p.name)
def test_cypher_only_uses_parameters(path):
    """Cypher bygges aldri med verdier: ingen f-strenger, .format, % eller + med Cypher-tekst i funksjoner.

    Spørringene er konstanter på modulnivå; verdiene sendes som $parametere.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    problems = []
    for function in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for node in ast.walk(function):
            if isinstance(node, ast.JoinedStr) and any(_is_cypher_text(v) for v in node.values):
                problems.append(f"f-streng med Cypher, linje {node.lineno}")
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
                if _is_cypher_text(node.left) or _is_cypher_text(node.right):
                    problems.append(f"Cypher bygget med {type(node.op).__name__}, linje {node.lineno}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "format"
                and _is_cypher_text(node.func.value)
            ):
                problems.append(f".format() på Cypher, linje {node.lineno}")
    assert problems == []


def test_neo4j_is_only_imported_in_repository_layer():
    app_dir = REPOSITORIES.parent.parent
    offenders = [
        str(path.relative_to(app_dir))
        for path in app_dir.rglob("*.py")
        if re.search(r"^\s*(from|import) neo4j\b", path.read_text(encoding="utf-8"), re.M)
        and REPOSITORIES not in path.parents
    ]
    assert offenders == []
