"""Database initialization and management."""

from pathlib import Path

from config import DATABASE_PATH
from database.database_manager import DatabaseManager
from database.migrations import run_migrations
from utils.exceptions import DatabaseException

__all__ = ["init_db", "DatabaseManager"]


def _apply_schema_tables(schema_path: str) -> None:
    table_statements = _load_table_statements(schema_path)
    with DatabaseManager.get_db_connection() as conn:
        for statement in table_statements:
            conn.execute(statement)


def _migrate_legacy_customers_table() -> None:
    with DatabaseManager.transaction():
        cursor = DatabaseManager._get_cursor()

        cursor.execute(
            """
            SELECT sql FROM sqlite_master
            WHERE type='table' AND name='customers'
            """
        )

        result = cursor.fetchone()
        if not result or "REGEXP" not in result[0]:
            return

        cursor.execute(
            """
            CREATE TEMPORARY TABLE customers_backup AS
            SELECT * FROM customers
            """
        )
        cursor.execute("DROP TABLE customers")
        cursor.execute(
            """
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier_9 TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                deleted_at TEXT,
                CHECK (LENGTH(identifier_9) = 9),
                CHECK (SUBSTR(identifier_9, 1, 1) = '9'),
                CHECK (identifier_9 NOT GLOB '*[^0-9]*'),
                CHECK (name IS NULL OR LENGTH(name) <= 50)
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO customers (id, identifier_9, name, is_active, deleted_at)
            SELECT id, identifier_9, name, 1, NULL
            FROM customers_backup
            WHERE LENGTH(identifier_9) = 9
            AND SUBSTR(identifier_9, 1, 1) = '9'
            AND identifier_9 NOT GLOB '*[^0-9]*'
            """
        )
        cursor.execute("DROP TABLE customers_backup")


def _get_schema_path() -> str:
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    if schema_path.exists():
        return str(schema_path)
    raise DatabaseException(
        f"schema.sql not found. Expected at: {schema_path}"
    )


def _load_table_statements(schema_path: str) -> list[str]:
    """Return only CREATE TABLE statements from the schema file."""
    with open(schema_path, "r") as f:
        schema_sql = "\n".join(
            line for line in f.readlines() if not line.lstrip().startswith("--")
        )

    statements = []
    for statement in schema_sql.split(";"):
        stripped = statement.strip()
        if stripped.upper().startswith("CREATE TABLE"):
            statements.append(f"{stripped};")
    return statements


def init_db(db_path: str | None = None):
    """Initialize the database connection and create tables."""
    try:
        DatabaseManager.initialize(str(db_path or DATABASE_PATH))
        _apply_schema_tables(_get_schema_path())
        _migrate_legacy_customers_table()
        run_migrations()
    except Exception as e:
        raise DatabaseException(f"Failed to initialize database: {str(e)}")
