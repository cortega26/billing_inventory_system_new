from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from services.customer_service import CustomerService
from utils.utils import create_table, show_error_message
from utils.validators import validate_9digit_identifier, validate_3or4digit_identifier
from utils.logger import logger

class EditCustomerDialog(QDialog):
    def __init__(self, customer, parent=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Edit Customer")
        self.setModal(True)
        layout = QVBoxLayout(self)
        
        self.identifier_9_input = QLineEdit(customer.identifier_9)
        self.identifier_3or4_input = QLineEdit()
        
        layout.addWidget(QLabel("9-digit Identifier:"))
        layout.addWidget(self.identifier_9_input)
        layout.addWidget(QLabel("Add 3 or 4-digit Identifier:"))
        layout.addWidget(self.identifier_3or4_input)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def validate_and_accept(self):
        try:
            validate_9digit_identifier(self.identifier_9_input.text())
            if self.identifier_3or4_input.text():
                validate_3or4digit_identifier(self.identifier_3or4_input.text())
            self.accept()
        except ValueError as e:
            show_error_message("Validation Error", str(e))

class CustomerView(QWidget):
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

        # Customer table
        self.customer_table = create_table(["ID", "9-digit Identifier", "3 or 4-digit Identifiers", "Total Purchases", "Total Amount", "Actions"])
        self.customer_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.customer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.customer_table)

        self.load_customers()

    def load_customers(self):
        logger.debug("Loading customers")
        try:
            customers = self.customer_service.get_all_customers()
            self.customer_table.setRowCount(len(customers))
            for row, customer in enumerate(customers):
                logger.debug(f"Loading customer: {customer}")
                total_purchases, total_amount = self.customer_service.get_customer_stats(customer.id)
                self.customer_table.setItem(row, 0, QTableWidgetItem(str(customer.id)))
                self.customer_table.setItem(row, 1, QTableWidgetItem(customer.identifier_9))
                self.customer_table.setItem(row, 2, QTableWidgetItem(', '.join([i.identifier_3or4 for i in customer.identifiers_3or4]) or "N/A"))
                self.customer_table.setItem(row, 3, QTableWidgetItem(str(total_purchases)))
                self.customer_table.setItem(row, 4, QTableWidgetItem(f"{total_amount:,}"))
                
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
            logger.debug(f"Loaded {len(customers)} customers")
        except Exception as e:
            logger.error(f"Failed to load customers: {str(e)}")
            show_error_message("Error", f"Failed to load customers: {str(e)}")

    def add_customer(self):
        identifier_9 = self.identifier_9_input.text().strip()
        identifier_3or4 = self.identifier_3or4_input.text().strip() or None
        logger.debug(f"Adding customer with identifier_9: {identifier_9}, identifier_3or4: {identifier_3or4}")

        try:
            validate_9digit_identifier(identifier_9)
            if identifier_3or4:
                validate_3or4digit_identifier(identifier_3or4)

            customer_id = self.customer_service.create_customer(identifier_9, identifier_3or4)
            if customer_id is not None:
                logger.debug(f"Customer added successfully with ID: {customer_id}")
                self.load_customers()
                self.identifier_9_input.clear()
                self.identifier_3or4_input.clear()
                QMessageBox.information(self, "Success", "Customer added successfully.")
            else:
                logger.error("Failed to add customer")
                show_error_message("Error", "Failed to add customer.")
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            show_error_message("Validation Error", str(e))
        except Exception as e:
            logger.error(f"Error adding customer: {str(e)}")
            show_error_message("Error", str(e))

    def edit_customer(self, customer):
        dialog = EditCustomerDialog(customer, self)
        if dialog.exec():
            new_identifier_9 = dialog.identifier_9_input.text().strip()
            new_identifier_3or4 = dialog.identifier_3or4_input.text().strip() or None
            try:
                self.customer_service.update_customer(customer.id, new_identifier_9, new_identifier_3or4)
                self.load_customers()
                QMessageBox.information(self, "Success", "Customer updated successfully.")
            except Exception as e:
                logger.error(f"Error updating customer: {str(e)}")
                show_error_message("Error", str(e))

    def delete_customer(self, customer):
        reply = QMessageBox.question(self, 'Delete Customer', 
                                     f'Are you sure you want to delete customer {customer.identifier_9}?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.customer_service.delete_customer(customer.id)
                self.load_customers()
                QMessageBox.information(self, "Success", "Customer deleted successfully.")
            except Exception as e:
                logger.error(f"Error deleting customer: {str(e)}")
                show_error_message("Error", str(e))