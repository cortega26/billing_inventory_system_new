import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.backup_service import BackupService


@pytest.fixture
def backup_service(tmp_path):
    # Reset singleton
    BackupService._instance = None

    # Mock config
    with patch("services.backup_service.config") as mock_config:
        # returns value or default
        def get_side_effect(key, default=None):
            if key == "backup_dir":
                return str(tmp_path / "backups")
            if key == "backup_retention_days":
                return 7
            if key == "backup_min_free_mb":
                return 1
            return default

        mock_config.get.side_effect = get_side_effect
        mock_config.get_active_database_path.return_value = Path("unused.db")

        service = BackupService()
        yield service, mock_config

    BackupService._instance = None


@pytest.fixture
def source_db(tmp_path):
    db_path = tmp_path / "test_db.db"
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    conn.close()
    return db_path


def test_get_backup_dir_creates_directory(backup_service):
    service, _ = backup_service
    backup_dir = service.get_backup_dir()
    assert backup_dir.exists()
    assert backup_dir.is_dir()


def test_get_backup_dir_scoped_to_business(backup_service):
    service, mock_config = backup_service
    mock_config.get.side_effect = lambda key, default=None: (
        str(Path.cwd() / "backups") if key == "backup_dir" else default
    )

    backup_dir = service.get_backup_dir()
    assert backup_dir.name == "default"


def test_create_backup_success(backup_service, source_db):
    service, mock_config = backup_service
    mock_config.get_active_database_path.return_value = source_db

    backup_path = service.create_backup()

    assert backup_path is not None
    assert Path(backup_path).exists()
    assert Path(backup_path).name.startswith("backup_")
    assert Path(backup_path).name.endswith(source_db.name)
    assert Path(backup_path).stat().st_size > 0
    # Backup lands in backups/<business_id>/
    assert Path(backup_path).parent == service.get_backup_dir()


def test_create_backup_no_db(backup_service):
    service, mock_config = backup_service
    non_existent_db = Path("non_existent.db")
    mock_config.get_active_database_path.return_value = non_existent_db

    backup_path = service.create_backup()
    assert backup_path is None


def test_create_backup_skips_when_disk_space_low(backup_service, source_db):
    service, mock_config = backup_service
    mock_config.get_active_database_path.return_value = source_db

    with patch(
        "services.backup_service.shutil.disk_usage",
        return_value=SimpleNamespace(total=100, used=100, free=0),
    ):
        backup_path = service.create_backup()
        assert backup_path is None


def test_create_backup_emits_event_when_disk_space_low(backup_service, source_db):
    service, mock_config = backup_service
    mock_config.get_active_database_path.return_value = source_db

    with (
        patch(
            "services.backup_service.shutil.disk_usage",
            return_value=SimpleNamespace(total=100, used=100, free=0),
        ),
        patch("services.backup_service.event_system") as mock_event_system,
    ):
        backup_path = service.create_backup()

        assert backup_path is None
        mock_event_system.emit_event.assert_called_once()
        args, _ = mock_event_system.emit_event.call_args
        assert args[0] == "backup_skipped"
        assert args[1]["reason"] == "low_disk_space"


def test_cleanup_old_backups(backup_service, source_db):
    service, mock_config = backup_service
    mock_config.get_active_database_path.return_value = source_db

    backup_dir = service.get_backup_dir()

    # Create a fresh backup
    fresh_backup = backup_dir / "backup_fresh.db"
    fresh_backup.write_text("fresh")

    # Create an old backup (8 days old)
    old_backup = backup_dir / "backup_old.db"
    old_backup.write_text("old")

    # Modify mtime to be 8 days ago
    eight_days_ago = time.time() - (8 * 86400) - 100
    try:
        import os

        os.utime(old_backup, (eight_days_ago, eight_days_ago))
    except Exception:
        # Fallback if os.utime fails (e.g. permission), skip test part
        pass

    # Trigger cleanup via create_backup or call directly
    service.cleanup_old_backups()

    assert fresh_backup.exists()
    assert not old_backup.exists()
