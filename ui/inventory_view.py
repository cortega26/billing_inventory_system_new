import random
import string
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QHeaderView,
)

from services.category_service import CategoryService
from services.inventory_service import InventoryService
from services.product_service import ProductService
from utils.decorators import handle_exceptions, ui_operation
from utils.exceptions import DatabaseException, UIException, ValidationException
from utils.helpers import create_table, show_error_message, show_info_message
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.ui.table_items import NumericTableWidgetItem
from utils.validation.validators import validate_string


class EditInventoryDialog(QDialog):
    def __init__(self, item: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle(f"Editar {item['product_name']}")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        # Show barcode if exists
        if self.item.get("barcode"):
            barcode_label = QLabel(self.item["barcode"])
            layout.addRow("Código:", barcode_label)

        # Quantity input (Read-only current quantity)
        self.current_quantity_label = QLabel(str(self.item["quantity"]))
        layout.addRow("Cantidad Actual:", self.current_quantity_label)

        # Adjustment input
        self.adjustment_input = QDoubleSpinBox()
        self.adjustment_input.setMinimum(-1000000)
        self.adjustment_input.setMaximum(1000000)
        self.adjustment_input.setDecimals(3)
        self.adjustment_input.setValue(0)
        layout.addRow("Ajustar Cantidad (+/-):", self.adjustment_input)

        # New Quantity Preview
        self.new_quantity_label = QLabel(str(self.item["quantity"]))
        layout.addRow("Nueva Cantidad:", self.new_quantity_label)
        self.adjustment_input.valueChanged.connect(self.update_new_quantity)

        # Reason for adjustment
        self.reason_input = QLineEdit()
        self.reason_input.setPlaceholderText("Motivo del ajuste (opcional)")
        layout.addRow("Motivo:", self.reason_input)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    def update_new_quantity(self):
        current = self.item["quantity"]
        adjustment = self.adjustment_input.value()
        self.new_quantity_label.setText(f"{current + adjustment:.3f}")

    def get_data(self):
        return {
            "adjustment": self.adjustment_input.value(),
            "reason": self.reason_input.text().strip(),
        }


class InventoryView(QWidget):
    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryService()
        self.product_service = ProductService()
        self.category_service = CategoryService()
        self.current_inventory = []
        self.setup_ui()
        self.setup_shortcuts()

    @handle_exceptions(UIException, show_dialog=True)
    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Top controls
        input_layout = QHBoxLayout()
        
        # Search & Barcode
        barcode_layout = QHBoxLayout()
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Escanear código...")
        self.barcode_input.returnPressed.connect(self.handle_barcode_scan)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar productos...")
        search_button = QPushButton("Buscar")
        search_button.clicked.connect(self.search_products)
        
        barcode_layout.addWidget(QLabel("Código:"))
        barcode_layout.addWidget(self.barcode_input)
        barcode_layout.addWidget(QLabel("Búsqueda Manual:"))
        barcode_layout.addWidget(self.search_input)
        barcode_layout.addWidget(search_button)
        
        input_layout.addLayout(barcode_layout)
        layout.addLayout(input_layout)

        # Filters
        filter_layout = QHBoxLayout()
        self.category_filter = QComboBox()
        self.category_filter.addItem("Todas las Categorías", None)
        self.load_categories()
        self.category_filter.currentIndexChanged.connect(self.load_inventory) # Reload when filter changes

        self.barcode_filter = QComboBox()
        self.barcode_filter.addItems(["Todos", "Con Código", "Sin Código"])
        self.barcode_filter.currentIndexChanged.connect(self.load_inventory)

        filter_layout.addWidget(QLabel("Categoría:"))
        filter_layout.addWidget(self.category_filter)
        filter_layout.addWidget(QLabel("Filtro Código:"))
        filter_layout.addWidget(self.barcode_filter)
        layout.addLayout(filter_layout)

        # Inventory Table
        self.inventory_table = create_table(
            ["ID", "Producto", "Categoría", "Código", "Cantidad", "Acciones"]
        )
        self.inventory_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.inventory_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inventory_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.inventory_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.inventory_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.inventory_table)

        # Load initial data
        self.load_inventory()

    def setup_shortcuts(self):
        # Refresh (F5)
        refresh_shortcut = QAction("Actualizar", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.refresh)
        self.addAction(refresh_shortcut)
        
        # Focus barcode (Ctrl+B)
        barcode_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        barcode_shortcut.activated.connect(self.barcode_input.setFocus)

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_categories(self):
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("Todas las Categorías", None)
        categories = self.category_service.get_all_categories()
        for category in categories:
            self.category_filter.addItem(category.name, category.id)
        self.category_filter.blockSignals(False)

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_inventory(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            category_id = self.category_filter.currentData()
            # If category is selected, we filter by it. Otherwise all.
            # Inventory service might need get_inventory_by_category or we filter locally.
            # Assuming get_inventory_status returns all and we filter.
            
            items = self.inventory_service.get_all_inventory()
            
            # Apply filters
            filtered_items = []
            barcode_filter_mode = self.barcode_filter.currentText()
            
            search_query = self.search_input.text().strip().lower()
            
            for item in items:
                # Category Filter
                if category_id is not None and item.get("category_id") != category_id:
                    continue
                    
                # Barcode Filter
                has_barcode = bool(item.get("barcode"))
                if barcode_filter_mode == "Con Código" and not has_barcode:
                    continue
                if barcode_filter_mode == "Sin Código" and has_barcode:
                    continue
                    
                # Search Filter
                if search_query:
                    if (search_query not in item["product_name"].lower() and 
                        search_query not in str(item.get("barcode", "")).lower()):
                        continue
                
                filtered_items.append(item)
            
            self.current_inventory = filtered_items
            self.update_table(filtered_items)
            
        finally:
            QApplication.restoreOverrideCursor()

    def update_table(self, items: List[Dict[str, Any]]):
        self.inventory_table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.inventory_table.setItem(row, 0, NumericTableWidgetItem(item["product_id"]))
            self.inventory_table.setItem(row, 1, QTableWidgetItem(item["product_name"]))
            self.inventory_table.setItem(row, 2, QTableWidgetItem(item.get("category_name", "Sin Categoría")))
            self.inventory_table.setItem(row, 3, QTableWidgetItem(item.get("barcode") or "Sin Código"))
            self.inventory_table.setItem(row, 4, NumericTableWidgetItem(item["quantity"]))
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_btn = QPushButton("Editar")
            edit_btn.clicked.connect(lambda _, i=item: self.edit_inventory(i))
            actions_layout.addWidget(edit_btn)
            
            self.inventory_table.setCellWidget(row, 5, actions_widget)

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def edit_inventory(self, item: Dict[str, Any]):
        dialog = EditInventoryDialog(item, self)
        if dialog.exec():
            data = dialog.get_data()
            if data["adjustment"] != 0:
                self.inventory_service.adjust_stock(
                    product_id=item["product_id"],
                    quantity_change=data["adjustment"],
                    reason=data["reason"] or "Manual adjustment"
                )
                self.load_inventory()
                show_info_message("Éxito", "Inventario actualizado correctamente")
                event_system.inventory_updated.emit()

    def handle_barcode_scan(self):
        barcode = self.barcode_input.text().strip()
        if not barcode:
            return
            
        found = False
        # Try to find in current list
        for item in self.current_inventory:
            if item.get("barcode") == barcode:
                self.edit_inventory(item)
                found = True
                break
        
        if not found:
            # Maybe it's not in current filtered list but exists?
            # Or assume we just search the table.
            from ui.styles import DesignTokens
            self.barcode_input.setStyleSheet(f"background-color: {DesignTokens.COLOR_ERROR_BG};")
            QTimer.singleShot(1000, lambda: self.barcode_input.setStyleSheet(""))
            show_error_message("Error", f"Producto con código {barcode} no encontrado en la vista actual")
            
        self.barcode_input.clear()

    def search_products(self):
        self.load_inventory()

    def refresh(self):
        self.inventory_service.clear_cache()
        self.load_inventory()

    def show_context_menu(self, position):
        menu = QMenu()
        edit_action = menu.addAction("Editar Cantidad")
        
        row = self.inventory_table.rowAt(position.y())
        action = menu.exec(self.inventory_table.mapToGlobal(position))
        
        if action == edit_action and row >= 0:
            product_id = int(self.inventory_table.item(row, 0).text())
            item = next((i for i in self.current_inventory if i["product_id"] == product_id), None)
            if item:
                self.edit_inventory(item)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F5:
            self.refresh()
        elif event.key() == Qt.Key.Key_Escape:
            self.barcode_input.clear()
            self.search_input.clear()
            self.barcode_input.setFocus()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
             if self.inventory_table.hasFocus():
                self.edit_selected_item()
             else:
                 super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def edit_selected_item(self):
        selected_rows = self.inventory_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            product_id = int(self.inventory_table.item(row, 0).text())
            item = next((i for i in self.current_inventory if i["product_id"] == product_id), None)
            if item:
                self.edit_inventory(item)


# Use for QApplication reference in static methods if needed or imports
from PySide6.QtWidgets import QApplication
