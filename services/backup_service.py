import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import sqlite3
from config import config, DATABASE_PATH
from database.database_manager import DatabaseManager
from utils.system.logger import logger

class BackupService:
    _instance: Optional["BackupService"] = None
    _lock = threading.Lock()
    _stop_event = threading.Event()
    _scheduler_thread: Optional[threading.Thread] = None

    def __new__(cls) -> "BackupService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(BackupService, cls).__new__(cls)
        return cls._instance

    def get_backup_dir(self) -> Path:
        """Get the directory where backups are stored."""
        backup_dir = Path(config.get("backup_dir", "backups"))
        if not backup_dir.is_absolute():
            # Relative to project root (assuming CWD is project root)
            backup_dir = Path.cwd() / backup_dir
        
        if not backup_dir.exists():
            try:
                backup_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create backup directory: {e}")
                # Fallback to temp dir? No, critical failure.
                raise
        return backup_dir

    def create_backup(self) -> Optional[str]:
        """
        Creates a backup of the current database.
        Returns the path to the backup file if successful, None otherwise.
        """
        try:
            db_path = DATABASE_PATH
            if not db_path.exists():
                logger.error(f"Database file not found at {db_path}")
                return None
            
            backup_dir = self.get_backup_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}_{db_path.name}"
            backup_path = backup_dir / backup_filename

            # Use SQLite native backup API for consistency
            # Open destination connection
            dest_conn = sqlite3.connect(str(backup_path))
            
            try:
                # Get source connection
                # We use the existing connection from DatabaseManager to ensure we capture current state including WAL
                with DatabaseManager.get_db_connection() as source_conn:
                    source_conn.backup(dest_conn)
                
                logger.info(f"Backup created successfully (sqlite3 backup): {backup_path}")
                
                # Also cleanup old backups after creating a new one
                self.cleanup_old_backups()
                
                return str(backup_path)
            finally:
                dest_conn.close()

        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            if 'backup_path' in locals() and backup_path.exists():
                try:
                    backup_path.unlink()
                except Exception:
                    pass
            return None

    def cleanup_old_backups(self) -> None:
        """Removes backups older than the configured retention period."""
        try:
            retention_days = config.get("backup_retention_days", 7)
            backup_dir = self.get_backup_dir()
            
            now = time.time()
            cutoff = now - (retention_days * 86400)

            for item in backup_dir.glob("backup_*.db"):
                if item.stat().st_mtime < cutoff:
                    try:
                        item.unlink()
                        logger.info(f"Deleted old backup: {item}")
                    except Exception as e:
                        logger.error(f"Failed to delete old backup {item}: {e}")

        except Exception as e:
            logger.error(f"Error during backup cleanup: {e}")

    def start_scheduler(self) -> None:
        """Starts the background scheduler for automated backups."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("Backup scheduler is already running.")
            return

        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info("Backup scheduler started.")

    def stop_scheduler(self) -> None:
        """Stops the background scheduler."""
        if self._scheduler_thread:
            self._stop_event.set()
            self._scheduler_thread.join(timeout=5)
            logger.info("Backup scheduler stopped.")

    def _scheduler_loop(self) -> None:
        """Loop to check if it's time to backup."""
        # Run one immediately on startup? Or wait?
        # Let's run safe check: if no backup exists for today, create one?
        # Or simply rely on interval.
        # Config interval is in hours.
        
        while not self._stop_event.is_set():
            try:
                # Interval check logic could be more complex (e.g., store last backup time in config),
                # but valid simple approach: Sleep for interval.
                # However, if app restarts often, we might spam backups or miss them.
                # Better: Check modification time of latest backup.
                
                interval_hours = config.get("backup_interval", 24)
                interval_seconds = interval_hours * 3600
                
                if self._should_run_backup(interval_seconds):
                    self.create_backup()
                
                # Check every minute
                time.sleep(60) 
            except Exception as e:
                logger.error(f"Error in backup scheduler loop: {e}")
                time.sleep(300) # Retry after 5 mins on error

    def _should_run_backup(self, interval_seconds: int) -> bool:
        """Check if enough time has passed since last backup."""
        try:
            backup_dir = self.get_backup_dir()
            backups = list(backup_dir.glob("backup_*.db"))
            if not backups:
                return True
            
            latest_backup = max(backups, key=lambda p: p.stat().st_mtime)
            time_since_last = time.time() - latest_backup.stat().st_mtime
            
            return time_since_last >= interval_seconds
        except Exception:
            return True

backup_service = BackupService()
