from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
                               QPushButton, QLineEdit, QMessageBox, QLabel, QComboBox, QInputDialog,
                               QDialog, QFormLayout, QDialogButtonBox)
from PySide6.QtCore import Qt
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.category_service import CategoryService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system
from typing import List, Dict, Any

class EditInventoryDialog(QDialog):
    def __init__(self, product: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(f"Edit {product['product_name']}")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.quantity_input = QLineEdit(str(self.product['quantity']))
        layout.addRow("Quantity:", self.quantity_input)

        self.adjustment_input = QLineEdit("0")
        layout.addRow("Adjust Quantity (+ or -):", self.adjustment_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_new_quantity(self) -> int:
        return int(self.quantity_input.text())

    def get_adjustment(self) -> int:
        return int(self.adjustment_input.text())

class InventoryView(QWidget):
    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryService()
        self.product_service = ProductService()
        self.category_service = CategoryService()
        self.setup_ui()
        event_system.product_added.connect(self.load_inventory)
        event_system.product_added.connect(self.on_product_added)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search inventory...")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_inventory)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Inventory table
        self.inventory_table = create_table(["Product ID", "Product Name", "Category", "Quantity", "Actions"])
        layout.addWidget(self.inventory_table)

        # Low stock alert button
        low_stock_button = QPushButton("Show Low Stock Items")
        low_stock_button.clicked.connect(self.show_low_stock_alert)
        layout.addWidget(low_stock_button)

        self.load_inventory()

    def on_product_added(self, product_id: int):
        self.inventory_service.update_quantity(product_id, 0)  # Add new product with quantity 0
        self.load_inventory()

    def load_inventory(self):
        try:
            inventory_items = self.inventory_service.get_all_inventory()
            self.update_inventory_table(inventory_items)
        except Exception as e:
            show_error_message("Error", f"Failed to load inventory: {str(e)}")

    def update_inventory_table(self, inventory_items: List[Dict[str, Any]]):
        self.inventory_table.setRowCount(len(inventory_items))
        for row, item in enumerate(inventory_items):
            self.inventory_table.setItem(row, 0, QTableWidgetItem(str(item['product_id'])))
            self.inventory_table.setItem(row, 1, QTableWidgetItem(item['product_name']))
            self.inventory_table.setItem(row, 2, QTableWidgetItem(item['category_name']))
            self.inventory_table.setItem(row, 3, QTableWidgetItem(str(item['quantity'])))
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(lambda _, i=item: self.edit_inventory(i))
            
            actions_layout.addWidget(edit_button)
            self.inventory_table.setCellWidget(row, 4, actions_widget)

    def edit_inventory(self, item: Dict[str, Any]):
        dialog = EditInventoryDialog(item, self)
        if dialog.exec():
            new_quantity = dialog.get_new_quantity()
            adjustment = dialog.get_adjustment()
            
            try:
                if adjustment != 0:
                    self.inventory_service.update_quantity(item['product_id'], adjustment)
                else:
                    self.inventory_service.set_quantity(item['product_id'], new_quantity)
                self.load_inventory()
                QMessageBox.information(self, "Success", "Inventory updated successfully.")
            except Exception as e:
                show_error_message("Error", f"Failed to update inventory: {str(e)}")

    def show_low_stock_alert(self, threshold: int = 10):
        try:
            low_stock_items = self.inventory_service.get_low_stock_products(threshold)
            if low_stock_items:
                message = "The following items are low in stock:\n\n"
                for item in low_stock_items:
                    message += f"{item['product_name']} ({item['category_name']}): {item['quantity']} left\n"
                QMessageBox.warning(self, "Low Stock Alert", message)
            else:
                QMessageBox.information(self, "Stock Status", "No items are low in stock.")
        except Exception as e:
            show_error_message("Error", f"Failed to check low stock items: {str(e)}")

    def search_inventory(self):
        search_term = self.search_input.text().strip().lower()
        if search_term:
            filtered_items = [
                item for item in self.inventory_service.get_all_inventory()
                if search_term in item['product_name'].lower() or 
                search_term in str(item['product_id']) or
                search_term in item['category_name'].lower()
            ]
            self.update_inventory_table(filtered_items)
        else:
            self.load_inventory()