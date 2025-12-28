import sys

from PySide6.QtWidgets import QApplication

from database import init_db
from ui.main_window import MainWindow
from utils.decorators import handle_exceptions
from utils.exceptions import AppException, DatabaseException
from utils.system.logger import logger


class Application:
    @staticmethod
    @handle_exceptions(AppException, show_dialog=True)
    def initialize():
        logger.info("Initializing the application")
        try:
            init_db()
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
