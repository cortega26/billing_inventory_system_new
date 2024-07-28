from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QComboBox, QDateEdit, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, QDate
from services.sale_service import SaleService
from services.customer_service import CustomerService
from services.product_service import ProductService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system
from utils.logger import logger
from typing import List, Dict, Any, Optional
from models.customer import Customer

class CustomerSelectionDialog(QDialog):
    def __init__(self, customers: List[Customer], parent=None):
        super().__init__(parent)
        self.customers = customers
        self.setWindowTitle("Select Customer")
        layout = QVBoxLayout(self)
        
        self.customer_combo = QComboBox()
        for customer in customers:
            identifiers_3or4 = ', '.join([i.identifier_3or4 for i in customer.identifiers_3or4]) or 'N/A'
            self.customer_combo.addItem(f"{customer.identifier_9} ({identifiers_3or4})", customer.id)
        
        layout.addWidget(QLabel("Select a customer:"))
        layout.addWidget(self.customer_combo)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_selected_customer(self) -> int:
        return self.customer_combo.currentData()

class SaleView(QWidget):
    def __init__(self):
        super().__init__()
        self.sale_service = SaleService()
        self.customer_service = CustomerService()
        self.product_service = ProductService()
        self.setup_ui()
        event_system.product_added.connect(self.load_products)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Input fields
        input_layout = QHBoxLayout()
        self.customer_id_input = QLineEdit()
        self.customer_id_input.setPlaceholderText("Enter 4-digit or 9-digit identifier")
        self.customer_select_button = QPushButton("Select Customer")
        self.customer_select_button.clicked.connect(self.select_customer)
        self.product_combo = QComboBox()
        self.quantity_input = QLineEdit()
        self.price_input = QLineEdit()
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        input_layout.addWidget(QLabel("Customer:"))
        input_layout.addWidget(self.customer_id_input)
        input_layout.addWidget(self.customer_select_button)
        input_layout.addWidget(QLabel("Product:"))
        input_layout.addWidget(self.product_combo)
        input_layout.addWidget(QLabel("Quantity:"))
        input_layout.addWidget(self.quantity_input)
        input_layout.addWidget(QLabel("Price:"))
        input_layout.addWidget(self.price_input)
        input_layout.addWidget(QLabel("Date:"))
        input_layout.addWidget(self.date_input)
        
        add_button = QPushButton("Add Sale")
        add_button.clicked.connect(self.add_sale)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Sale table
        self.sale_table = create_table(["ID", "Customer", "Product", "Quantity", "Price", "Date", "Total Amount"])
        self.sale_table.setSortingEnabled(True)  # Enable sorting
        layout.addWidget(self.sale_table)

        self.load_products()
        self.load_sales()

    def load_products(self):
        logger.debug("Loading products")
        try:
            products = self.product_service.get_all_products()
            self.product_combo.clear()
            for product in products:
                self.product_combo.addItem(product.name, product.id)
            logger.debug(f"Loaded {len(products)} products")
        except Exception as e:
            logger.error(f"Failed to load products: {str(e)}")
            show_error_message("Error", f"Failed to load products: {str(e)}")

    def load_sales(self):
        logger.debug("Loading sales")
        try:
            sales = self.sale_service.get_all_sales()
            self.sale_table.setRowCount(len(sales))
            for row, sale in enumerate(sales):
                customer = self.customer_service.get_customer(sale.customer_id)
                sale_items = self.sale_service.get_sale_items(sale.id)
                
                if sale_items:
                    sale_item = sale_items[0]  # Assuming we're displaying the first item for simplicity
                    product = self.product_service.get_product(sale_item.product_id)
                    
                    self.sale_table.setItem(row, 0, QTableWidgetItem(str(sale.id)))
                    
                    customer_text = f"{customer.identifier_9} ({', '.join([i.identifier_3or4 for i in customer.identifiers_3or4]) or 'N/A'})" if customer else "Unknown Customer"
                    self.sale_table.setItem(row, 1, QTableWidgetItem(customer_text))
                    
                    product_name = product.name if product else "Unknown Product"
                    self.sale_table.setItem(row, 2, QTableWidgetItem(product_name))
                    
                    self.sale_table.setItem(row, 3, QTableWidgetItem(str(sale_item.quantity)))
                    self.sale_table.setItem(row, 4, QTableWidgetItem(f"{sale_item.price:,}"))
                    self.sale_table.setItem(row, 5, QTableWidgetItem(sale.date))
                    self.sale_table.setItem(row, 6, QTableWidgetItem(f"{sale.total_amount:,}"))
            logger.debug(f"Loaded {len(sales)} sales")
        except Exception as e:
            logger.error(f"Failed to load sales: {str(e)}")
            show_error_message("Error", f"Failed to load sales: {str(e)}")

    def select_customer(self):
        identifier = self.customer_id_input.text().strip()
        logger.debug(f"Selecting customer with identifier: {identifier}")
        if len(identifier) == 3 or len(identifier) == 4:
            customers = self.customer_service.get_customers_by_identifier_3or4(identifier)
        elif len(identifier) == 9:
            customer = self.customer_service.get_customer_by_identifier_9(identifier)
            customers = [customer] if customer else []
        else:
            logger.error("Invalid identifier length")
            show_error_message("Error", "Please enter a valid 4-digit or 9-digit identifier.")
            return

        if not customers:
            logger.warning("No customers found with the given identifier")
            show_error_message("Error", "No customers found with the given identifier.")
            return

        if len(customers) == 1:
            self.selected_customer_id = customers[0].id
            identifiers_3or4 = ', '.join([i.identifier_3or4 for i in customers[0].identifiers_3or4]) or 'N/A'
            self.customer_id_input.setText(f"{customers[0].identifier_9} ({identifiers_3or4})")
        else:
            dialog = CustomerSelectionDialog(customers, self)
            if dialog.exec():
                self.selected_customer_id = dialog.get_selected_customer()
                selected_customer = next(c for c in customers if c.id == self.selected_customer_id)
                identifiers_3or4 = ', '.join([i.identifier_3or4 for i in selected_customer.identifiers_3or4]) or 'N/A'
                self.customer_id_input.setText(f"{selected_customer.identifier_9} ({identifiers_3or4})")
        logger.debug(f"Selected customer ID: {self.selected_customer_id}")

    def add_sale(self):
        if not hasattr(self, 'selected_customer_id'):
            logger.error("No customer selected")
            show_error_message("Error", "Please select a customer first.")
            return

        product_id = self.product_combo.currentData()
        quantity = self.quantity_input.text().strip()
        price = self.price_input.text().strip()
        date = self.date_input.date().toString("yyyy-MM-dd")

        if not all([product_id, quantity, price]):
            logger.error("Missing required fields")
            show_error_message("Error", "All fields are required.")
            return

        try:
            quantity = int(quantity)
            price = int(price)
            
            sale_data = {
                "customer_id": self.selected_customer_id,
                "date": date,
                "items": [{"product_id": product_id, "quantity": quantity, "price": price}]
            }
            
            sale_id = self.sale_service.create_sale(self.selected_customer_id, date, sale_data["items"])
            if sale_id is not None:
                logger.info(f"Sale added successfully with ID: {sale_id}")
                self.load_sales()
                self.customer_id_input.clear()
                self.quantity_input.clear()
                self.price_input.clear()
                del self.selected_customer_id
                QMessageBox.information(self, "Success", "Sale added successfully.")
            else:
                logger.error("Failed to add sale")
                show_error_message("Error", "Failed to add sale.")
        except ValueError:
            logger.error("Invalid quantity or price")
            show_error_message("Error", "Invalid quantity or price. Please enter valid integers.")
        except Exception as e:
            logger.error(f"Error adding sale: {str(e)}")
            show_error_message("Error", str(e))