from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QWidget, QMessageBox, QStatusBar, QMenuBar, QMenu
)
from PySide6.QtCore import Qt, QSettings, QSize, QPoint
from PySide6.QtGui import QAction, QKeySequence
from ui.customer_view import CustomerView
from ui.dashboard_view import DashboardView
from ui.product_view import ProductView
from ui.sale_view import SaleView
from ui.purchase_view import PurchaseView
from ui.inventory_view import InventoryView
from ui.analytics_view import AnalyticsView
from typing import Protocol, Dict, Type, cast
from utils.system.logger import logger
from config import config, APP_NAME, APP_VERSION, COMPANY_NAME
from utils.system.event_system import event_system
from utils.decorators import ui_operation, handle_exceptions
from utils.exceptions import UIException

class RefreshableWidget(Protocol):
    def refresh(self) -> None: ...

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        self.settings = QSettings(COMPANY_NAME, APP_NAME)
        self.setup_ui()

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def setup_ui(self):
        try:
            # Handle window size
            size = self.settings.value("WindowSize")
            if isinstance(size, QSize):
                self.resize(size)
            else:
                self.resize(QSize(1200, 800))

            # Handle window position
            pos = self.settings.value("WindowPosition")
            if isinstance(pos, QPoint):
                self.move(pos)
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
            raise UIException(f"Failed to set up main window UI: {str(e)}")

    def setup_menu_bar(self):
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        file_menu = self.create_menu(
            "&File",
            [
                ("&Export Data", "Ctrl+E", self.export_data),
                ("&Import Data", "Ctrl+I", self.import_data),
                ("E&xit", QKeySequence.StandardKey.Quit, self.close),
            ],
        )
        view_menu = self.create_menu(
            "&View",
            [("&Refresh", QKeySequence.StandardKey.Refresh, self.refresh_current_tab)],
        )
        help_menu = self.create_menu(
            "&Help",
            [
                (
                    "&User Guide",
                    QKeySequence.StandardKey.HelpContents,
                    self.show_user_guide,
                ),
                ("&About", None, self.show_about_dialog),
            ],
        )

        menu_bar.addMenu(file_menu)
        menu_bar.addMenu(view_menu)
        menu_bar.addMenu(help_menu)

    def setup_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def create_tabs(self):
        try:
            tabs: Dict[str, Type[QWidget]] = {
                "Dashboard": DashboardView,
                "Customers": CustomerView,
                "Products": ProductView,
                "Sales": SaleView,
                "Purchases": PurchaseView,
                "Inventory": InventoryView,
                "Analytics": AnalyticsView,
            }

            for tab_name, view_class in tabs.items():
                view = view_class()
                self.tab_widget.addTab(view, tab_name)
                logger.info(f"Added {tab_name} tab successfully")

            self.restore_last_tab()
            self.tab_widget.currentChanged.connect(self.on_tab_changed)

            self.connect_to_events()
        except Exception as e:
            logger.error(f"Error creating tabs: {str(e)}")
            raise UIException(f"Failed to create tabs: {str(e)}")

    def restore_last_tab(self):
        last_tab_index = self.settings.value("LastTabIndex", 0)
        if (
            isinstance(last_tab_index, int)
            and 0 <= last_tab_index < self.tab_widget.count()
        ):
            self.tab_widget.setCurrentIndex(last_tab_index)
        else:
            self.tab_widget.setCurrentIndex(0)

    def connect_to_events(self):
        event_system.product_added.connect(self.on_product_added)
        event_system.product_updated.connect(self.on_product_updated)
        event_system.product_deleted.connect(self.on_product_deleted)
        event_system.sale_added.connect(self.on_sale_added)
        event_system.purchase_added.connect(self.on_purchase_added)

    @ui_operation(show_dialog=True)
    def on_tab_changed(self, index):
        self.settings.setValue("LastTabIndex", index)
        tab_name = self.tab_widget.tabText(index)
        self.status_bar.showMessage(f"Current view: {tab_name}")

    @ui_operation(show_dialog=True)
    def show_about_dialog(self):
        QMessageBox.about(
            self,
            "About",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"Developed by {COMPANY_NAME}\n\n"
            "An inventory and billing management system.",
        )

    @ui_operation(show_dialog=True)
    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "Exit",
            "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.settings.setValue("WindowSize", self.size())
            self.settings.setValue("WindowPosition", self.pos())

            logger.info("Application closed by user")
            event.accept()
        else:
            event.ignore()

    def show_status_message(self, message: str, timeout: int = 5000):
        self.status_bar.showMessage(message, timeout)

    @ui_operation(show_dialog=True)
    def on_product_added(self, product_id: int):
        self.show_status_message(f"Product added (ID: {product_id})")
        self.refresh_relevant_views()

    @ui_operation(show_dialog=True)
    def on_product_updated(self, product_id: int):
        self.show_status_message(f"Product updated (ID: {product_id})")
        self.refresh_relevant_views()

    @ui_operation(show_dialog=True)
    def on_product_deleted(self, product_id: int):
        self.show_status_message(f"Product deleted (ID: {product_id})")
        self.refresh_relevant_views()

    @ui_operation(show_dialog=True)
    def on_sale_added(self, sale_id: int):
        self.show_status_message(f"Sale added (ID: {sale_id})")
        self.refresh_relevant_views()

    @ui_operation(show_dialog=True)
    def on_purchase_added(self, purchase_id: int):
        self.show_status_message(f"Purchase added (ID: {purchase_id})")
        self.refresh_relevant_views()

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def refresh_relevant_views(self):
        try:
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if hasattr(widget, "refresh") and callable(getattr(widget, "refresh")):
                    refreshable_widget = cast(RefreshableWidget, widget)
                    refreshable_widget.refresh()
        except Exception as e:
            logger.error(f"Error refreshing views: {str(e)}")
            raise UIException(f"Failed to refresh views: {str(e)}")

    def create_menu(self, name: str, actions: list) -> QMenu:
        menu = QMenu(name, self)
        for action_name, shortcut, callback in actions:
            action = QAction(action_name, self)
            if shortcut:
                if isinstance(shortcut, QKeySequence.StandardKey):
                    action.setShortcut(QKeySequence(shortcut))
                else:
                    action.setShortcut(shortcut)
            action.triggered.connect(callback)
            menu.addAction(action)
        return menu

    @ui_operation(show_dialog=True)
    def export_data(self):
        self.show_status_message("Data export initiated")
        # TODO: Implement actual data export logic

    @ui_operation(show_dialog=True)
    def import_data(self):
        self.show_status_message("Data import initiated")
        # TODO: Implement actual data import logic

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def refresh_current_tab(self):
        try:
            current_widget = self.tab_widget.currentWidget()
            if hasattr(current_widget, "refresh") and callable(
                getattr(current_widget, "refresh")
            ):
                refreshable_widget = cast(RefreshableWidget, current_widget)
                refreshable_widget.refresh()
            self.show_status_message("View refreshed")
        except Exception as e:
            logger.error(f"Error refreshing current tab: {str(e)}")
            raise UIException(f"Failed to refresh current tab: {str(e)}")

    @ui_operation(show_dialog=True)
    def show_user_guide(self):
        QMessageBox.information(self, "User Guide", "User guide content goes here.")
        # TODO: Implement actual user guide content or link to documentation
