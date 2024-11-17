from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QMessageBox, QDialog, QDialogButtonBox, 
    QFormLayout, QHeaderView, QMenu, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence
from services.customer_service import CustomerService
from utils.helpers import create_table, show_error_message, show_info_message, format_price
from utils.system.event_system import event_system
from utils.ui.table_items import NumericTableWidgetItem, PriceTableWidgetItem, DepartmentIdentifierTableWidgetItem
from typing import Optional
from models.customer import Customer
from utils.decorators import ui_operation, handle_exceptions
from utils.exceptions import ValidationException, DatabaseException, UIException
from utils.validation.validators import validate_string
from utils.system.logger import logger

class EditCustomerDialog(QDialog):
    def __init__(self, customer: Optional[Customer], parent=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Edit Customer" if customer else "Add Customer")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        # 9-digit identifier
        self.identifier_9_input = QLineEdit(
            self.customer.identifier_9 if self.customer else ""
        )
        self.identifier_9_input.setPlaceholderText("Enter 9-digit identifier")
        layout.addRow("9-digit Identifier:", self.identifier_9_input)

        # 3 or 4-digit identifier
        self.identifier_3or4_input = QLineEdit(
            self.customer.identifier_3or4 or "" if self.customer else ""
        )
        self.identifier_3or4_input.setPlaceholderText("Enter 3 or 4-digit identifier (optional)")
        layout.addRow("3 or 4-digit Identifier:", self.identifier_3or4_input)

        # Name field
        self.name_input = QLineEdit(
            self.customer.name or "" if self.customer else ""
        )
        self.name_input.setPlaceholderText("Enter customer name (optional)")
        layout.addRow("Name:", self.name_input)

        # Add help text for name requirements
        name_help = QLabel("Name can contain letters, accented characters, and spaces (max 50 chars)")
        name_help.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow("", name_help)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, show_dialog=True)
    def validate_and_accept(self):
        try:
            # Create a temporary customer to validate the input
            temp_customer = Customer(
                id=0,
                identifier_9=self.identifier_9_input.text().strip(),
                identifier_3or4=self.identifier_3or4_input.text().strip() or None,
                name=self.name_input.text().strip() or None
            )
            self.accept()
        except ValidationException as e:
            raise ValidationException(str(e))

