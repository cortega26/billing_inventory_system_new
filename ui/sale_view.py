from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
                               QDoubleSpinBox, QProgressBar, QHeaderView)
from PySide6.QtCore import Qt, QDate, QTimer
from services.sale_service import SaleService
from services.customer_service import CustomerService
from services.product_service import ProductService
from models.customer import Customer
from models.sale import Sale
from utils.utils import create_table, show_error_message, show_info_message, format_price
from utils.logger import logger
from utils.event_system import event_system
from utils.table_items import NumericTableWidgetItem, PriceTableWidgetItem
from typing import List

class CustomerSelectionDialog(QDialog):
    def __init__(self, customers: List[Customer], parent=None):
        super().__init__(parent)
        self.customers = customers
        self.setWindowTitle("Select Customer")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.customer_combo = QComboBox()
        for customer in self.customers:
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
        layout = QFormLayout(self)
        
        self.product_combo = QComboBox()
        for product in self.products:
            self.product_combo.addItem(product.name, product)
        self.product_combo.currentIndexChanged.connect(self.update_price)
        layout.addRow("Product:", self.product_combo)
        
        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setMinimum(0.01)
        self.quantity_input.setMaximum(1000000.00)
        self.quantity_input.setDecimals(2)
        self.quantity_input.valueChanged.connect(self.update_total)
        layout.addRow("Quantity:", self.quantity_input)
        
        self.price_input = QDoubleSpinBox()
        self.price_input.setMinimum(0.01)
        self.price_input.setMaximum(1000000.00)
        self.price_input.setDecimals(2)
        self.price_input.valueChanged.connect(self.update_total)
        layout.addRow("Sell Price:", self.price_input)
        
        self.total_label = QLabel("0.00")
        layout.addRow("Total:", self.total_label)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

        self.update_price()

    def update_price(self):
        product = self.product_combo.currentData()
        if product and product.sell_price is not None:
            self.price_input.setValue(product.sell_price)
        else:
            self.price_input.setValue(0.00)
        self.update_total()

    def update_total(self):
        total = self.quantity_input.value() * self.price_input.value()
        self.total_label.setText(f"{total:.2f}")

    def validate_and_accept(self):
        if self.quantity_input.value() <= 0:
            show_error_message("Invalid Quantity", "Quantity must be greater than 0.")
            return
        if self.price_input.value() <= 0:
            show_error_message("Invalid Price", "Price must be greater than 0.")
            return
        self.accept()

    def get_item_data(self):
        product = self.product_combo.currentData()
        return {
            "product_id": product.id,
            "product_name": product.name,
            "quantity": self.quantity_input.value(),
            "sell_price": self.price_input.value()
        }

