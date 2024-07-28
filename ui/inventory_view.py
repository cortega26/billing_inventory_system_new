from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QLineEdit, QMessageBox, QLabel
from services.inventory_service import InventoryService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system
from typing import List, Dict, Any

class InventoryView(QWidget):
    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryService()
        self.setup_ui()
        event_system.product_added.connect(self.load_inventory)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Inventory table
        self.inventory_table = create_table(["Product ID", "Product Name", "Quantity"])
        layout.addWidget(self.inventory_table)

        # Add/Edit inventory
        edit_layout = QHBoxLayout()
        self.product_id_input = QLineEdit()
        self.quantity_input = QLineEdit()
        edit_layout.addWidget(QLabel("Product ID:"))
        edit_layout.addWidget(self.product_id_input)
        edit_layout.addWidget(QLabel("Quantity:"))
        edit_layout.addWidget(self.quantity_input)
        update_button = QPushButton("Update Quantity")
        update_button.clicked.connect(self.update_quantity)
        edit_layout.addWidget(update_button)
        layout.addLayout(edit_layout)

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
            self.inventory_table.setItem(row, 2, QTableWidgetItem(str(item['quantity'])))

    def update_quantity(self):
        product_id = self.product_id_input.text()
        quantity = self.quantity_input.text()
        
        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except ValueError:
            show_error_message("Invalid Input", "Product ID and Quantity must be integers.")
            return

        try:
            self.inventory_service.update_quantity(product_id, quantity)
            self.load_inventory()
            QMessageBox.information(self, "Success", "Inventory updated successfully.")
        except Exception as e:
            show_error_message("Error", str(e))

        self.product_id_input.clear()
        self.quantity_input.clear()

    def show_low_stock_alert(self, threshold: int = 10):
        try:
            low_stock_items = [item for item in self.inventory_service.get_all_inventory() if item['quantity'] <= threshold]
            if low_stock_items:
                message = "The following items are low in stock:\n\n"
                for item in low_stock_items:
                    message += f"{item['product_name']}: {item['quantity']} left\n"
                QMessageBox.warning(self, "Low Stock Alert", message)
        except Exception as e:
            show_error_message("Error", f"Failed to check low stock items: {str(e)}")