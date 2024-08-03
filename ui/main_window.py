from PySide6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout, QWidget, QMessageBox,
                               QStatusBar, QMenuBar, QMenu)
from PySide6.QtCore import Qt, QSettings, QSize, QPoint
from PySide6.QtGui import QAction
from ui.customer_view import CustomerView
from ui.dashboard_view import DashboardView
from ui.product_view import ProductView
from ui.sale_view import SaleView
from ui.purchase_view import PurchaseView
from ui.inventory_view import InventoryView
from ui.analytics_view import AnalyticsView
from typing import Dict, Type
from utils.logger import logger
from config import APP_NAME, APP_VERSION, COMPANY_NAME
from utils.event_system import event_system

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        self.settings = QSettings(COMPANY_NAME, APP_NAME)
        self.setup_ui()

    def setup_ui(self):
        try:
            # Handle window size
            size_value = self.settings.value("WindowSize")
            if isinstance(size_value, QSize):
                self.resize(size_value)
            else:
                self.resize(QSize(1200, 800))

            # Handle window position
            pos_value = self.settings.value("WindowPosition")
            if isinstance(pos_value, QPoint):
                self.move(pos_value)
            else:
                self.move(QPoint(100, 100))

            self.setup_menu_bar()
            self.setup_status_bar()

            central_widget = QWidget()
            self.setCentralWidget(central_widget)

            layout = QVBoxLayout(central_widget)

            self.tab_widget = QTabWidget()
            layout.addWidget(self.tab_widget)

            self.create_tabs()
            logger.info("Main window UI setup completed successfully")
        except Exception as e:
            logger.error(f"Error setting up main window UI: {str(e)}")
            QMessageBox.critical(self, "UI Setup Error", f"An error occurred while setting up the UI: {str(e)}")

    def setup_menu_bar(self):
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # File menu
        file_menu = QMenu("&File", self)
        menu_bar.addMenu(file_menu)

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = QMenu("&Help", self)
        menu_bar.addMenu(help_menu)

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def setup_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

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
                QMessageBox.critical(
                    self, "Initialization Error", 
                    f"Failed to initialize {tab_name} view. The application may not function correctly: {str(e)}"
                    )

        # Restore the last selected tab
        last_tab_index = self.settings.value("LastTabIndex", 0)
        if isinstance(last_tab_index, int) and 0 <= last_tab_index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(last_tab_index)
        else:
            self.tab_widget.setCurrentIndex(0)

        # Connect tab change signal
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        # Connect to global events
        event_system.product_added.connect(self.on_product_added)
        event_system.product_updated.connect(self.on_product_updated)
        event_system.product_deleted.connect(self.on_product_deleted)
        event_system.sale_added.connect(self.on_sale_added)
        event_system.purchase_added.connect(self.on_purchase_added)

    def on_tab_changed(self, index):
        self.settings.setValue("LastTabIndex", index)
        tab_name = self.tab_widget.tabText(index)
        self.status_bar.showMessage(f"Current view: {tab_name}")

    def show_about_dialog(self):
        QMessageBox.about(
            self, "About",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"Developed by {COMPANY_NAME}\n\n"
            "An inventory and billing management system."
            )

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, 'Exit', 'Are you sure you want to exit?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
            )

        if reply == QMessageBox.StandardButton.Yes:
            # Save window state
            self.settings.setValue("WindowSize", self.size())
            self.settings.setValue("WindowPosition", self.pos())
            
            logger.info("Application closed by user")
            event.accept()
        else:
            event.ignore()

    def show_status_message(self, message: str, timeout: int = 5000):
        self.status_bar.showMessage(message, timeout)

    def on_product_added(self, product_id: int):
        self.show_status_message(f"Product added (ID: {product_id})")
        self.refresh_relevant_views()

    def on_product_updated(self, product_id: int):
        self.show_status_message(f"Product updated (ID: {product_id})")
        self.refresh_relevant_views()

    def on_product_deleted(self, product_id: int):
        self.show_status_message(f"Product deleted (ID: {product_id})")
        self.refresh_relevant_views()

    def on_sale_added(self, sale_id: int):
        self.show_status_message(f"Sale added (ID: {sale_id})")
        self.refresh_relevant_views()

    def on_purchase_added(self, purchase_id: int):
        self.show_status_message(f"Purchase added (ID: {purchase_id})")
        self.refresh_relevant_views()

    def refresh_relevant_views(self):
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, ProductView):
                widget.load_products()
            elif isinstance(widget, SaleView):
                widget.load_sales()
            elif isinstance(widget, PurchaseView):
                widget.load_purchases()
            elif isinstance(widget, InventoryView):
                widget.load_inventory()
            elif isinstance(widget, CustomerView):
                widget.load_customers()
            elif isinstance(widget, DashboardView):
                widget.update_dashboard()
            elif isinstance(widget, AnalyticsView):
                widget.generate_analytics()
