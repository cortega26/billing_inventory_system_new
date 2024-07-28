from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QComboBox, QDateEdit)
from PySide6.QtCore import Qt, QDate
from services.purchase_service import PurchaseService
from services.product_service import ProductService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system
from typing import List, Dict, Any

class PurchaseView(QWidget):
    def __init__(self):
        super().__init__()
        self.purchase_service = PurchaseService()
        self.product_service = ProductService()
        self.setup_ui()
        event_system.product_added.connect(self.load_products)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Input fields
        input_layout = QHBoxLayout()
        self.supplier_combo = QComboBox()
        self.supplier_combo.setEditable(True)
        self.product_combo = QComboBox()
        self.quantity_input = QLineEdit()
        self.price_input = QLineEdit()
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        
        input_layout.addWidget(QLabel("Supplier:"))
        input_layout.addWidget(self.supplier_combo)
        input_layout.addWidget(QLabel("Product:"))
        input_layout.addWidget(self.product_combo)
        input_layout.addWidget(QLabel("Quantity:"))
        input_layout.addWidget(self.quantity_input)
        input_layout.addWidget(QLabel("Price:"))
        input_layout.addWidget(self.price_input)
        input_layout.addWidget(QLabel("Date:"))
        input_layout.addWidget(self.date_input)
        
        add_button = QPushButton("Add Purchase")
        add_button.clicked.connect(self.add_purchase)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Purchase table
        self.purchase_table = create_table(["ID", "Supplier", "Date", "Total Amount"])
        layout.addWidget(self.purchase_table)

        self.load_suppliers()
        self.load_products()
        self.load_purchases()

    def load_suppliers(self):
        try:
            suppliers = self.purchase_service.get_suppliers()
            self.supplier_combo.clear()
            self.supplier_combo.addItems(suppliers)
        except Exception as e:
            show_error_message("Error", f"Failed to load suppliers: {str(e)}")

    def load_products(self):
        try:
            products = self.product_service.get_all_products()
            self.product_combo.clear()
            for product in products:
                self.product_combo.addItem(product.name, product.id)
        except Exception as e:
            show_error_message("Error", f"Failed to load products: {str(e)}")

    def load_purchases(self):
        try:
            purchases = self.purchase_service.get_all_purchases()
            self.purchase_table.setRowCount(len(purchases))
            for row, purchase in enumerate(purchases):
                self.purchase_table.setItem(row, 0, QTableWidgetItem(str(purchase.id)))
                self.purchase_table.setItem(row, 1, QTableWidgetItem(purchase.supplier))
                self.purchase_table.setItem(row, 2, QTableWidgetItem(purchase.date))
                self.purchase_table.setItem(row, 3, QTableWidgetItem(f"{purchase.total_amount:,}"))
        except Exception as e:
            show_error_message("Error", f"Failed to load purchases: {str(e)}")

    def add_purchase(self):
        supplier = self.supplier_combo.currentText().strip()
        product_id = self.product_combo.currentData()
        quantity = self.quantity_input.text().strip()
        price = self.price_input.text().strip()
        date = self.date_input.date().toString("yyyy-MM-dd")

        if not all([supplier, product_id, quantity, price]):
            show_error_message("Error", "All fields are required.")
            return

        try:
            quantity = int(quantity)
            price = int(price)
            
            purchase_data = {
                "supplier": supplier,
                "date": date,
                "items": [{"product_id": product_id, "quantity": quantity, "price": price}]
            }
            
            purchase_id = self.purchase_service.create_purchase(supplier, date, purchase_data["items"])
            if purchase_id is not None:
                self.load_purchases()
                self.load_suppliers()
                self.quantity_input.clear()
                self.price_input.clear()
                QMessageBox.information(self, "Success", "Purchase added successfully.")
            else:
                show_error_message("Error", "Failed to add purchase.")
        except ValueError:
            show_error_message("Error", "Invalid quantity or price. Please enter valid integers.")
        except Exception as e:
            show_error_message("Error", str(e))