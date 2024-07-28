from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QComboBox, QDateEdit, QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt, QDate
from services.sale_service import SaleService
from services.customer_service import CustomerService
from services.product_service import ProductService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system

class CustomerSelectionDialog(QDialog):
    def __init__(self, customers, parent=None):
        super().__init__(parent)
        self.customers = customers
        self.setWindowTitle("Select Customer")
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.customer_combo = QComboBox()
        for customer in customers:
            self.customer_combo.addItem(f"{customer.identifier_9} ({customer.identifier_4 or 'N/A'})", customer.id)
        
        self.layout.addWidget(QLabel("Select a customer:"))
        self.layout.addWidget(self.customer_combo)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def get_selected_customer(self):
        return self.customer_combo.currentData()

class EditSaleDialog(QDialog):
    def __init__(self, sale, parent=None):
        super().__init__(parent)
        self.sale = sale
        self.setWindowTitle("Edit Sale")
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.customer_combo = QComboBox()
        self.product_combo = QComboBox()
        self.quantity_input = QLineEdit(str(sale.quantity))
        self.price_input = QLineEdit(str(sale.price))
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.fromString(sale.date, "yyyy-MM-dd"))
        self.date_input.setCalendarPopup(True)
        
        self.layout.addWidget(QLabel("Customer:"))
        self.layout.addWidget(self.customer_combo)
        self.layout.addWidget(QLabel("Product:"))
        self.layout.addWidget(self.product_combo)
        self.layout.addWidget(QLabel("Quantity:"))
        self.layout.addWidget(self.quantity_input)
        self.layout.addWidget(QLabel("Price:"))
        self.layout.addWidget(self.price_input)
        self.layout.addWidget(QLabel("Date:"))
        self.layout.addWidget(self.date_input)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        # Load customers and products
        self.load_customers()
        self.load_products()

    def load_customers(self):
        customers = CustomerService().get_all_customers()
        self.customer_combo.clear()
        for customer in customers:
            self.customer_combo.addItem(f"{customer.identifier_9} ({customer.identifier_4 or 'N/A'})", customer.id)
        self.customer_combo.setCurrentIndex(self.customer_combo.findData(self.sale.customer_id))

    def load_products(self):
        products = ProductService().get_all_products()
        self.product_combo.clear()
        for product in products:
            self.product_combo.addItem(product.name, product.id)
        self.product_combo.setCurrentIndex(self.product_combo.findData(self.sale.product_id))

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
        self.sale_table = create_table(["ID", "Customer", "Product", "Quantity", "Price", "Date", "Total Amount", "Edit", "Delete"])
        self.sale_table.setSortingEnabled(True)  # Enable sorting
        layout.addWidget(self.sale_table)

        self.load_products()
        self.load_sales()

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
            sale_items = self.sale_service.get_sale_items(sale.id)
            
            if sale_items:
                sale_item = sale_items[0]  # Assuming we're displaying the first item for simplicity
                product = self.product_service.get_product(sale_item.product_id)
                
                self.sale_table.setItem(row, 0, QTableWidgetItem(str(sale.id)))
                
                # Handle potential None customer
                if customer:
                    customer_text = f"{customer.identifier_9} ({customer.identifier_4 or 'N/A'})"
                else:
                    customer_text = "Unknown Customer"
                self.sale_table.setItem(row, 1, QTableWidgetItem(customer_text))
                
                # Handle potential None product
                product_name = product.name if product else "Unknown Product"
                self.sale_table.setItem(row, 2, QTableWidgetItem(product_name))
                
                self.sale_table.setItem(row, 3, QTableWidgetItem(str(sale_item.quantity)))
                self.sale_table.setItem(row, 4, QTableWidgetItem(f"{sale_item.price:.2f}"))
                self.sale_table.setItem(row, 5, QTableWidgetItem(sale.date))
                self.sale_table.setItem(row, 6, QTableWidgetItem(f"{sale.total_amount:.2f}"))
            else:
                # Handle case where there are no sale items
                for col in range(7):
                    self.sale_table.setItem(row, col, QTableWidgetItem("N/A"))
            
            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(lambda _, s=sale: self.edit_sale(s))
            self.sale_table.setCellWidget(row, 7, edit_button)
            
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, s=sale: self.delete_sale(s))
            self.sale_table.setCellWidget(row, 8, delete_button)

    def select_customer(self):
        identifier = self.customer_id_input.text().strip()
        if len(identifier) == 4:
            customers = self.customer_service.get_customers_by_identifier_4(identifier)
        elif len(identifier) == 9:
            customer = self.customer_service.get_customer_by_identifier_9(identifier)
            customers = [customer] if customer else []
        else:
            show_error_message("Error", "Please enter a valid 4-digit or 9-digit identifier.")
            return

        if not customers:
            show_error_message("Error", "No customers found with the given identifier.")
            return

        if len(customers) == 1:
            self.selected_customer_id = customers[0].id
            self.customer_id_input.setText(f"{customers[0].identifier_9} ({customers[0].identifier_4 or 'N/A'})")
        else:
            dialog = CustomerSelectionDialog(customers, self)
            if dialog.exec():
                self.selected_customer_id = dialog.get_selected_customer()
                selected_customer = next(c for c in customers if c.id == self.selected_customer_id)
                self.customer_id_input.setText(f"{selected_customer.identifier_9} ({selected_customer.identifier_4 or 'N/A'})")

    def add_sale(self):
        if not hasattr(self, 'selected_customer_id'):
            show_error_message("Error", "Please select a customer first.")
            return

        product_id = self.product_combo.currentData()
        quantity = self.quantity_input.text().strip()
        price = self.price_input.text().strip()
        date = self.date_input.date().toString("yyyy-MM-dd")

        if not all([product_id, quantity, price]):
            show_error_message("Error", "All fields are required.")
            return

        try:
            quantity = int(quantity)
            price = float(price)
            
            sale_data = {
                "customer_id": self.selected_customer_id,
                "date": date,
                "items": [{"product_id": product_id, "quantity": quantity, "price": price}]
            }
            
            self.sale_service.create_sale(self.selected_customer_id, date, sale_data["items"])
            self.load_sales()
            self.customer_id_input.clear()
            self.quantity_input.clear()
            self.price_input.clear()
            del self.selected_customer_id
            QMessageBox.information(self, "Success", "Sale added successfully.")
        except ValueError:
            show_error_message("Error", "Invalid quantity or price.")
        except Exception as e:
            show_error_message("Error", str(e))

    def edit_sale(self, sale):
        dialog = EditSaleDialog(sale, self)
        if dialog.exec():
            new_customer_id = dialog.customer_combo.currentData()
            new_product_id = dialog.product_combo.currentData()
            new_quantity = dialog.quantity_input.text().strip()
            new_price = dialog.price_input.text().strip()
            new_date = dialog.date_input.date().toString("yyyy-MM-dd")
            
            try:
                new_quantity = int(new_quantity)
                new_price = float(new_price)
                
                updated_sale_data = {
                    "customer_id": new_customer_id,
                    "date": new_date,
                    "items": [{"product_id": new_product_id, "quantity": new_quantity, "price": new_price}]
                }
                
                self.sale_service.update_sale(sale.id, updated_sale_data)
                self.load_sales()
                QMessageBox.information(self, "Success", "Sale updated successfully.")
            except ValueError:
                show_error_message("Error", "Invalid quantity or price.")
            except Exception as e:
                show_error_message("Error", str(e))

    def delete_sale(self, sale):
        reply = QMessageBox.question(self, 'Delete Sale', 
                                     f'Are you sure you want to delete this sale?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.sale_service.delete_sale(sale.id)
                self.load_sales()
                QMessageBox.information(self, "Success", "Sale deleted successfully.")
            except Exception as e:
                show_error_message("Error", str(e))