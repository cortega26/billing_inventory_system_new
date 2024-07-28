from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget
from ui.customer_view import CustomerView
from ui.product_view import ProductView
from ui.sale_view import SaleView
from ui.purchase_view import PurchaseView
from ui.inventory_view import InventoryView
from ui.analytics_view import AnalyticsView
from typing import Dict, Type

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
            except Exception as e:
                print(f"Error initializing {tab_name} view: {str(e)}")

    def closeEvent(self, event):
        # Perform any cleanup or saving operations here
        # For example, you might want to save application state or close database connections
        event.accept()