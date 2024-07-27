from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox)
from PySide6.QtCore import Qt
from services.product_service import ProductService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system

class ProductView(QWidget):
    def __init__(self):
        super().__init__()
        self.product_service = ProductService()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Input fields
        input_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.description_input = QLineEdit()
        input_layout.addWidget(QLabel("Name:"))
        input_layout.addWidget(self.name_input)
        input_layout.addWidget(QLabel("Description:"))
        input_layout.addWidget(self.description_input)
        
        add_button = QPushButton("Add Product")
        add_button.clicked.connect(self.add_product)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Product table
        self.product_table = create_table(["ID", "Name", "Description", "Avg. Purchase Price"])
        layout.addWidget(self.product_table)

        self.load_products()

    def load_products(self):
        products = self.product_service.get_all_products()
        self.product_table.setRowCount(len(products))
        for row, product in enumerate(products):
            avg_price = self.product_service.get_average_purchase_price(product.id)
            self.product_table.setItem(row, 0, QTableWidgetItem(str(product.id)))
            self.product_table.setItem(row, 1, QTableWidgetItem(product.name))
            self.product_table.setItem(row, 2, QTableWidgetItem(product.description))
            self.product_table.setItem(row, 3, QTableWidgetItem(f"{avg_price:.2f}"))

    def add_product(self):
        name = self.name_input.text().strip()
        description = self.description_input.text().strip()

        if not name:
            show_error_message("Error", "Product name is required.")
            return

        try:
            self.product_service.create_product(name, description)
            self.load_products()
            self.name_input.clear()
            self.description_input.clear()
            QMessageBox.information(self, "Success", "Product added successfully.")
            event_system.product_added.emit()  # Emit the event
        except Exception as e:
            show_error_message("Error", str(e))