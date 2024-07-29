from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
                               QPushButton, QLineEdit, QMessageBox, QLabel, QComboBox, QInputDialog)
from PySide6.QtCore import Qt
from services.inventory_service import InventoryService
from services.product_service import ProductService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system
from typing import List, Dict, Any

class InventoryView(QWidget):
    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryService()
        self.product_service = ProductService()
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
        self.inventory_table = create_table(["Product ID", "Product Name", "Quantity", "Actions"])
        layout.addWidget(self.inventory_table)

        # Add/Edit inventory
        edit_layout = QHBoxLayout()
        self.product_combo = QComboBox()
        self.quantity_input = QLineEdit()
        edit_layout.addWidget(QLabel("Product:"))
        edit_layout.addWidget(self.product_combo)
        edit_layout.addWidget(QLabel("Quantity:"))
        edit_layout.addWidget(self.quantity_input)
        update_button = QPushButton("Update Quantity")
        update_button.clicked.connect(self.update_quantity)
        edit_layout.addWidget(update_button)
        layout.addLayout(edit_layout)

        # Low stock alert button
        low_stock_button = QPushButton("Show Low Stock Items")
        low_stock_button.clicked.connect(self.show_low_stock_alert)
        layout.addWidget(low_stock_button)

        self.load_products()
        self.load_inventory()

    def on_product_added(self, product_id: int):
            self.inventory_service.update_quantity(product_id, 0)  # Add new product with quantity 0
            self.load_inventory()
            self.load_products()

    def load_products(self):
        try:
            products = self.product_service.get_all_products()
            self.product_combo.clear()
            for product in products:
                self.product_combo.addItem(product.name, product.id)
        except Exception as e:
            show_error_message("Error", f"Failed to load products: {str(e)}")

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
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_button = QPushButton("Edit")
            edit_button.setFixedWidth(50)
            edit_button.clicked.connect(lambda _, i=item: self.edit_inventory(i))
            
            actions_layout.addWidget(edit_button)
            self.inventory_table.setCellWidget(row, 3, actions_widget)

    def update_quantity(self):
        product_id = self.product_combo.currentData()
        quantity = self.quantity_input.text()
        
        try:
            quantity = int(quantity)
            if quantity < 0:
                raise ValueError("Quantity must be a non-negative integer")
        except ValueError as e:
            show_error_message("Invalid Input", str(e))
            return

        try:
            self.inventory_service.update_quantity(product_id, quantity)
            self.load_inventory()
            QMessageBox.information(self, "Success", "Inventory updated successfully.")
        except Exception as e:
            show_error_message("Error", str(e))

        self.quantity_input.clear()

    def show_low_stock_alert(self, threshold: int = 10):
        try:
            low_stock_items = self.inventory_service.get_low_stock_products(threshold)
            if low_stock_items:
                message = "The following items are low in stock:\n\n"
                for item in low_stock_items:
                    message += f"{item['product_name']}: {item['quantity']} left\n"
                QMessageBox.warning(self, "Low Stock Alert", message)
            else:
                QMessageBox.information(self, "Stock Status", "No items are low in stock.")
        except Exception as e:
            show_error_message("Error", f"Failed to check low stock items: {str(e)}")

    def edit_inventory(self, item: Dict[str, Any]):
        product_id = item['product_id']
        current_quantity = item['quantity']
        new_quantity, ok = QInputDialog.getInt(self, "Edit Inventory", 
                                            f"Enter new quantity for {item['product_name']}:",
                                            value=current_quantity)
        if ok:
            if new_quantity < 0:
                show_error_message("Invalid Input", "Quantity must be a non-negative integer")
                return
            try:
                self.inventory_service.set_quantity(product_id, new_quantity)
                self.load_inventory()
                QMessageBox.information(self, "Success", "Inventory updated successfully.")
            except Exception as e:
                show_error_message("Error", f"Failed to update inventory: {str(e)}")

    def search_inventory(self):
        search_term = self.search_input.text().strip().lower()
        if search_term:
            filtered_items = [
                item for item in self.inventory_service.get_all_inventory()
                if search_term in item['product_name'].lower() or search_term in str(item['product_id'])
            ]
            self.update_inventory_table(filtered_items)
        else:
            self.load_inventory()