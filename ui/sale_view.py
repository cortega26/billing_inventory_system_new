from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QComboBox, QDateEdit, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, QDate
from services.sale_service import SaleService
from services.customer_service import CustomerService
from services.product_service import ProductService
from models.customer import Customer
from models.sale import Sale
from utils.utils import create_table, show_error_message
from utils.logger import logger
from typing import List, Optional

class CustomerSelectionDialog(QDialog):
    def __init__(self, customers: List[Customer], parent=None):
        super().__init__(parent)
        self.customers = customers
        self.setWindowTitle("Select Customer")
        layout = QVBoxLayout(self)
        
        self.customer_combo = QComboBox()
        for customer in customers:
            self.customer_combo.addItem(f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})", customer.id)
        
        layout.addWidget(QLabel("Select a customer:"))
        layout.addWidget(self.customer_combo)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_selected_customer(self) -> int:
        return self.customer_combo.currentData()

class SaleItemDialog(QDialog):
    def __init__(self, products, parent=None):
        super().__init__(parent)
        self.products = products
        self.setWindowTitle("Add Sale Item")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.product_combo = QComboBox()
        for product in self.products:
            self.product_combo.addItem(product.name, product.id)
        layout.addWidget(QLabel("Product:"))
        layout.addWidget(self.product_combo)
        
        self.quantity_input = QLineEdit()
        layout.addWidget(QLabel("Quantity:"))
        layout.addWidget(self.quantity_input)
        
        self.price_input = QLineEdit()
        layout.addWidget(QLabel("Price:"))
        layout.addWidget(self.price_input)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_item_data(self):
        return {
            "product_id": self.product_combo.currentData(),
            "quantity": int(self.quantity_input.text()),
            "price": float(self.price_input.text())
        }

class SaleView(QWidget):
    def __init__(self):
        super().__init__()
        self.sale_service = SaleService()
        self.customer_service = CustomerService()
        self.product_service = ProductService()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search sales...")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_sales)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Input fields
        input_layout = QHBoxLayout()
        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Enter 4-digit or 9-digit identifier")
        self.customer_select_button = QPushButton("Select Customer")
        self.customer_select_button.clicked.connect(self.select_customer)
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setFixedWidth(150)  # Adjust this value to make it larger
        
        input_layout.addWidget(QLabel("Customer:"))
        input_layout.addWidget(self.customer_input)
        input_layout.addWidget(self.customer_select_button)
        input_layout.addWidget(QLabel("Date:"))
        input_layout.addWidget(self.date_input)
        input_layout.addStretch(1)  # This will push the add button to the right
        
        add_button = QPushButton("Add Sale")
        add_button.clicked.connect(self.add_sale)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Sale table
        self.sale_table = create_table(["ID", "Customer", "Date", "Total Amount", "Actions"])
        layout.addWidget(self.sale_table)

        self.load_sales()

    def load_sales(self):
        logger.debug("Loading sales")
        try:
            sales = self.sale_service.get_all_sales()
            self.update_sale_table(sales)
        except Exception as e:
            logger.error(f"Failed to load sales: {str(e)}")
            show_error_message("Error", f"Failed to load sales: {str(e)}")

    def update_sale_table(self, sales: List[Sale]):
        self.sale_table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            customer = self.customer_service.get_customer(sale.customer_id)
            
            self.sale_table.setItem(row, 0, QTableWidgetItem(str(sale.id)))
            
            customer_text = f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})" if customer else "Unknown Customer"
            self.sale_table.setItem(row, 1, QTableWidgetItem(customer_text))
            
            self.sale_table.setItem(row, 2, QTableWidgetItem(sale.date.strftime("%Y-%m-%d")))
            self.sale_table.setItem(row, 3, QTableWidgetItem(f"{sale.total_amount:,.2f}"))
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            view_button = QPushButton("View")
            view_button.clicked.connect(lambda _, s=sale: self.view_sale(s))
            actions_layout.addWidget(view_button)
            
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, s=sale: self.delete_sale(s))
            actions_layout.addWidget(delete_button)
            
            self.sale_table.setCellWidget(row, 4, actions_widget)

    def select_customer(self):
        identifier = self.customer_input.text().strip()
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
            self.customer_input.setText(f"{customers[0].identifier_9} ({customers[0].identifier_3or4 or 'N/A'})")
        else:
            dialog = CustomerSelectionDialog(customers, self)
            if dialog.exec():
                self.selected_customer_id = dialog.get_selected_customer()
                selected_customer = next(c for c in customers if c.id == self.selected_customer_id)
                self.customer_input.setText(f"{selected_customer.identifier_9} ({selected_customer.identifier_3or4 or 'N/A'})")
        logger.debug(f"Selected customer ID: {self.selected_customer_id}")

    def add_sale(self):
        if not hasattr(self, 'selected_customer_id'):
            logger.error("No customer selected")
            show_error_message("Error", "Please select a customer first.")
            return

        date = self.date_input.date().toString("yyyy-MM-dd")

        try:
            products = self.product_service.get_all_products()
            items = []
            while True:
                dialog = SaleItemDialog(products, self)
                if dialog.exec():
                    items.append(dialog.get_item_data())
                    reply = QMessageBox.question(self, "Add Another Item", "Do you want to add another item?",
                                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        break
                else:
                    break

            if items:
                sale_id = self.sale_service.create_sale(self.selected_customer_id, date, items)
                if sale_id is not None:
                    logger.info(f"Sale added successfully with ID: {sale_id}")
                    self.load_sales()
                    self.customer_input.clear()
                    del self.selected_customer_id
                    QMessageBox.information(self, "Success", "Sale added successfully.")
                else:
                    logger.error("Failed to add sale")
                    show_error_message("Error", "Failed to add sale.")
            else:
                logger.error("No items added to the sale")
                show_error_message("Error", "No items added to the sale.")
        except Exception as e:
            logger.error(f"Error adding sale: {str(e)}")
            show_error_message("Error", str(e))

    def view_sale(self, sale: Sale):
        items = self.sale_service.get_sale_items(sale.id)
        customer = self.customer_service.get_customer(sale.customer_id)
        customer_text = f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})" if customer else "Unknown Customer"
        
        message = f"Sale Details:\n\nCustomer: {customer_text}\nDate: {sale.date.strftime('%Y-%m-%d')}\n\nItems:\n"
        for item in items:
            product = self.product_service.get_product(item.product_id)
            product_name = product.name if product else "Unknown Product"
            message += f"- {product_name}: {item.quantity} @ {item.price:.2f}\n"
        message += f"\nTotal Amount: {sale.total_amount:.2f}"
        QMessageBox.information(self, "Sale Details", message)

    def delete_sale(self, sale: Sale):
        reply = QMessageBox.question(self, 'Delete Sale', 
                                     f'Are you sure you want to delete this sale?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.sale_service.delete_sale(sale.id)
                self.load_sales()
                QMessageBox.information(self, "Success", "Sale deleted successfully.")
            except Exception as e:
                logger.error(f"Error deleting sale: {str(e)}")
                show_error_message("Error", str(e))

    def search_sales(self):
        search_term = self.search_input.text().strip().lower()
        if search_term:
            sales = self.sale_service.get_all_sales()
            filtered_sales = [
                s for s in sales
                if search_term in str(s.id).lower() or
                search_term in s.date.strftime("%Y-%m-%d").lower() or
                search_term in str(s.total_amount).lower()
            ]
            self.update_sale_table(filtered_sales)
        else:
            self.load_sales()