from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget
from ui.customer_view import CustomerView
from ui.product_view import ProductView
from ui.sale_view import SaleView
from ui.purchase_view import PurchaseView
from ui.inventory_view import InventoryView
from ui.analytics_view import AnalyticsView

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

        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        tab_widget.addTab(CustomerView(), "Customers")
        tab_widget.addTab(ProductView(), "Products")
        tab_widget.addTab(SaleView(), "Sales")
        tab_widget.addTab(PurchaseView(), "Purchases")
        tab_widget.addTab(InventoryView(), "Inventory")
        tab_widget.addTab(AnalyticsView(), "Analytics")