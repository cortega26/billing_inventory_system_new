"""Multi-business isolation tests using real temp database files."""

import sqlite3
from pathlib import Path

from config import DATABASE_PATH, Config, config
from database import init_db
from services.analytics_service import AnalyticsService

PRIMARY_TABLES = ("customers", "products", "sales", "inventory")

ANALYTICS_DATE_RANGE = ("2026-07-01", "2026-08-14")


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


def _insert_sale(
    db_path: Path, date: str, total_amount: int, total_profit: int
) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "INSERT INTO sales (customer_id, date, total_amount, total_profit, status) "
            "VALUES (NULL, ?, ?, ?, 'confirmed')",
            (date, total_amount, total_profit),
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
            # table ∈ a hardcoded test tuple — not user input
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[
                0
            ]  # nosec B608
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


def test_analytics_follows_active_business(tmp_path, monkeypatch):
    """Analytics read the ACTIVE business's DB, not the import-time default."""
    db_a = tmp_path / "a.db"
    db_b = tmp_path / "b.db"
    business_paths = {"default": db_a, "casabea": db_b}

    config.set(
        "businesses",
        [
            {"id": "default", "name": "Principal", "db_filename": "a.db"},
            {"id": "casabea", "name": "CasaBea", "db_filename": "b.db"},
        ],
    )
    config.set_active_business("default")
    # Business db_filenames resolve to the repo root by design; map the real
    # registry flow to temp files for this test.
    monkeypatch.setattr(
        Config,
        "get_active_database_path",
        classmethod(lambda cls: business_paths[Config.get_active_business()["id"]]),
    )

    init_db(str(db_a))
    _insert_product(db_a, "Pan Amasado")
    _insert_sale(db_a, "2026-07-10", 4000, 2000)

    AnalyticsService.clear_cache()
    summary_a = AnalyticsService.get_sales_summary(*ANALYTICS_DATE_RANGE)
    assert summary_a == {
        "total_sales": 1,
        "total_revenue": 4000,
        "total_profit": 2000,
        "average_sale_value": 4000.0,
        "unique_customers": 0,
    }

    # Switch to a fresh business: the DB exists (born migrated) but the
    # metrics must come back zeroed.
    config.set_active_business("casabea")
    init_db(str(db_b))
    AnalyticsService.clear_cache()
    summary_b = AnalyticsService.get_sales_summary(*ANALYTICS_DATE_RANGE)
    assert summary_b == {
        "total_sales": 0,
        "total_revenue": 0,
        "total_profit": 0,
        "average_sale_value": 0,
        "unique_customers": 0,
    }

    # Switch back: the original totals return.
    config.set_active_business("default")
    AnalyticsService.clear_cache()
    summary_back = AnalyticsService.get_sales_summary(*ANALYTICS_DATE_RANGE)
    assert summary_back == {
        "total_sales": 1,
        "total_revenue": 4000,
        "total_profit": 2000,
        "average_sale_value": 4000.0,
        "unique_customers": 0,
    }
