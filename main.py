import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from database import init_db
from utils.system.logger import logger
from utils.exceptions import DatabaseException, AppException
from utils.decorators import handle_exceptions


class Application:
    @staticmethod
    @handle_exceptions(AppException, show_dialog=True)
    def initialize():
        logger.info("Initializing the application")
        try:
            init_db()
        except DatabaseException as e:
            logger.critical(f"Failed to initialize database: {e}")
            raise AppException(f"Failed to initialize database: {e}")

    @staticmethod
    @handle_exceptions(AppException, show_dialog=True)
    def run():
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        logger.info("Application started")
        sys.exit(app.exec())


if __name__ == "__main__":
    try:
        Application.initialize()
        Application.run()
    except AppException as e:
        logger.critical(f"An unhandled error occurred: {e}")
        sys.exit(1)

