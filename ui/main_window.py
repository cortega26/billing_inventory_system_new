from typing import Dict, Optional, Protocol, Type, cast

from PySide6.QtCore import QPoint, QSettings, QSize
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, APP_VERSION, COMPANY_NAME
from ui.analytics_view import AnalyticsView
from ui.audit_log_view import AuditLogView
from ui.customer_view import CustomerView
from ui.dashboard_view import DashboardView
from ui.inventory_view import InventoryView
from ui.product_view import ProductView
from ui.purchase_view import PurchaseView
from ui.sale_view import SaleView
from utils.decorators import handle_exceptions, ui_operation
from utils.exceptions import UIException
from utils.system.event_system import event_system
from utils.system.logger import logger


class RefreshableWidget(Protocol):
    def refresh(self) -> None: ...


class ExportableWidget(Protocol):
    def export_current_view(self) -> None: ...


def build_backup_skipped_status_message(payload: object) -> str:
    """Build a user-facing status message for skipped backup events."""
    if isinstance(payload, dict) and payload.get("reason") == "low_disk_space":
        return "Alerta: copia de seguridad omitida por espacio insuficiente en disco"
    return "Alerta: copia de seguridad omitida"


DASHBOARD_TAB = "Panel"
CUSTOMERS_TAB = "Clientes"
PRODUCTS_TAB = "Productos"
SALES_TAB = "Ventas"
PURCHASES_TAB = "Compras"
INVENTORY_TAB = "Inventario"
ANALYTICS_TAB = "Analíticas"
AUDIT_TAB = "Auditoría"

