
import pytest
import sqlite3
import threading
import time
import os
from pathlib import Path
from services.backup_service import BackupService
from database.database_manager import DatabaseManager
from database import database_manager
from utils.system.logger import logger

class TestPerfBackup:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, mocker):
        # Initialize DB in memory
        DatabaseManager.initialize(":memory:")
        # Create schema
        with DatabaseManager.get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS perf_test (id INTEGER PRIMARY KEY, name TEXT)")
        
        # Patch backup dir to tmp_path
        mocker.patch.object(BackupService, 'get_backup_dir', return_value=tmp_path)
        # Patch DATABASE_PATH to a dummy path for naming
        # Patch DATABASE_PATH to a dummy path that claims to exist
        mock_db_path = mocker.MagicMock(spec=Path)
        mock_db_path.exists.return_value = True
        mock_db_path.name = "test.db"
        mocker.patch("services.backup_service.DATABASE_PATH", mock_db_path)
        
        # Clean Logger mock
        self.mock_logger = mocker.patch("database.database_manager.logger")
        self.mocker = mocker
        
        self.bs = BackupService()
        
    def test_backup_atomicity(self):
        # Start a thread writing to DB
        stop_event = threading.Event()
        
        def writer_loop():
            try:
                i = 0
                while not stop_event.is_set():
                    DatabaseManager.execute_query("INSERT INTO perf_test (name) VALUES (?)", (f"item_{i}",))
                    i += 1
                    time.sleep(0.001) # fast writes
            except Exception as e:
                print(f"Writer failed: {e}")

        t = threading.Thread(target=writer_loop)
        t.start()
        
        # Let it write some data
        time.sleep(0.1)
        
        # Create backup
        backup_path_str = self.bs.create_backup()
        
        # Stop writer
        stop_event.set()
        t.join()
        
        assert backup_path_str is not None
        backup_path = Path(backup_path_str)
        assert backup_path.exists()
        
        # Verify backup integrity
        # Connect to backup file
        bk_conn = sqlite3.connect(backup_path)
        cursor = bk_conn.cursor()
        
        # Check integrity
        integrity = cursor.execute("PRAGMA integrity_check").fetchone()[0]
        assert integrity == "ok"
        
        # Check count
        count = cursor.execute("SELECT COUNT(*) FROM perf_test").fetchone()[0]
        assert count > 0
        print(f"Backup captured {count} rows")
        
        bk_conn.close()

    def test_performance_logging(self):
        # Set threshold to 0 to catch all
        original_threshold = database_manager.SLOW_QUERY_THRESHOLD_MS
        database_manager.SLOW_QUERY_THRESHOLD_MS = 0
        
        # Mock perf_counter to guarantee > 0 duration
        # side_effect: start_time, end_time. dur = 1.0 - 0.0 = 1.0s = 1000ms > 0
        # DatabaseManager calls perf_counter twice per query.
        self.mocker.patch("time.perf_counter", side_effect=[0.0, 1.0, 2.0, 3.0])
        
        try:
            # Run a query
            DatabaseManager.execute_query("SELECT * FROM perf_test")
            
            # Check log
            # logger.warning should have been called
            assert self.mock_logger.warning.called
            args = self.mock_logger.warning.call_args[0][0]
            assert "Slow query" in args
            print(f"Log message caught: {args}")
            
        finally:
            database_manager.SLOW_QUERY_THRESHOLD_MS = original_threshold

            
if __name__ == "__main__":
    # Standalone run logic
    pass
