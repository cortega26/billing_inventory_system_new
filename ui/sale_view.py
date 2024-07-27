from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QComboBox, QDateEdit)
from PySide6.QtCore import Qt, QDate
from services.sale_service import SaleService
from services.customer_service import CustomerService
from services.product_service import ProductService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system

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
        self.customer_combo = QComboBox()
        self.product_combo = QComboBox()
        self.quantity_input = QLineEdit()
        self.price_input = QLineEdit()
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        
        input_layout.addWidget(QLabel("Customer:"))
        input_layout.addWidget(self.customer_combo)
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
        self.sale_table = create_table(["ID", "Customer", "Date", "Total Amount"])
        layout.addWidget(self.sale_table)

        self.load_customers()
        self.load_products()
        self.load_sales()

    def load_customers(self):
        customers = self.customer_service.get_all_customers()
        self.customer_combo.clear()
        for customer in customers:
            self.customer_combo.addItem(f"{customer.identifier_9} ({customer.identifier_4 or 'N/A'})", customer.id)

    def load_products(self):
        products = self.product_service.get_all_products()
        self.product_combo.clear()
        for product in products:
            self.product_combo.addItem(product.name, product.id)

    def load_sales(self):
        sales = self.sale_service.get_all_sales()
        self.sale_table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            customer = self.customer_service.get_customer(sale.customer_id)
            self.sale_table.setItem(row, 0, QTableWidgetItem(str(sale.id)))
            self.sale_table.setItem(row, 1, QTableWidgetItem(f"{getattr(customer, 'identifier_9', 'N/A')} ({getattr(customer, 'identifier_4', 'N/A')})"))
            self.sale_table.setItem(row, 2, QTableWidgetItem(sale.date))
            self.sale_table.setItem(row, 3, QTableWidgetItem(f"{sale.total_amount:.2f}"))

    def add_sale(self):
        customer_id = self.customer_combo.currentData()
        product_id = self.product_combo.currentData()
        quantity = self.quantity_input.text().strip()
        price = self.price_input.text().strip()
        date = self.date_input.date().toString("yyyy-MM-dd")

        if not all([customer_id, product_id, quantity, price]):
            show_error_message("Error", "All fields are required.")
            return

        try:
            quantity = int(quantity)
            price = float(price)
            
            sale_data = {
                "customer_id": customer_id,
                "date": date,
                "items": [{"product_id": product_id, "quantity": quantity, "price": price}]
            }
            
            self.sale_service.create_sale(customer_id, date, sale_data["items"])
            self.load_sales()
            self.quantity_input.clear()
            self.price_input.clear()
            QMessageBox.information(self, "Success", "Sale added successfully.")
        except ValueError:
            show_error_message("Error", "Invalid quantity or price.")
        except Exception as e:
            show_error_message("Error", str(e))