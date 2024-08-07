from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QDialog, QDialogButtonBox, QFormLayout)
from PySide6.QtCore import Qt, Signal
from services.customer_service import CustomerService
from utils.helpers import create_table, show_error_message, format_price
from utils.ui.table_items import NumericTableWidgetItem, PriceTableWidgetItem
from utils.validation.validators import validate_9digit_identifier, validate_3or4digit_identifier
from utils.decorators import ui_operation
from models.customer import Customer
from typing import Optional

class EditCustomerDialog(QDialog):
    def __init__(self, customer: Optional[Customer], parent=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Edit Customer" if customer else "Add Customer")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.identifier_9_input = QLineEdit(self.customer.identifier_9 if self.customer else "")
        self.identifier_3or4_input = QLineEdit(self.customer.identifier_3or4 or "" if self.customer else "")
        
        layout.addRow("9-digit Identifier:", self.identifier_9_input)
        layout.addRow("3 or 4-digit Identifier:", self.identifier_3or4_input)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    @ui_operation(show_dialog=True)
    def validate_and_accept(self):
        try:
            validate_9digit_identifier(self.identifier_9_input.text())
            if self.identifier_3or4_input.text():
                validate_3or4digit_identifier(self.identifier_3or4_input.text())
            self.accept()
        except ValueError as e:
            show_error_message("Validation Error", str(e))

class CustomerView(QWidget):
    customer_updated = Signal()

    def __init__(self):
        super().__init__()
        self.customer_service = CustomerService()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Input fields
        input_layout = QHBoxLayout()
        self.identifier_9_input = QLineEdit()
        self.identifier_3or4_input = QLineEdit()
        input_layout.addWidget(QLabel("9-digit Identifier:"))
        input_layout.addWidget(self.identifier_9_input)
        input_layout.addWidget(QLabel("3 or 4-digit Identifier:"))
        input_layout.addWidget(self.identifier_3or4_input)
        
        add_button = QPushButton("Add Customer")
        add_button.clicked.connect(self.add_customer)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Search field
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search customers...")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_customers)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Customer table
        self.customer_table = create_table(["ID", "9-digit Identifier", "3 or 4-digit Identifier", "Total Purchases", "Total Amount", "Actions"])
        self.customer_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.customer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.customer_table)

        self.load_customers()

    @ui_operation(show_dialog=True)
    def load_customers(self):
        customers = self.customer_service.get_all_customers()
        self.populate_customer_table(customers)

    @ui_operation(show_dialog=True)
    def populate_customer_table(self, customers):
        self.customer_table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            total_purchases, total_amount = self.customer_service.get_customer_stats(customer.id)
            self.customer_table.setItem(row, 0, NumericTableWidgetItem(customer.id))
            self.customer_table.setItem(row, 1, QTableWidgetItem(customer.identifier_9))
            self.customer_table.setItem(row, 2, QTableWidgetItem(customer.identifier_3or4 or "N/A"))
            self.customer_table.setItem(row, 3, NumericTableWidgetItem(total_purchases))
            self.customer_table.setItem(row, 4, PriceTableWidgetItem(total_amount, format_price))
            
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            edit_button = QPushButton("Edit")
            edit_button.setFixedWidth(50)
            edit_button.clicked.connect(lambda _, c=customer: self.edit_customer(c))
            
            delete_button = QPushButton("Delete")
            delete_button.setFixedWidth(50)
            delete_button.clicked.connect(lambda _, c=customer: self.delete_customer(c))
            
            actions_layout.addWidget(edit_button)
            actions_layout.addWidget(delete_button)
            self.customer_table.setCellWidget(row, 5, actions_widget)

    @ui_operation(show_dialog=True)
    def add_customer(self):
        dialog = EditCustomerDialog(None, self)
        if dialog.exec():
            identifier_9 = dialog.identifier_9_input.text().strip()
            identifier_3or4 = dialog.identifier_3or4_input.text().strip() or None

            customer_id = self.customer_service.create_customer(identifier_9, identifier_3or4)
            if customer_id is not None:
                self.load_customers()
                QMessageBox.information(self, "Success", "Customer added successfully.")
                self.customer_updated.emit()
            else:
                show_error_message("Error", "Failed to add customer.")

    @ui_operation(show_dialog=True)
    def edit_customer(self, customer: Customer):
        dialog = EditCustomerDialog(customer, self)
        if dialog.exec():
            new_identifier_9 = dialog.identifier_9_input.text().strip()
            new_identifier_3or4 = dialog.identifier_3or4_input.text().strip() or None
            self.customer_service.update_customer(customer.id, new_identifier_9, new_identifier_3or4)
            self.load_customers()
            QMessageBox.information(self, "Success", "Customer updated successfully.")
            self.customer_updated.emit()

    @ui_operation(show_dialog=True)
    def delete_customer(self, customer: Customer):
        reply = QMessageBox.question(self, 'Delete Customer', 
                                     f'Are you sure you want to delete customer {customer.identifier_9}?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.customer_service.delete_customer(customer.id)
            self.load_customers()
            QMessageBox.information(self, "Success", "Customer deleted successfully.")
            self.customer_updated.emit()

    @ui_operation(show_dialog=True)
    def search_customers(self):
        search_term = self.search_input.text().strip()
        if search_term:
            customers = self.customer_service.search_customers(search_term)
            self.populate_customer_table(customers)
        else:
            self.load_customers()

    def refresh(self):
        self.load_customers()
