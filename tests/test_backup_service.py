import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

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
            return default
            
        mock_config.get.side_effect = get_side_effect
        
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

def test_get_backup_dir_creates_directory(backup_service):
    backup_dir = backup_service.get_backup_dir()
    assert backup_dir.exists()
    assert backup_dir.is_dir()

def test_create_backup_success(backup_service, source_db, tmp_path):
    with patch("services.backup_service.DATABASE_PATH", source_db):
        backup_path = backup_service.create_backup()
        
        assert backup_path is not None
        assert Path(backup_path).exists()
        assert Path(backup_path).name.startswith("backup_")
        assert Path(backup_path).name.endswith(source_db.name)
        assert Path(backup_path).stat().st_size > 0

def test_create_backup_no_db(backup_service, tmp_path):
    non_existent_db = tmp_path / "non_existent.db"
    with patch("services.backup_service.DATABASE_PATH", non_existent_db):
        backup_path = backup_service.create_backup()
        assert backup_path is None

def test_cleanup_old_backups(backup_service, source_db):
    backup_dir = backup_service.get_backup_dir()
    
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

    with patch("services.backup_service.DATABASE_PATH", source_db):
        # Trigger cleanup via create_backup or call directly
        backup_service.cleanup_old_backups()
        
        assert fresh_backup.exists()
        assert not old_backup.exists()
