import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from database import init_db
from utils.system.logger import logger

def initialize_application():
    logger.info("Initializing the application")
    try:
        init_db()
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}")
        sys.exit(1)

def execute_application():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    logger.info("Application started")
    sys.exit(app.exec())

if __name__ == "__main__":
    try:
        initialize_application()
        execute_application()
    except Exception as e:
        logger.critical(f"An unhandled error occurred: {e}")
        sys.exit(1)