class SaleView(QWidget):
    def __init__(self):
        super().__init__()
        self.sale_service = SaleService()
        self.customer_service = CustomerService()
        self.product_service = ProductService()
        self.setup_ui()

        # Connect to event system
        event_system.product_updated.connect(self.on_product_updated)
        event_system.product_deleted.connect(self.on_product_deleted)

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
        self.customer_input.setPlaceholderText("Enter 9-digit or 3/4-digit identifier")
        self.customer_select_button = QPushButton("Select Customer")
        self.customer_select_button.clicked.connect(self.select_customer)
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setFixedWidth(150)
        
        input_layout.addWidget(QLabel("Customer:"))
        input_layout.addWidget(self.customer_input)
        input_layout.addWidget(self.customer_select_button)
        input_layout.addWidget(QLabel("Date:"))
        input_layout.addWidget(self.date_input)
        input_layout.addStretch(1)
        
        add_button = QPushButton("Add Sale")
        add_button.clicked.connect(self.add_sale)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Sale table
        self.sale_table = create_table(["ID", "Customer", "Date", "Total Amount", "Actions"])
        self.sale_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sale_table.setSortingEnabled(True)
        self.sale_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.sale_table)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.load_sales()

    def load_sales(self):
        logger.debug("Loading sales")
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            sales = self.sale_service.get_all_sales()
            self.update_sale_table(sales)
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
        except Exception as e:
            logger.error(f"Failed to load sales: {str(e)}")
            show_error_message("Error", f"Failed to load sales: {str(e)}")
            self.progress_bar.setVisible(False)

    def update_sale_table(self, sales: List[Sale]):
        self.sale_table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            try:
                customer = self.customer_service.get_customer(sale.customer_id)
                
                #self.sale_table.setItem(row, 0, QTableWidgetItem(str(sale.id)))
                self.sale_table.setItem(row, 0, NumericTableWidgetItem(sale.id))

                customer_text = f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})" if customer else "Unknown Customer"
                self.sale_table.setItem(row, 1, QTableWidgetItem(customer_text))

                self.sale_table.setItem(row, 2, QTableWidgetItem(sale.date.strftime("%Y-%m-%d")))

                total_amount_item = QTableWidgetItem(format_price(sale.total_amount))
                total_amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                #self.sale_table.setItem(row, 3, total_amount_item)
                self.sale_table.setItem(row, 3, PriceTableWidgetItem(sale.total_amount, format_price))

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

            except Exception as e:
                logger.error(f"Error populating sale row: {str(e)}")

    def select_customer(self):
        identifier = self.customer_input.text().strip()
        logger.debug(f"Selecting customer with identifier: {identifier}")
        try:
            if len(identifier) == 9:
                customer = self.customer_service.get_customer_by_identifier_9(identifier)
            elif len(identifier) in (3, 4):
                customers = self.customer_service.get_customers_by_identifier_3or4(identifier)
                if len(customers) == 1:
                    customer = customers[0]
                elif len(customers) > 1:
                    # If multiple customers found, show a dialog to select one
                    dialog = CustomerSelectionDialog(customers, self)
                    if dialog.exec():
                        customer = self.customer_service.get_customer(dialog.get_selected_customer())
                    else:
                        return
                else:
                    customer = None
            else:
                raise ValueError("Invalid identifier length")
            
            if customer:
                self.selected_customer_id = customer.id
                self.customer_input.setText(f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})")
            else:
                show_error_message("Error", "No customer found with the given identifier.")
        except Exception as e:
            logger.error(f"Error selecting customer: {str(e)}")
            show_error_message("Error", str(e))

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
                    reply = QMessageBox.question(
                        self, "Add Another Item", "Do you want to add another item?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
                        )
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
                    show_info_message("Success", "Sale added successfully.")
                    event_system.sale_added.emit(sale_id)
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
        try:
            items = self.sale_service.get_sale_items(sale.id)
            customer = self.customer_service.get_customer(sale.customer_id)
            customer_text = f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})" if customer else "Unknown Customer"
            
            message = f"<pre>"
            message += f"{'Sale Details':=^60}\n\n"
            message += f"Customer: {customer_text}\n"
            message += f"Date: {sale.date.strftime('%Y-%m-%d')}\n"
            message += f"{'':=^60}\n\n"
            message += f"{'Item':<20}{'Quantity':>10}{'Unit Price':>15}{'Subtotal':>15}\n"
            message += f"{'':-^60}\n"
            for item in items:
                product = self.product_service.get_product(item.product_id)
                product_name = product.name if product else "Unknown Product"
                message += f"{product_name[:20]:<20}{item.quantity:>10.2f}{format_price(item.unit_price):>15}{format_price(item.total_price()):>15}\n"
            message += f"{'':-^60}\n"
            message += f"{'Total Amount:':<45}{format_price(sale.total_amount):>15}\n"
            message += "</pre>"
            
            show_info_message("Sale Details", message)
        except Exception as e:
            logger.error(f"Error viewing sale details: {str(e)}")
            show_error_message("Error", f"Failed to view sale details: {str(e)}")

    def delete_sale(self, sale: Sale):
        reply = QMessageBox.question(
            self, 'Delete Sale', 
            f'Are you sure you want to delete this sale?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
            )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.sale_service.delete_sale(sale.id)
                self.load_sales()
                show_info_message("Success", "Sale deleted successfully.")
                event_system.sale_deleted.emit(sale.id)
            except Exception as e:
                logger.error(f"Error deleting sale: {str(e)}")
                show_error_message("Error", str(e))

    def search_sales(self):
        search_term = self.search_input.text().strip().lower()
        if search_term:
            try:
                sales = self.sale_service.get_all_sales()
                filtered_sales = [
                    s for s in sales
                    if search_term in str(s.id).lower() or
                    search_term in s.date.strftime("%Y-%m-%d").lower() or
                    search_term in str(s.total_amount).lower()
                ]
                self.update_sale_table(filtered_sales)
            except Exception as e:
                logger.error(f"Error searching sales: {str(e)}")
                show_error_message("Error", f"Failed to search sales: {str(e)}")
        else:
            self.load_sales()

    def on_product_updated(self, product_id):
        # Refresh the sale items if the updated product is part of any sale
        self.load_sales()

    def on_product_deleted(self, product_id):
        # Handle the case where a product in a sale has been deleted
        self.load_sales()