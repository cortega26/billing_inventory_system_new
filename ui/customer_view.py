from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt
from services.customer_service import CustomerService
from utils.utils import create_table, show_error_message

class EditCustomerDialog(QDialog):
    def __init__(self, customer, parent=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Edit Customer")
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.identifier_9_input = QLineEdit(customer.identifier_9)
        self.identifier_4_input = QLineEdit(customer.identifier_4 or "")
        
        self.layout.addWidget(QLabel("9-digit Identifier:"))
        self.layout.addWidget(self.identifier_9_input)
        self.layout.addWidget(QLabel("4-digit Identifier:"))
        self.layout.addWidget(self.identifier_4_input)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

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
        self.identifier_4_input = QLineEdit()
        input_layout.addWidget(QLabel("9-digit Identifier:"))
        input_layout.addWidget(self.identifier_9_input)
        input_layout.addWidget(QLabel("4-digit Identifier:"))
        input_layout.addWidget(self.identifier_4_input)
        
        add_button = QPushButton("Add Customer")
        add_button.clicked.connect(self.add_customer)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Customer table
        self.customer_table = create_table(["ID", "9-digit Identifier", "4-digit Identifier", "Total Purchases", "Total Amount", "Edit", "Delete"])
        self.customer_table.setSortingEnabled(True)  # Enable sorting
        layout.addWidget(self.customer_table)

        # Update 4-digit identifier button
        update_button = QPushButton("Update 4-digit Identifier for All")
        update_button.clicked.connect(self.update_identifier_4)
        layout.addWidget(update_button)

        self.load_customers()

    def load_customers(self):
        customers = self.customer_service.get_all_customers()
        self.customer_table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            total_purchases, total_amount = self.customer_service.get_customer_stats(customer.id)
            self.customer_table.setItem(row, 0, QTableWidgetItem(str(customer.id)))
            self.customer_table.setItem(row, 1, QTableWidgetItem(customer.identifier_9))
            self.customer_table.setItem(row, 2, QTableWidgetItem(customer.identifier_4 or ""))
            self.customer_table.setItem(row, 3, QTableWidgetItem(str(total_purchases)))
            self.customer_table.setItem(row, 4, QTableWidgetItem(f"{total_amount:.2f}"))
            
            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(lambda _, c=customer: self.edit_customer(c))
            self.customer_table.setCellWidget(row, 5, edit_button)
            
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, c=customer: self.delete_customer(c))
            self.customer_table.setCellWidget(row, 6, delete_button)

    def add_customer(self):
        identifier_9 = self.identifier_9_input.text().strip()
        identifier_4 = self.identifier_4_input.text().strip() or None

        if not identifier_9:
            show_error_message("Error", "9-digit identifier is required.")
            return

        try:
            self.customer_service.create_customer(identifier_9, identifier_4)
            self.load_customers()
            self.identifier_9_input.clear()
            self.identifier_4_input.clear()
            QMessageBox.information(self, "Success", "Customer added successfully.")
        except Exception as e:
            show_error_message("Error", str(e))

    def edit_customer(self, customer):
        dialog = EditCustomerDialog(customer, self)
        if dialog.exec():
            new_identifier_9 = dialog.identifier_9_input.text().strip()
            new_identifier_4 = dialog.identifier_4_input.text().strip() or None
            try:
                self.customer_service.update_customer(customer.id, new_identifier_9, new_identifier_4)
                self.load_customers()
                QMessageBox.information(self, "Success", "Customer updated successfully.")
            except Exception as e:
                show_error_message("Error", str(e))

    def delete_customer(self, customer):
        reply = QMessageBox.question(self, 'Delete Customer', 
                                     f'Are you sure you want to delete customer {customer.identifier_9}?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.customer_service.delete_customer(customer.id)
                self.load_customers()
                QMessageBox.information(self, "Success", "Customer deleted successfully.")
            except Exception as e:
                show_error_message("Error", str(e))

    def update_identifier_4(self):
        identifier_4 = self.identifier_4_input.text().strip()
        if not identifier_4:
            show_error_message("Error", "4-digit identifier is required for update.")
            return

        try:
            self.customer_service.update_identifier_4(identifier_4)
            self.load_customers()
            QMessageBox.information(self, "Success", "4-digit identifier updated for all customers.")
        except Exception as e:
            show_error_message("Error", str(e))