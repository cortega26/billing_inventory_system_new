import sqlite3
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from config import DATABASE_PATH
from database import init_db
from database.database_manager import DatabaseManager
from ui.main_window import MainWindow
from utils.decorators import handle_exceptions
from utils.exceptions import AppException, DatabaseException
from utils.system.logger import logger


STARTUP_GUARD_TABLES = (
    "customers",
    "customer_identifiers",
    "products",
    "inventory",
    "sales",
    "sale_items",
    "purchases",
    "purchase_items",
)

TABLE_COUNT_QUERIES = {
    "customers": "SELECT COUNT(*) AS count FROM customers",
    "customer_identifiers": "SELECT COUNT(*) AS count FROM customer_identifiers",
    "products": "SELECT COUNT(*) AS count FROM products",
    "inventory": "SELECT COUNT(*) AS count FROM inventory",
    "sales": "SELECT COUNT(*) AS count FROM sales",
    "sale_items": "SELECT COUNT(*) AS count FROM sale_items",
    "purchases": "SELECT COUNT(*) AS count FROM purchases",
    "purchase_items": "SELECT COUNT(*) AS count FROM purchase_items",
}

TABLE_TOTAL_QUERIES = {
    "customers": "SELECT COUNT(*) FROM customers",
    "customer_identifiers": "SELECT COUNT(*) FROM customer_identifiers",
    "products": "SELECT COUNT(*) FROM products",
    "inventory": "SELECT COUNT(*) FROM inventory",
    "sales": "SELECT COUNT(*) FROM sales",
    "sale_items": "SELECT COUNT(*) FROM sale_items",
    "purchases": "SELECT COUNT(*) FROM purchases",
    "purchase_items": "SELECT COUNT(*) FROM purchase_items",
}


def _get_primary_table_counts() -> dict[str, int]:
    counts = {}
    for table in STARTUP_GUARD_TABLES:
        row = DatabaseManager.fetch_one(TABLE_COUNT_QUERIES[table])
        counts[table] = row["count"] if row else 0
    return counts


def _count_records_in_database_file(db_path: Path) -> int:
    total = 0
    connection = sqlite3.connect(str(db_path))
    try:
        cursor = connection.cursor()
        for table in STARTUP_GUARD_TABLES:
            try:
                cursor.execute(TABLE_TOTAL_QUERIES[table])
                total += int(cursor.fetchone()[0])
            except sqlite3.Error:
                continue
    finally:
        connection.close()
    return total


def _iter_recovery_candidate_paths(active_db_path: Path):
    seen_paths = set()
    active_resolved = active_db_path.resolve()
    for search_root in (active_db_path.parent, active_db_path.parent / "backups"):
        if not search_root.exists():
            continue
        for candidate in search_root.glob("*.db"):
            resolved = candidate.resolve()
            if resolved == active_resolved:
                continue
            if "recovery" in candidate.parts or resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            yield candidate


def _find_recovery_candidate(active_db_path: Path) -> tuple[Path, int] | None:
    candidates = []
    for candidate in _iter_recovery_candidate_paths(active_db_path):
        total_records = _count_records_in_database_file(candidate)
        if total_records > 0:
            candidates.append((candidate, total_records, candidate.stat().st_mtime))

    if not candidates:
        return None

    best_path, best_total, _ = max(candidates, key=lambda item: (item[1], item[2]))
    return best_path, best_total


def _build_empty_database_warning(db_already_existed: bool) -> str | None:
    if not db_already_existed:
        return None

    current_counts = _get_primary_table_counts()
    if sum(current_counts.values()) > 0:
        return None

    active_db_path = Path(DATABASE_PATH)
    recovery_candidate = _find_recovery_candidate(active_db_path)
    if recovery_candidate is None:
        return (
            "La base de datos activa esta vacia.\n\n"
            f"Archivo activo: {active_db_path}\n\n"
            "No se encontro automaticamente otra copia con datos. "
            "Revise sus backups antes de seguir operando."
        )

    candidate_path, candidate_total = recovery_candidate
    return (
        "La base de datos activa esta vacia.\n\n"
        f"Archivo activo: {active_db_path}\n"
        f"Copia con datos detectada: {candidate_path} ({candidate_total} registros en tablas principales).\n\n"
        "No se restauro nada automaticamente. Revise o restaure la copia correcta antes de seguir operando."
    )


def _show_startup_warning(message: str) -> None:
    if "pytest" in sys.modules:
        logger.warning(message)
        return
    QMessageBox.warning(
        QApplication.activeWindow(),
        "Advertencia de base de datos",
        message,
    )


def _warn_if_active_database_looks_empty(db_already_existed: bool) -> None:
    warning_message = _build_empty_database_warning(db_already_existed)
    if warning_message:
        logger.warning(warning_message)
        _show_startup_warning(warning_message)


class Application:
    @staticmethod
    @handle_exceptions(AppException, show_dialog=True)
    def initialize():
        logger.info("Initializing the application")
        try:
            db_already_existed = DATABASE_PATH.exists()
            init_db()
            _warn_if_active_database_looks_empty(db_already_existed)
            from services.backup_service import backup_service

            backup_service.start_scheduler()
        except DatabaseException as e:
            logger.critical(f"Failed to initialize database: {e}")
            raise AppException(f"Failed to initialize database: {e}")

    # @staticmethod
    # def run():
    #     # Logic moved to main block
    #     pass


if __name__ == "__main__":
    # Create QApplication first to ensure UI elemens (like error dialogs) can be created
    app = QApplication(sys.argv)

    from ui.styles import apply_theme

    apply_theme(app)

    try:
        Application.initialize()

        # Run the main window setup and execution
        window = MainWindow()
        window.show()
        logger.info("Application started")
        sys.exit(app.exec())
    except AppException as e:
        logger.critical(f"An unhandled error occurred: {e}")
