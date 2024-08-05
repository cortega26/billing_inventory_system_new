from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QInputDialog,
                               QPushButton, QTableWidgetItem, QDoubleSpinBox, QComboBox, QDialog,
                               QFormLayout, QDialogButtonBox, QHeaderView)
from PySide6.QtCore import Qt
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.category_service import CategoryService
from utils.utils import create_table, show_error_message, show_info_message, format_price
from utils.event_system import event_system
from utils.table_items import NumericTableWidgetItem, PriceTableWidgetItem
from typing import List, Dict, Any, Optional
from utils.logger import logger

class EditInventoryDialog(QDialog):
    def __init__(self, product: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(f"Edit {product['product_name']}")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setMinimum(0)
        self.quantity_input.setMaximum(1000000)
        self.quantity_input.setDecimals(2)
        self.quantity_input.setValue(self.product['quantity'])
        layout.addRow("Quantity:", self.quantity_input)

        self.adjustment_input = QDoubleSpinBox()
        self.adjustment_input.setMinimum(-1000000)
        self.adjustment_input.setMaximum(1000000)
        self.adjustment_input.setDecimals(2)
        self.adjustment_input.setValue(0)
        layout.addRow("Adjust Quantity (+ or -):", self.adjustment_input)

        self.reason_input = QLineEdit()
        layout.addRow("Reason for Adjustment:", self.reason_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def validate_and_accept(self):
        if self.adjustment_input.value() != 0 and not self.reason_input.text().strip():
            show_error_message("Error", "Please provide a reason for the adjustment.")
            return
        self.accept()

    def get_new_quantity(self) -> float:
        return self.quantity_input.value()

    def get_adjustment(self) -> float:
        return self.adjustment_input.value()

    def get_reason(self) -> str:
        return self.reason_input.text().strip()

class InventoryView(QWidget):
    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryService()
        self.product_service = ProductService()
        self.category_service = CategoryService()
        self.current_inventory = []  # Add this line
        self.setup_ui()
        event_system.product_added.connect(self.on_product_added)
        event_system.product_updated.connect(self.load_inventory)
        event_system.product_deleted.connect(self.load_inventory)
        event_system.sale_added.connect(self.load_inventory)
        event_system.purchase_added.connect(self.load_inventory)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search and filter
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search inventory...")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_inventory)
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", None)
        self.load_categories()
        self.category_filter.currentIndexChanged.connect(self.filter_inventory)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        search_layout.addWidget(QLabel("Category:"))
        search_layout.addWidget(self.category_filter)
        layout.addLayout(search_layout)

        # Inventory table
        self.inventory_table = create_table(["ID", "Product Name", "Category", "Quantity", "Actions"])
        layout.addWidget(self.inventory_table)

        # Low stock alert button
        low_stock_button = QPushButton("Show Low Stock Items")
        low_stock_button.clicked.connect(self.show_low_stock_alert)
        layout.addWidget(low_stock_button)

        self.load_inventory()

    def load_categories(self):
        try:
            categories = self.category_service.get_all_categories()
            for category in categories:
                self.category_filter.addItem(category.name, category.id)
        except Exception as e:
            logger.error(f"Failed to load categories: {str(e)}")
            show_error_message("Error", f"Failed to load categories: {str(e)}")

    def on_product_added(self, product_id: int):
        try:
            self.inventory_service.update_quantity(product_id, 0)  # Add new product with quantity 0
            self.load_inventory()
        except Exception as e:
            logger.error(f"Error adding new product to inventory: {str(e)}")
            show_error_message("Error", f"Failed to add new product to inventory: {str(e)}")

    def load_inventory(self):
        try:
            inventory_items = self.inventory_service.get_all_inventory()
            self.current_inventory = inventory_items  # Store the current inventory
            self.update_inventory_table(inventory_items)
        except Exception as e:
            logger.error(f"Failed to load inventory: {str(e)}")
            show_error_message("Error", f"Failed to load inventory: {str(e)}")

    def update_inventory_table(self, inventory_items: List[Dict[str, Any]]):
        current_sort_column = self.inventory_table.horizontalHeader().sortIndicatorSection()
        current_sort_order = self.inventory_table.horizontalHeader().sortIndicatorOrder()
        
        self.inventory_table.setSortingEnabled(False)  # Disable sorting temporarily
        self.inventory_table.setRowCount(len(inventory_items))
        for row, item in enumerate(inventory_items):
            self.inventory_table.setItem(row, 0, NumericTableWidgetItem(item['product_id']))
            self.inventory_table.setItem(row, 1, QTableWidgetItem(item['product_name']))
            self.inventory_table.setItem(row, 2, QTableWidgetItem(item['category_name']))
            self.inventory_table.setItem(row, 3, PriceTableWidgetItem(item['quantity'], format_price))
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(lambda _, i=item: self.edit_inventory(i))
            
            actions_layout.addWidget(edit_button)
            self.inventory_table.setCellWidget(row, 4, actions_widget)

        self.inventory_table.setSortingEnabled(True)  # Re-enable sorting
        self.inventory_table.sortItems(current_sort_column, current_sort_order)  # Restore the previous sort

    def edit_inventory(self, item: Dict[str, Any]):
        dialog = EditInventoryDialog(item, self)
        if dialog.exec():
            new_quantity = dialog.get_new_quantity()
            adjustment = dialog.get_adjustment()
            reason = dialog.get_reason()
            
            try:
                if adjustment != 0:
                    self.inventory_service.adjust_inventory(item['product_id'], int(adjustment), reason)
                    new_quantity = item['quantity'] + adjustment
                else:
                    self.inventory_service.set_quantity(item['product_id'], int(new_quantity))
                
                # Update the specific item in the current_inventory
                for i, inv_item in enumerate(self.current_inventory):
                    if inv_item['product_id'] == item['product_id']:
                        self.current_inventory[i]['quantity'] = new_quantity
                        break
                
                # Update the specific row in the table
                self.update_inventory_table(self.current_inventory)
                
                show_info_message("Success", "Inventory updated successfully.")
            except Exception as e:
                logger.error(f"Failed to update inventory: {str(e)}")
                show_error_message("Error", f"Failed to update inventory: {str(e)}")

    def show_low_stock_alert(self):
        threshold, ok = QInputDialog.getInt(self, "Low Stock Threshold", "Enter the low stock threshold:", 10, 1, 1000)
        if ok:
            try:
                low_stock_items = self.inventory_service.get_low_stock_products(threshold)
                if low_stock_items:
                    message = "The following items are low in stock:\n\n"
                    for item in low_stock_items:
                        message += f"{item['product_name']} ({item['category_name']}): {format_price(item['quantity'])} left\n"
                    show_info_message("Low Stock Alert", message)
                else:
                    show_info_message("Stock Status", "No items are low in stock.")
            except Exception as e:
                logger.error(f"Failed to check low stock items: {str(e)}")
                show_error_message("Error", f"Failed to check low stock items: {str(e)}")

    def search_inventory(self):
        search_term = self.search_input.text().strip().lower()
        category_id = self.category_filter.currentData()
        self.filter_inventory(search_term, category_id)

    def filter_inventory(self, search_term: str = "", category_id: Optional[int] = None):
        try:
            all_items = self.inventory_service.get_all_inventory()
            filtered_items = [
                item for item in all_items
                if (search_term in item['product_name'].lower() or 
                    search_term in str(item['product_id']) or
                    search_term in item['category_name'].lower()) and
                   (category_id is None or item['category_id'] == category_id)
            ]
            self.update_inventory_table(filtered_items)
        except Exception as e:
            logger.error(f"Error filtering inventory: {str(e)}")
            show_error_message("Error", f"Failed to filter inventory: {str(e)}")
