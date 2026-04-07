import sqlite3
from pathlib import Path

import main


def _create_db_with_customer(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            "CREATE TABLE customers (id INTEGER PRIMARY KEY AUTOINCREMENT, identifier_9 TEXT, name TEXT)"
        )
        connection.execute(
            "INSERT INTO customers (identifier_9, name) VALUES (?, ?)",
            ("912345678", "Cliente recuperable"),
        )
        connection.commit()
    finally:
        connection.close()


def test_build_empty_database_warning_returns_none_for_new_database(mocker):
    counts_mock = mocker.patch("main._get_primary_table_counts")

    assert main._build_empty_database_warning(False) is None
    counts_mock.assert_not_called()


def test_find_recovery_candidate_detects_backup_with_data(tmp_path, mocker):
    active_db_path = tmp_path / "billing_inventory.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    active_db_path.touch()
    candidate_path = backup_dir / "backup_20260407_154754_billing_inventory.db"
    _create_db_with_customer(candidate_path)
    mocker.patch("main.DATABASE_PATH", active_db_path)

    recovery_candidate = main._find_recovery_candidate(active_db_path)

    assert recovery_candidate is not None
    assert recovery_candidate[0] == candidate_path
    assert recovery_candidate[1] == 1


def test_warn_if_active_database_looks_empty_shows_warning_for_existing_database(
    mocker,
):
    warning_message = "Base vacia detectada"
    build_warning_mock = mocker.patch(
        "main._build_empty_database_warning", return_value=warning_message
    )
    show_warning_mock = mocker.patch("main._show_startup_warning")

    main._warn_if_active_database_looks_empty(True)

    build_warning_mock.assert_called_once_with(True)
    show_warning_mock.assert_called_once_with(warning_message)