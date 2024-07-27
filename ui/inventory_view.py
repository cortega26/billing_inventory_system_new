from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QLineEdit, QMessageBox
from services.inventory_service import InventoryService
from utils.utils import create_table
from utils.event_system import event_system

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
        edit_layout.addWidget(self.product_id_input)
        edit_layout.addWidget(self.quantity_input)
        update_button = QPushButton("Update Quantity")
        update_button.clicked.connect(self.update_quantity)
        edit_layout.addWidget(update_button)
        layout.addLayout(edit_layout)

        self.load_inventory()

    def load_inventory(self):
        inventory_items = self.inventory_service.get_all_inventory()
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
            QMessageBox.warning(self, "Invalid Input", "Product ID and Quantity must be integers.")
            return

        try:
            self.inventory_service.update_quantity(product_id, quantity)
            self.load_inventory()
            QMessageBox.information(self, "Success", "Inventory updated successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

        self.product_id_input.clear()
        self.quantity_input.clear()