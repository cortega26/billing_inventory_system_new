import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from database import init_db

def main():
    # Initialize the database
    init_db()
    
    # Create and run the application
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()