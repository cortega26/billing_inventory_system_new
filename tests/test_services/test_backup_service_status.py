from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from config import config
from services.backup_service import BackupService
from utils.system.event_system import event_system


@pytest.fixture
def backup_service_test(tmp_path):
    # Reset singleton
    BackupService._instance = None

    # Configure actual config to use tmp_path
    config.set("backup_dir", str(tmp_path / "backups"))
    config.set("backup_retention_days", 7)
    config.set("last_backup_success", "")
    config.set("last_backup_skipped_time", "")
    config.set("last_backup_skipped_reason", "")
    config.save()

    service = BackupService()
    yield service

    BackupService._instance = None


@pytest.fixture
def source_db(tmp_path):
    db_path = tmp_path / "test_db.db"
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    conn.close()
    return db_path


def test_create_backup_success_updates_config_and_emits_event(
    backup_service_test, source_db
):
    completed_payloads = []

    def completed_handler(path):
        completed_payloads.append(path)

    event_system.backup_completed.connect(completed_handler)

    try:
        with patch("services.backup_service.DATABASE_PATH", source_db):
            backup_path = backup_service_test.create_backup()
            assert backup_path is not None
            assert Path(backup_path).exists()

            # Verify config updated
            last_success = config.get("last_backup_success")
            assert last_success != ""
            # Ensure it is a valid isoformat timestamp
            assert datetime.fromisoformat(last_success) is not None

            # Verify event emitted
            assert len(completed_payloads) == 1
            assert completed_payloads[0] == backup_path
    finally:
        event_system.backup_completed.disconnect(completed_handler)


def test_create_backup_skipped_updates_config_and_emits_event(
    backup_service_test, source_db
):
    skipped_payloads = []

    def skipped_handler(data):
        skipped_payloads.append(data)

    event_system.backup_skipped.connect(skipped_handler)

    try:
        with (
            patch("services.backup_service.DATABASE_PATH", source_db),
            patch(
                "services.backup_service.shutil.disk_usage",
                return_value=SimpleNamespace(total=100, used=100, free=0),
            ),
        ):
            backup_path = backup_service_test.create_backup()
            assert backup_path is None

            # Verify config updated
            last_skipped_time = config.get("last_backup_skipped_time")
            assert last_skipped_time != ""
            assert datetime.fromisoformat(last_skipped_time) is not None

            last_skipped_reason = config.get("last_backup_skipped_reason")
            assert last_skipped_reason == "low_disk_space"

            # Verify event emitted
            assert len(skipped_payloads) == 1
            assert skipped_payloads[0]["reason"] == "low_disk_space"
    finally:
        event_system.backup_skipped.disconnect(skipped_handler)


def test_create_backup_exception_updates_config_and_emits_event(
    backup_service_test, source_db
):
    # Force exception during sqlite3.connect
    with (
        patch("services.backup_service.DATABASE_PATH", source_db),
        patch(
            "services.backup_service.sqlite3.connect",
            side_effect=Exception("Failed to open connection"),
        ),
    ):
        backup_path = backup_service_test.create_backup()
        assert backup_path is None

        # Verify config updated
        last_skipped_time = config.get("last_backup_skipped_time")
        assert last_skipped_time != ""
        assert datetime.fromisoformat(last_skipped_time) is not None

        last_skipped_reason = config.get("last_backup_skipped_reason")
        assert "Failed to open connection" in last_skipped_reason
