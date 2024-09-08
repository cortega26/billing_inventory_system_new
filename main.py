import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from database import init_db
from utils.system.logger import logger
from utils.exceptions import DatabaseException, AppException
from utils.decorators import handle_exceptions
from config import config, APP_NAME, APP_VERSION

class Application:
    """
    Main application class responsible for initializing and running the application.
    """

    @staticmethod
    @handle_exceptions(AppException, show_dialog=True)
    def initialize():
        """
        Initialize the application by setting up the database.

        Raises:
            AppException: If there's an error initializing the database.
        """
        logger.info("Initializing the application")
        try:
            init_db()
            logger.info("Database initialized successfully")
        except DatabaseException as e:
            logger.critical(f"Failed to initialize database: {e}")
            raise AppException(f"Failed to initialize database: {e}")

    @staticmethod
    @handle_exceptions(AppException, show_dialog=True)
    def run():
        """
        Run the main application loop.

        This method sets up the QApplication, applies the theme,
        creates the main window, and starts the event loop.

        Raises:
            AppException: If there's an error during application execution.
        """
        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)

        Application.apply_theme(app)

        window = MainWindow()
        window.show()
        logger.info("Application started")
        sys.exit(app.exec())

    @staticmethod
    def apply_theme(app: QApplication):
        """
        Apply the theme specified in the configuration.

        Args:
            app (QApplication): The QApplication instance.
        """
        theme = config.get('theme', 'default')
        if theme != 'default':
            app.setStyle(theme)
        logger.info(f"Applied theme: {theme}")

    @staticmethod
    def shutdown():
        """Perform any necessary cleanup before application exit."""
        logger.info("Application shutting down")
        # Perform any necessary cleanup here
        # For example, close database connections, save application state, etc.

if __name__ == "__main__":
    try:
        Application.initialize()
        Application.run()
    except AppException as e:
        logger.critical(f"An unhandled error occurred: {e}")
        sys.exit(1)
    finally:
        Application.shutdown()