PRODUCT_REFRESH_TARGETS = (
    DASHBOARD_TAB,
    PRODUCTS_TAB,
    SALES_TAB,
    PURCHASES_TAB,
    INVENTORY_TAB,
    ANALYTICS_TAB,
    AUDIT_TAB,
)
CUSTOMER_REFRESH_TARGETS = (
    CUSTOMERS_TAB,
    SALES_TAB,
    AUDIT_TAB,
)
SALE_REFRESH_TARGETS = (
    DASHBOARD_TAB,
    SALES_TAB,
    INVENTORY_TAB,
    ANALYTICS_TAB,
    AUDIT_TAB,
)
PURCHASE_REFRESH_TARGETS = (
    DASHBOARD_TAB,
    PURCHASES_TAB,
    INVENTORY_TAB,
    ANALYTICS_TAB,
    AUDIT_TAB,
)
INVENTORY_REFRESH_TARGETS = (
    DASHBOARD_TAB,
    SALES_TAB,
    PURCHASES_TAB,
    INVENTORY_TAB,
    AUDIT_TAB,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - v{APP_VERSION}")
        self.settings = QSettings(COMPANY_NAME, APP_NAME)
        self.views_by_name: Dict[str, QWidget] = {}
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
            self.setup_global_shortcuts()

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
            "&Archivo",
            [
                ("&Exportar Datos", "Ctrl+E", self.export_data),
                ("&Importar Datos", "Ctrl+I", self.import_data),
                ("&Crear Copia de Seguridad", None, self.backup_data),
                ("&Salir", QKeySequence.StandardKey.Quit, self.close),
            ],
        )
        view_menu = self.create_menu(
            "&Ver",
            [
                (
                    "&Actualizar",
                    QKeySequence.StandardKey.Refresh,
                    self.refresh_current_tab,
                )
            ],
        )
        help_menu = self.create_menu(
            "&Ayuda",
            [
                (
                    "&Guía de Usuario",
                    QKeySequence.StandardKey.HelpContents,
                    self.show_user_guide,
                ),
                ("&Acerca de", None, self.show_about_dialog),
            ],
        )

        menu_bar.addMenu(file_menu)
        menu_bar.addMenu(view_menu)
        menu_bar.addMenu(help_menu)

    def setup_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")

    def setup_global_shortcuts(self):
        """Setup global keyboard shortcuts for navigation."""
        shortcuts = {
            "F1": 3,  # Sales (mapped to index 3 in create_tabs)
            "F2": 5,  # Inventory (mapped to index 5 in create_tabs)
            "F3": 2,  # Products (mapped to index 2 in create_tabs)
            "F4": 1,  # Customers (mapped to index 1 in create_tabs)
            "F5": 0,  # Dashboard (mapped to index 0 in create_tabs)
            "F6": 4,  # Purchases (mapped to index 4 in create_tabs)
            "F7": 6,  # Analytics
            "F8": 7,  # Audit log
        }

        for key, index in shortcuts.items():
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            # Use default argument capture to bind the specific index
            action.triggered.connect(
                lambda checked=False, idx=index: self.switch_to_tab(idx)
            )
            self.addAction(action)

    @ui_operation()
    def switch_to_tab(self, index: int):
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def create_tabs(self):
        try:
            tabs: Dict[str, Type[QWidget]] = {
                DASHBOARD_TAB: DashboardView,
                CUSTOMERS_TAB: CustomerView,
                PRODUCTS_TAB: ProductView,
                SALES_TAB: SaleView,
                PURCHASES_TAB: PurchaseView,
                INVENTORY_TAB: InventoryView,
                ANALYTICS_TAB: AnalyticsView,
                AUDIT_TAB: AuditLogView,
            }

            self.views_by_name = {}
            for tab_name, view_class in tabs.items():
                view = view_class()
                self.views_by_name[tab_name] = view
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
        event_system.connect_to_event("product_added", self.on_product_added)
        event_system.connect_to_event("product_updated", self.on_product_updated)
        event_system.connect_to_event("product_deleted", self.on_product_deleted)
        event_system.connect_to_event("customer_added", self.on_customer_changed)
        event_system.connect_to_event("customer_updated", self.on_customer_changed)
        event_system.connect_to_event("customer_deleted", self.on_customer_changed)
        event_system.connect_to_event("sale_added", self.on_sale_added)
        event_system.connect_to_event("sale_updated", self.on_sale_changed)
        event_system.connect_to_event("sale_deleted", self.on_sale_changed)
        event_system.connect_to_event("purchase_added", self.on_purchase_added)
        event_system.connect_to_event("purchase_updated", self.on_purchase_changed)
        event_system.connect_to_event("purchase_deleted", self.on_purchase_changed)
        event_system.connect_to_event("inventory_changed", self.on_inventory_changed)
        event_system.connect_to_event("backup_skipped", self.on_backup_skipped)

    @ui_operation(show_dialog=True)
    def on_tab_changed(self, index):
        self.settings.setValue("LastTabIndex", index)
        tab_name = self.tab_widget.tabText(index)
        self.status_bar.showMessage(f"Vista actual: {tab_name}")

    @ui_operation(show_dialog=True)
    def show_about_dialog(self):
        QMessageBox.about(
            self,
            "Acerca de",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"Desarrollado por {COMPANY_NAME}\n\n"
            "Sistema de inventario y facturación.",
        )

    @ui_operation(show_dialog=True)
    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "Salir",
            "¿Está seguro que desea salir?",
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
        self.show_status_message(f"Producto agregado (ID: {product_id})")
        self.refresh_relevant_views(PRODUCT_REFRESH_TARGETS)

    @ui_operation(show_dialog=True)
    def on_product_updated(self, product_id: int):
        self.show_status_message(f"Producto actualizado (ID: {product_id})")
        self.refresh_relevant_views(PRODUCT_REFRESH_TARGETS)

    @ui_operation(show_dialog=True)
    def on_product_deleted(self, product_id: int):
        self.show_status_message(f"Producto eliminado (ID: {product_id})")
        self.refresh_relevant_views(PRODUCT_REFRESH_TARGETS)

    @ui_operation(show_dialog=True)
    def on_customer_changed(self, _payload: object = None):
        self.refresh_relevant_views(CUSTOMER_REFRESH_TARGETS)

    @ui_operation(show_dialog=True)
    def on_sale_added(self, sale_id: int):
        self.show_status_message(f"Venta agregada (ID: {sale_id})")
        self.refresh_relevant_views(SALE_REFRESH_TARGETS)

    @ui_operation(show_dialog=True)
    def on_sale_changed(self, _payload: object = None):
        self.refresh_relevant_views(SALE_REFRESH_TARGETS)

    @ui_operation(show_dialog=True)
    def on_purchase_added(self, purchase_id: int):
        self.show_status_message(f"Compra agregada (ID: {purchase_id})")
        self.refresh_relevant_views(PURCHASE_REFRESH_TARGETS)

    @ui_operation(show_dialog=True)
    def on_purchase_changed(self, _payload: object = None):
        self.refresh_relevant_views(PURCHASE_REFRESH_TARGETS)

    @ui_operation(show_dialog=True)
    def on_backup_skipped(self, payload: object):
        message = build_backup_skipped_status_message(payload)
        logger.warning(message)
        # Keep visible longer to increase operator awareness.
        self.show_status_message(message, timeout=15000)

    @ui_operation(show_dialog=True)
    def on_inventory_changed(self, _payload: object = None):
        self.refresh_relevant_views(INVENTORY_REFRESH_TARGETS)

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def refresh_relevant_views(
        self, target_tab_names: Optional[tuple[str, ...]] = None
    ):
        try:
            if target_tab_names is None:
                target_tab_names = tuple(self.views_by_name.keys())

            refreshed_tabs = set()
            for tab_name in target_tab_names:
                if tab_name in refreshed_tabs:
                    continue
                refreshed_tabs.add(tab_name)

                widget = self.views_by_name.get(tab_name)
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
        current_widget = self.tab_widget.currentWidget()
        if hasattr(current_widget, "export_current_view") and callable(
            getattr(current_widget, "export_current_view")
        ):
            exportable_widget = cast(ExportableWidget, current_widget)
            exportable_widget.export_current_view()
            return

        self.show_status_message("La vista actual no tiene exportación disponible")

    @ui_operation(show_dialog=True)
    def import_data(self):
        self.show_status_message("Importación de datos iniciada")
        # TODO: Implement actual data import logic

    @ui_operation(show_dialog=True)
    def backup_data(self):
        from services.backup_service import backup_service

        try:
            self.show_status_message("Creando copia de seguridad...")
            backup_path = backup_service.create_backup()
            if backup_path:
                QMessageBox.information(
                    self,
                    "Copia de Seguridad Exitosa",
                    f"Copia de seguridad creada en:\n{backup_path}",
                )
                self.show_status_message("Copia de seguridad creada exitosamente")
            else:
                QMessageBox.warning(
                    self,
                    "Error de Copia de Seguridad",
                    "Error al crear la copia de seguridad. Revise los registros para más detalles.",
                )
                self.show_status_message("Fallo en la copia de seguridad")
        except Exception as e:
            logger.error(f"Manual backup error: {e}")
            QMessageBox.critical(
                self, "Error en Copia de Seguridad", f"Ha ocurrido un error: {e}"
            )

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
            self.show_status_message("Vista actualizada")
        except Exception as e:
            logger.error(f"Error refreshing current tab: {str(e)}")
            raise UIException(f"Failed to refresh current tab: {str(e)}")

    @ui_operation(show_dialog=True)
    def show_user_guide(self):
        QMessageBox.information(
            self, "Guía de Usuario", "El contenido de la guía de usuario va aquí."
        )
        # TODO: Implement actual user guide content or link to documentation
