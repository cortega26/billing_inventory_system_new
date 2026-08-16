"""Multi-business isolation tests using real temp database files."""

import sqlite3
from pathlib import Path

from config import DATABASE_PATH, Config
from database import init_db

PRIMARY_TABLES = ("customers", "products", "sales", "inventory")


def _table_names(db_path: Path) -> set[str]:
    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {row[0] for row in rows}
    finally:
        connection.close()


def _product_count(db_path: Path) -> int:
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    finally:
        connection.close()


def _insert_product(db_path: Path, name: str) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO products (name, cost_price, sell_price) VALUES (?, ?, ?)",
            (name, 300, 500),
        )
        connection.commit()
    finally:
        connection.close()


def test_switch_to_new_business_gets_fresh_schema(tmp_path):
    db_b = tmp_path / "casabea.db"
    assert not db_b.exists()

    init_db(str(db_b))

    tables = _table_names(db_b)
    assert set(PRIMARY_TABLES) <= tables
    connection = sqlite3.connect(db_b)
    try:
        for table in PRIMARY_TABLES:
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == 0
    finally:
        connection.close()


def test_business_data_is_isolated(tmp_path):
    db_a = tmp_path / "a.db"
    db_b = tmp_path / "b.db"

    init_db(str(db_a))
    _insert_product(db_a, "Pan Amasado")
    assert _product_count(db_a) == 1

    # Switch to business B: its file is born fresh and does not see A's data.
    init_db(str(db_b))
    assert _product_count(db_b) == 0

    # Switch back to business A: the product is still there.
    init_db(str(db_a))
    assert _product_count(db_a) == 1


def test_active_business_defaults_to_default():
    assert Config.get_active_business()["id"] == "default"
    assert Config.get_active_database_path() == DATABASE_PATH
