import sqlite3
from pathlib import Path

from database import init_db
from database.database_manager import DatabaseManager


LEGACY_SCHEMA = """
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category_id INTEGER,
    cost_price INTEGER NOT NULL DEFAULT 0,
    sell_price INTEGER NOT NULL DEFAULT 0,
    barcode TEXT UNIQUE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE TABLE inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL UNIQUE,
    quantity DECIMAL(10,3) NOT NULL DEFAULT 0.000,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier_9 TEXT NOT NULL UNIQUE,
    name TEXT
);

CREATE TABLE customer_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    identifier_3or4 TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    date TEXT NOT NULL,
    total_amount INTEGER NOT NULL DEFAULT 0,
    total_profit INTEGER NOT NULL DEFAULT 0,
    receipt_id TEXT UNIQUE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
);

CREATE TABLE sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity DECIMAL(10,3) NOT NULL,
    price INTEGER NOT NULL,
    profit INTEGER NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

CREATE TABLE purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier TEXT NOT NULL,
    date TEXT NOT NULL,
    total_amount INTEGER NOT NULL
);

CREATE TABLE purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity DECIMAL(10,3) NOT NULL,
    price INTEGER NOT NULL,
    FOREIGN KEY (purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

CREATE TABLE inventory_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    quantity_change DECIMAL(10,3) NOT NULL,
    reason TEXT NOT NULL,
    date TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
"""


def _close_db_connection():
    if DatabaseManager._connection:
        DatabaseManager._connection.close()
        DatabaseManager._connection = None


def _create_legacy_database(db_path):
    legacy_conn = sqlite3.connect(str(db_path))
    legacy_conn.executescript(LEGACY_SCHEMA)
    legacy_conn.execute(
        "INSERT INTO customers (identifier_9, name) VALUES (?, ?)",
        ("912345678", "Cliente heredado"),
    )
    legacy_conn.execute(
        """
        INSERT INTO products (name, description, cost_price, sell_price, barcode)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("Producto heredado", "Sin columnas soft-delete", 100, 150, "LEGACY-001"),
    )
    legacy_conn.commit()
    legacy_conn.close()


def _fetch_index(name):
    return DatabaseManager.fetch_one(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'index' AND name = ?
        """,
        (name,),
    )


def test_init_db_applies_startup_pragmas_outside_transactions(tmp_path):
    """Application startup should configure pragmas without transaction errors."""
    db_path = tmp_path / "app_init.db"

    try:
        init_db(str(db_path))

        journal_mode = DatabaseManager.execute_query("PRAGMA journal_mode").fetchone()[
            0
        ]
        synchronous = DatabaseManager.execute_query("PRAGMA synchronous").fetchone()[0]
        created_index = DatabaseManager.fetch_one(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index' AND name = ?
            """,
            ("idx_sales_date",),
        )
        audit_log_table = DatabaseManager.fetch_one(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            """,
            ("audit_log",),
        )

        assert str(journal_mode).lower() == "wal"
        assert synchronous == 1
        assert created_index is not None
        assert audit_log_table is not None
        assert not DatabaseManager._connection.in_transaction
    finally:
        _close_db_connection()


def test_init_db_uses_configured_database_path_by_default(mocker, tmp_path):
    """Default initialization should use the configured absolute database path."""
    configured_db_path = tmp_path / "configured.db"

    initialize_mock = mocker.patch("database.DatabaseManager.initialize")
    apply_schema_mock = mocker.patch("database._apply_schema_tables")
    migrate_legacy_mock = mocker.patch("database._migrate_legacy_customers_table")
    run_migrations_mock = mocker.patch("database.run_migrations")
    mocker.patch("database.DATABASE_PATH", configured_db_path)
    mocker.patch("database._get_schema_path", return_value=str(Path("/tmp/schema.sql")))

    init_db()

    initialize_mock.assert_called_once_with(str(configured_db_path))
    apply_schema_mock.assert_called_once_with("/tmp/schema.sql")
    migrate_legacy_mock.assert_called_once()
    run_migrations_mock.assert_called_once()


def test_init_db_migrates_legacy_soft_delete_columns_without_losing_data(tmp_path):
    """Startup should migrate legacy DBs before creating indexes that depend on new columns."""
    db_path = tmp_path / "legacy_app_init.db"
    _create_legacy_database(db_path)

    try:
        init_db(str(db_path))

        customer = DatabaseManager.fetch_one(
            "SELECT identifier_9, name, is_active, deleted_at FROM customers WHERE identifier_9 = ?",
            ("912345678",),
        )
        product = DatabaseManager.fetch_one(
            "SELECT name, is_active, deleted_at FROM products WHERE barcode = ?",
            ("LEGACY-001",),
        )
        customer_index = _fetch_index("idx_customers_is_active")
        product_index = _fetch_index("idx_products_is_active")

        assert customer is not None
        assert customer["name"] == "Cliente heredado"
        assert customer["is_active"] == 1
        assert customer["deleted_at"] is None

        assert product is not None
        assert product["name"] == "Producto heredado"
        assert product["is_active"] == 1
        assert product["deleted_at"] is None

        assert customer_index is not None
        assert product_index is not None
    finally:
        _close_db_connection()