class CustomerView(QWidget):
    customer_updated = Signal()

    def __init__(self):
        super().__init__()
        self.customer_service = CustomerService()
        self.setup_ui()

    def __del__(self):
        # Disconnect from event system to prevent multiple connections
        event_system.customer_added.disconnect(self.load_customers)
        event_system.customer_updated.disconnect(self.load_customers)
        event_system.customer_deleted.disconnect(self.load_customers)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search field
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by ID or name...")
        self.search_input.returnPressed.connect(self.search_customers)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_customers)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Customer table
        self.customer_table = create_table(
            [
                "ID",
                "9-digit Identifier",
                "3 or 4-digit Identifier",
                "Name",
                "Total Purchases",
                "Total Amount",
                "Actions",
            ]
        )
        self.customer_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.customer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.customer_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.customer_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customer_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.customer_table)

        # Add customer button
        add_button = QPushButton("Add Customer")
        add_button.clicked.connect(self.add_customer)
        add_button.setToolTip("Add a new customer (Ctrl+N)")
        layout.addWidget(add_button)

        self.load_customers()

        # Set up shortcuts
        self.setup_shortcuts()

        # Connect to event system
        event_system.customer_added.connect(self.load_customers)
        event_system.customer_updated.connect(self.load_customers)
        event_system.customer_deleted.connect(self.load_customers)

    def setup_shortcuts(self):
        add_shortcut = QAction("Add Customer", self)
        add_shortcut.setShortcut(QKeySequence("Ctrl+N"))
        add_shortcut.triggered.connect(self.add_customer)
        self.addAction(add_shortcut)

        refresh_shortcut = QAction("Refresh", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_customers)
        self.addAction(refresh_shortcut)

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_customers(self):
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            
            # Clear the table first
            self.customer_table.setRowCount(0)
            
            # Force a cache clear
            self.customer_service.clear_cache()
            
            customers = self.customer_service.get_all_customers()
            QTimer.singleShot(0, lambda: self.populate_customer_table(customers))
            logger.info(f"Loaded {len(customers)} customers")
        except Exception as e:
            logger.error(f"Error loading customers: {str(e)}")
            raise DatabaseException(f"Failed to load customers: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def populate_customer_table(self, customers):
        """Populate the customer table with data."""
        try:
            logger.debug(f"Starting population of customer table with {len(customers)} customers")
            
            # Create a set to track displayed customer IDs
            displayed_customers = set()
            
            # Initially set row count to total customers
            self.customer_table.setRowCount(len(customers))
            current_row = 0
            
            for customer in customers:
                # Skip if this customer ID is already displayed
                if customer.id in displayed_customers:
                    logger.warning(f"Duplicate customer detected: ID {customer.id}, Name: {customer.name}")
                    continue
                    
                displayed_customers.add(customer.id)
                
                try:
                    # Get customer stats
                    total_purchases, total_amount = self.customer_service.get_customer_stats(
                        customer.id
                    )
                    
                    # Basic information
                    self.customer_table.setItem(current_row, 0, NumericTableWidgetItem(customer.id))
                    self.customer_table.setItem(current_row, 1, QTableWidgetItem(customer.identifier_9))
                    
                    # Use the new custom item for department identifier
                    self.customer_table.setItem(
                        current_row, 2, 
                        DepartmentIdentifierTableWidgetItem(customer.identifier_3or4 or "N/A")
                    )
                    
                    # Name column
                    name_item = QTableWidgetItem(customer.name or "")
                    name_item.setToolTip(customer.name if customer.name else "No name provided")
                    self.customer_table.setItem(current_row, 3, name_item)
                    
                    # Statistics
                    self.customer_table.setItem(current_row, 4, NumericTableWidgetItem(total_purchases))
                    self.customer_table.setItem(
                        current_row, 5, PriceTableWidgetItem(total_amount, format_price)
                    )

                    # Actions
                    actions_widget = QWidget()
                    actions_layout = QHBoxLayout(actions_widget)
                    actions_layout.setContentsMargins(0, 0, 0, 0)

                    edit_button = QPushButton("Edit")
                    edit_button.setFixedWidth(50)
                    edit_button.clicked.connect(lambda _, c=customer: self.edit_customer(c))
                    edit_button.setToolTip("Edit this customer")

                    delete_button = QPushButton("Delete")
                    delete_button.setFixedWidth(50)
                    delete_button.clicked.connect(lambda _, c=customer: self.delete_customer(c))
                    delete_button.setToolTip("Delete this customer")

                    actions_layout.addWidget(edit_button)
                    actions_layout.addWidget(delete_button)
                    self.customer_table.setCellWidget(current_row, 6, actions_widget)

                    current_row += 1
                    
                except Exception as row_error:
                    logger.error(f"Error processing customer {customer.id}: {str(row_error)}")
                    continue
            
            # Adjust final row count if we skipped duplicates
            if current_row < len(customers):
                logger.info(f"Adjusting table row count from {len(customers)} to {current_row} due to duplicates")
                self.customer_table.setRowCount(current_row)

            # Adjust column widths
            self.customer_table.resizeColumnsToContents()
            
            # Enable sorting
            self.customer_table.setSortingEnabled(True)
            
            # Sort by department identifier initially (column 2)
            self.customer_table.sortItems(2, Qt.SortOrder.AscendingOrder)
            
            logger.debug(f"Finished populating customer table with {current_row} rows")
            
        except Exception as e:
            logger.error(f"Error populating customer table: {str(e)}")
            # Log the full error details for debugging
            logger.error("Full error details:", exc_info=True)
            raise UIException(f"Failed to populate customer table: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def add_customer(self):
        dialog = EditCustomerDialog(None, self)
        if dialog.exec():
            try:
                customer_id = self.customer_service.create_customer(
                    identifier_9=dialog.identifier_9_input.text().strip(),
                    name=dialog.name_input.text().strip() or None,
                    identifier_3or4=dialog.identifier_3or4_input.text().strip() or None
                )
                if customer_id is not None:
                    self.load_customers()
                    show_info_message("Success", "Customer added successfully.")
                    event_system.customer_added.emit(customer_id)
                    self.customer_updated.emit()
                    logger.info(f"Customer added successfully: ID {customer_id}")
                else:
                    raise DatabaseException("Failed to add customer.")
            except Exception as e:
                logger.error(f"Error adding customer: {str(e)}")
                raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def edit_customer(self, customer: Optional[Customer]):
        if customer is None:
            raise ValidationException("No customer selected for editing.")

        dialog = EditCustomerDialog(customer, self)
        if dialog.exec():
            try:
                self.customer_service.update_customer(
                    customer.id,
                    identifier_9=dialog.identifier_9_input.text().strip(),
                    name=dialog.name_input.text().strip() or None,
                    identifier_3or4=dialog.identifier_3or4_input.text().strip() or None
                )
                self.load_customers()
                show_info_message("Success", "Customer updated successfully.")
                event_system.customer_updated.emit(customer.id)
                self.customer_updated.emit()
                logger.info(f"Customer updated successfully: ID {customer.id}")
            except Exception as e:
                logger.error(f"Error updating customer: {str(e)}")
                raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def delete_customer(self, customer: Optional[Customer]):
        if customer is None:
            raise ValidationException("No customer selected for deletion.")

        display_name = customer.get_display_name()
        reply = QMessageBox.question(
            self,
            "Delete Customer",
            f"Are you sure you want to delete customer {display_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.customer_service.delete_customer(customer.id)
                self.load_customers()
                show_info_message("Success", "Customer deleted successfully.")
                event_system.customer_deleted.emit(customer.id)
                self.customer_updated.emit()
                logger.info(f"Customer deleted successfully: ID {customer.id}")
            except Exception as e:
                logger.error(f"Error deleting customer: {str(e)}")
                raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def search_customers(self):
        search_term = self.search_input.text().strip()
        search_term = validate_string(search_term, max_length=50)
        if search_term:
            try:
                customers = self.customer_service.search_customers(search_term)
                self.populate_customer_table(customers)
                logger.info(f"Customer search performed: '{search_term}'")
            except Exception as e:
                logger.error(f"Error searching customers: {str(e)}")
                raise
        else:
            self.load_customers()

    def show_context_menu(self, position):
        menu = QMenu()
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")

        action = menu.exec(self.customer_table.mapToGlobal(position))
        if action:
            row = self.customer_table.rowAt(position.y())
            customer_id = self.customer_table.item(row, 0).text()
            customer = self.customer_service.get_customer(int(customer_id))

            if customer is not None:
                if action == edit_action:
                    self.edit_customer(customer)
                elif action == delete_action:
                    self.delete_customer(customer)
            else:
                show_error_message(
                    "Error", f"Customer with ID {customer_id} not found."
                )

    def refresh(self):
        self.load_customers()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_rows = self.customer_table.selectionModel().selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                customer_id = int(self.customer_table.item(row, 0).text())
                customer = self.customer_service.get_customer(customer_id)
                if customer:
                    self.delete_customer(customer)
        else:
            super().keyPressEvent(event)
