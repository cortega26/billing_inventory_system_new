from database import init_db
from database.database_manager import DatabaseManager


def test_init_db_applies_startup_pragmas_outside_transactions(tmp_path):
    """Application startup should configure pragmas without transaction errors."""
    db_path = tmp_path / "app_init.db"

    try:
        init_db(str(db_path))

        journal_mode = DatabaseManager.execute_query("PRAGMA journal_mode").fetchone()[0]
        synchronous = DatabaseManager.execute_query("PRAGMA synchronous").fetchone()[0]
        created_index = DatabaseManager.fetch_one(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index' AND name = ?
            """,
            ("idx_sales_date",),
        )

        assert str(journal_mode).lower() == "wal"
        assert synchronous == 1
        assert created_index is not None
        assert not DatabaseManager._connection.in_transaction
    finally:
        if DatabaseManager._connection:
            DatabaseManager._connection.close()
            DatabaseManager._connection = None
