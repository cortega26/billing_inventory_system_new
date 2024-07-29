from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget, QMessageBox
from ui.customer_view import CustomerView
from ui.dashboard_view import DashboardView
from ui.product_view import ProductView
from ui.sale_view import SaleView
from ui.purchase_view import PurchaseView
from ui.inventory_view import InventoryView
from ui.analytics_view import AnalyticsView
from typing import Dict, Type
from utils.logger import logger

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Inventory and Billing System")
        self.setGeometry(100, 100, 1200, 800)
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        self.create_tabs()

    def create_tabs(self):
        tabs: Dict[str, Type[QWidget]] = {
            "Dashboard": DashboardView,
            "Customers": CustomerView,
            "Products": ProductView,
            "Sales": SaleView,
            "Purchases": PurchaseView,
            "Inventory": InventoryView,
            "Analytics": AnalyticsView
        }

        for tab_name, view_class in tabs.items():
            try:
                view = view_class()
                self.tab_widget.addTab(view, tab_name)
                logger.info(f"Added {tab_name} tab successfully")
            except Exception as e:
                logger.error(f"Error initializing {tab_name} view: {str(e)}")
                QMessageBox.critical(self, "Initialization Error", 
                                     f"Failed to initialize {tab_name} view. The application may not function correctly.")

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Exit', 'Are you sure you want to exit?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            logger.info("Application closed by user")
            event.accept()
        else:
            event.ignore()