from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox)
from PySide6.QtCore import Qt
from services.customer_service import CustomerService
from utils.utils import create_table, show_error_message

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
        self.customer_table = create_table(["ID", "9-digit Identifier", "4-digit Identifier"])
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
            self.customer_table.setItem(row, 0, QTableWidgetItem(str(customer.id)))
            self.customer_table.setItem(row, 1, QTableWidgetItem(customer.identifier_9))
            self.customer_table.setItem(row, 2, QTableWidgetItem(customer.identifier_4 or ""))

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