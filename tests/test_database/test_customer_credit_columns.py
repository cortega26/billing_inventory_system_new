"""Tests for the customer credit columns reconciliation (plan 024).

Covers: fresh init_db() producing the new columns with defaults and the
credit_limit CHECK, the migration being a no-op on a DB that already has the
columns (live-DB simulation), and the migration being additive on a pre-024
DB.
"""

import sqlite3

import pytest

from database import init_db
from database.database_manager import DatabaseManager
from database.migrations import run_migrations

NEW_REVISION = "652b05c0c11e"
PRE_024_REVISION = "72e1091bcd50"

LIVE_LIKE_CUSTOMERS_DDL = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier_9 TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT,
    current_balance INTEGER NOT NULL DEFAULT 0,
    credit_limit INTEGER NOT NULL DEFAULT 50000 CHECK (credit_limit >= 0),
    is_active INTEGER NOT NULL DEFAULT 1,
    deleted_at TEXT,
    CHECK (LENGTH(identifier_9) = 9),
    CHECK (SUBSTR(identifier_9, 1, 1) = '9'),
    CHECK (identifier_9 NOT GLOB '*[^0-9]*'),
    CHECK (name IS NULL OR LENGTH(name) <= 50)
)
"""

PRE_024_CUSTOMERS_DDL = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier_9 TEXT NOT NULL UNIQUE,
    name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    deleted_at TEXT
)
"""

PRE_024_CUSTOMER_IDENTIFIERS_DDL = """
CREATE TABLE customer_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    identifier_3or4 TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
)
"""


def _close_db_connection():
    if DatabaseManager._connection:
        DatabaseManager._connection.close()
        DatabaseManager._connection = None


def _create_stamped_db(db_path, customers_ddl):
    conn = sqlite3.connect(str(db_path))
    conn.execute(customers_ddl)
    conn.execute(
        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
    )
    conn.execute(
        "INSERT INTO alembic_version (version_num) VALUES (?)", (PRE_024_REVISION,)
    )
    conn.commit()
    conn.close()


def _migrate(db_path):
    DatabaseManager.initialize(str(db_path))
    run_migrations()


class TestCustomerCreditColumns:
    def test_fresh_db_has_columns_with_defaults(self, tmp_path):
        db_path = tmp_path / "fresh.db"

        try:
            init_db(str(db_path))

            columns = {
                row["name"]
                for row in DatabaseManager.execute_query(
                    "PRAGMA table_info(customers)"
                ).fetchall()
            }
            assert "current_balance" in columns
            assert "credit_limit" in columns

            DatabaseManager.execute_query(
                "INSERT INTO customers (identifier_9, name) VALUES (?, ?)",
                ("912345678", "Cliente"),
            )
            row = DatabaseManager.fetch_one(
                "SELECT current_balance, credit_limit FROM customers WHERE identifier_9 = ?",
                ("912345678",),
            )
            assert row["current_balance"] == 0
            assert row["credit_limit"] == 50000

            raw_conn = sqlite3.connect(str(db_path))
            try:
                with pytest.raises(sqlite3.IntegrityError):
                    raw_conn.execute(
                        "INSERT INTO customers (identifier_9, name, credit_limit)"
                        " VALUES (?, ?, ?)",
                        ("987654321", "Negativo", -1),
                    )
            finally:
                raw_conn.close()
        finally:
            _close_db_connection()

    def test_migration_is_noop_on_db_that_already_has_columns(self, tmp_path):
        db_path = tmp_path / "live_like.db"
        _create_stamped_db(db_path, LIVE_LIKE_CUSTOMERS_DDL)

        try:
            _migrate(db_path)

            conn = sqlite3.connect(str(db_path))
            try:
                version = conn.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()[0]
                assert version == NEW_REVISION

                columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(customers)").fetchall()
                }
                assert "current_balance" in columns
                assert "credit_limit" in columns

                conn.execute(
                    "INSERT INTO customers (identifier_9, name) VALUES (?, ?)",
                    ("912345678", "Sin tocar"),
                )
                row = conn.execute(
                    "SELECT current_balance, credit_limit FROM customers"
                    " WHERE identifier_9 = ?",
                    ("912345678",),
                ).fetchone()
                assert row == (0, 50000)
                conn.commit()
            finally:
                conn.close()
        finally:
            _close_db_connection()

    def test_migration_adds_columns_to_pre_024_db(self, tmp_path):
        db_path = tmp_path / "pre_024.db"
        _create_stamped_db(db_path, PRE_024_CUSTOMERS_DDL)

        try:
            _migrate(db_path)

            conn = sqlite3.connect(str(db_path))
            try:
                version = conn.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()[0]
                assert version == NEW_REVISION

                columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(customers)").fetchall()
                }
                assert "current_balance" in columns
                assert "credit_limit" in columns

                conn.execute(
                    "INSERT INTO customers (identifier_9, name) VALUES (?, ?)",
                    ("912345678", "Migrado"),
                )
                row = conn.execute(
                    "SELECT current_balance, credit_limit FROM customers"
                    " WHERE identifier_9 = ?",
                    ("912345678",),
                ).fetchone()
                assert row == (0, 50000)
                conn.commit()
            finally:
                conn.close()
        finally:
            _close_db_connection()

    def test_pre_024_migration_preserves_customer_identifiers(self, tmp_path):
        """Regression: the batch recreate of `customers` must not cascade-wipe
        `customer_identifiers` rows when the connection has
        PRAGMA foreign_keys = ON (DatabaseManager startup pragma). This bug
        silently deleted every identifier of the seeded casabea DB."""
        db_path = tmp_path / "pre_024_with_identifiers.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(PRE_024_CUSTOMERS_DDL)
        conn.execute(PRE_024_CUSTOMER_IDENTIFIERS_DDL)
        conn.execute(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL"
            " PRIMARY KEY)"
        )
        conn.execute(
            "INSERT INTO alembic_version (version_num) VALUES (?)",
            (PRE_024_REVISION,),
        )
        conn.execute(
            "INSERT INTO customers (identifier_9, name) VALUES (?, ?)",
            ("912345678", "Cliente"),
        )
        conn.execute(
            "INSERT INTO customer_identifiers (customer_id, identifier_3or4)"
            " VALUES (?, ?)",
            (1, "408"),
        )
        conn.commit()
        conn.close()

        try:
            _migrate(db_path)

            conn = sqlite3.connect(str(db_path))
            try:
                rows = conn.execute(
                    "SELECT ci.identifier_3or4 FROM customer_identifiers ci"
                    " JOIN customers c ON c.id = ci.customer_id"
                    " WHERE c.identifier_9 = ?",
                    ("912345678",),
                ).fetchall()
                assert rows == [("408",)]
            finally:
                conn.close()
        finally:
            _close_db_connection()
