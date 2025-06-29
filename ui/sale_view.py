from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QMessageBox, QDialog, QDialogButtonBox, 
    QFormLayout, QDateEdit, QComboBox, QDoubleSpinBox, QSpinBox, QHeaderView,
    QMenu, QApplication, QFileDialog
)
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtCore import Qt, QDate, QTimer, Signal, QUrl, QPoint
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from services.sale_service import SaleService
from services.customer_service import CustomerService
from services.product_service import ProductService
from models.customer import Customer
from models.sale import Sale
from models.product import Product
from utils.helpers import (
    create_table, show_error_message, show_info_message, format_price, confirm_action
)
from utils.system.event_system import event_system
from utils.ui.table_items import NumericTableWidgetItem, PriceTableWidgetItem
from typing import List, Optional, Dict, Any
from utils.decorators import ui_operation, handle_exceptions
from utils.exceptions import ValidationException, DatabaseException, UIException
from utils.validation.validators import validate_date
from utils.system.logger import logger
from utils.ui.sound import SoundEffect
from utils.validation.validators import validate_money
from datetime import datetime, timedelta


class EditSaleDialog(QDialog):
    def __init__(self, sale: Sale, sale_service: SaleService, customer_service: CustomerService, 
                 product_service: ProductService, parent=None):
        super().__init__(parent)
        self.sale = sale
        self.sale_service = sale_service
        self.customer_service = customer_service
        self.product_service = product_service
        self.sale_items = []
        self.selected_customer_id = sale.customer_id
        
        self.setWindowTitle(f"Edit Sale #{sale.id}")
        self.setup_ui()
        self.load_sale_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Customer info section
        customer_group = QWidget()
        customer_layout = QHBoxLayout(customer_group)
        self.customer_info_label = QLabel()
        customer_layout.addWidget(QLabel("Customer:"))
        customer_layout.addWidget(self.customer_info_label)
        layout.addWidget(customer_group)

        # Date section
        date_group = QWidget()
        date_layout = QHBoxLayout(date_group)
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setMinimumWidth(120)
        date_layout.addWidget(QLabel("Date:"))
        date_layout.addWidget(self.date_input)
        date_layout.addStretch()
        layout.addWidget(date_group)

        # Barcode and search section
        barcode_group = QWidget()
        barcode_layout = QHBoxLayout(barcode_group)
        
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Scan barcode...")
        self.barcode_input.returnPressed.connect(self.handle_barcode_scan)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search products...")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_products)
        
        barcode_layout.addWidget(QLabel("Barcode:"))
        barcode_layout.addWidget(self.barcode_input)
        barcode_layout.addWidget(QLabel("Search:"))
        barcode_layout.addWidget(self.search_input)
        barcode_layout.addWidget(search_button)
        layout.addWidget(barcode_group)

        # Items table
        self.items_table = create_table(
            ["Product ID", "Product Name", "Quantity", "Unit Price", "Total", "Actions"]
        )
        layout.addWidget(self.items_table)

        # Total amount
        total_layout = QHBoxLayout()
        self.total_amount_label = QLabel("Total: $ 0")
        self.total_amount_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        total_layout.addStretch()
        total_layout.addWidget(self.total_amount_label)
        layout.addLayout(total_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Set dialog size
        self.resize(800, 600)

    def load_sale_data(self):
        try:
            # Load customer info
            customer = self.customer_service.get_customer(self.sale.customer_id)
            if customer:
                display_parts = []
                if customer.identifier_3or4:
                    display_parts.append(customer.identifier_3or4)
                if customer.name:
                    display_parts.append(customer.name)
                display_parts.append(customer.identifier_9)
                self.customer_info_label.setText(" - ".join(display_parts))

            # Set date
            qdate = QDate.fromString(self.sale.date.strftime("%Y-%m-%d"), "yyyy-MM-dd")
            self.date_input.setDate(qdate)

            # Load items
            items = self.sale_service.get_sale_items(self.sale.id)
            for item in items:
                # Get the product to ensure we have the correct name
                product = self.product_service.get_product(item.product_id)
                item_data = {
                    "product_id": item.product_id,
                    "product_name": product.name if product else "Unknown Product",
                    "quantity": item.quantity,
                    "sell_price": item.unit_price,
                    "profit": item.profit
                }
                self.sale_items.append(item_data)
            
            self.update_items_table()

        except Exception as e:
            logger.error(f"Error loading sale data: {str(e)}")
            raise

    def update_items_table(self):
        """Update the items table display."""
        self.items_table.setRowCount(len(self.sale_items))
        total_amount = 0
        
        for row, item in enumerate(self.sale_items):
            self.items_table.setItem(row, 0, NumericTableWidgetItem(item["product_id"]))
            self.items_table.setItem(row, 1, QTableWidgetItem(item["product_name"]))
            self.items_table.setItem(row, 2, NumericTableWidgetItem(item["quantity"]))
            self.items_table.setItem(row, 3, PriceTableWidgetItem(item["sell_price"], format_price))
            
            # Calculate and display total for this item
            item_total = round(item["quantity"] * item["sell_price"])
            total_amount += item_total
            self.items_table.setItem(row, 4, PriceTableWidgetItem(item_total, format_price))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(lambda _, i=row: self.remove_item(i))
            remove_button.setMaximumWidth(60)
            actions_layout.addWidget(remove_button)

            self.items_table.setCellWidget(row, 5, actions_widget)

        self.total_amount_label.setText(f"Total: {format_price(total_amount)}")

    def handle_barcode_scan(self):
        """Handle barcode scan event."""
        barcode = self.barcode_input.text().strip()
        if not barcode:
            return

        try:
            product = self.product_service.get_product_by_barcode(barcode)
            if product:
                dialog = SaleItemDialog(product, self)
                if dialog.exec():
                    self.add_item(dialog.get_item_data())
                self.barcode_input.clear()
            else:
                self.barcode_input.setStyleSheet("background-color: #ffebee;")
                QTimer.singleShot(1000, lambda: self.barcode_input.setStyleSheet(""))
                show_error_message("Error", f"No product found with barcode: {barcode}")
        except Exception as e:
            logger.error(f"Error processing barcode: {str(e)}")
            show_error_message("Error", str(e))

    def search_products(self):
        """Search for products manually."""
        search_term = self.search_input.text().strip()
        if not search_term:
            return

        try:
            products = self.product_service.search_products(search_term)
            if products:
                if len(products) == 1:
                    dialog = SaleItemDialog(products[0], self)
                    if dialog.exec():
                        self.add_item(dialog.get_item_data())
                else:
                    product = self.show_product_selection_dialog(products)
                    if product:
                        dialog = SaleItemDialog(product, self)
                        if dialog.exec():
                            self.add_item(dialog.get_item_data())
            else:
                show_error_message("Not Found", "No products found matching the search term")
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            show_error_message("Error", str(e))

    def add_item(self, item_data: Dict[str, Any]):
        """Add an item to the sale."""
        self.sale_items.append(item_data)
        self.update_items_table()

    def remove_item(self, row: int):
        """Remove an item from the sale."""
        if 0 <= row < len(self.sale_items):
            del self.sale_items[row]
            self.update_items_table()

    def show_product_selection_dialog(self, products: List[Product]) -> Optional[Product]:
        """Show dialog for selecting from multiple matching products."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Product")
        layout = QVBoxLayout(dialog)

        product_list = QComboBox()
        for product in products:
            display_text = f"{product.name}"
            if product.barcode:
                display_text += f" (Barcode: {product.barcode})"
            product_list.addItem(display_text, product)

        layout.addWidget(QLabel("Select a product:"))
        layout.addWidget(product_list)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return product_list.currentData()
        return None

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def accept(self):
        """Handle dialog acceptance and save changes."""
        if not self.sale_items:
            raise ValidationException("Please add at least one item to the sale")

        try:
            date = self.date_input.date().toString("yyyy-MM-dd")
            
            # Update the sale
            self.sale_service.update_sale(
                sale_id=self.sale.id,
                customer_id=self.selected_customer_id,
                date=date,
                items=self.sale_items
            )
            
            super().accept()
            
        except Exception as e:
            logger.error(f"Error updating sale: {str(e)}")
            raise


class SaleItemDialog(QDialog):
    def __init__(self, product: Product, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle("Add Item")
        self.setup_ui()
        self.setup_product_details(product)

    def setup_ui(self):
        layout = QFormLayout(self)
        
        # Product name label
        self.product_name_label = QLabel()
        layout.addRow("Product:", self.product_name_label)
        
        # Quantity input - Allow 3 decimal places
        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setMinimum(0.001)
        self.quantity_input.setMaximum(1000000.000)
        self.quantity_input.setDecimals(3)
        self.quantity_input.setValue(1.000)
        self.quantity_input.valueChanged.connect(self.update_total)
        layout.addRow("Quantity:", self.quantity_input)

        # Price input (pre-filled with product price) - Integer only
        self.price_input = QSpinBox()
        self.price_input.setMinimum(1)
        self.price_input.setMaximum(1000000000)
        self.price_input.setPrefix("$ ")
        self.price_input.valueChanged.connect(self.format_price_display)
        if self.product.sell_price:
            self.price_input.setValue(int(self.product.sell_price))
        layout.addRow("Unit Price:", self.price_input)

        # Total and profit preview
        self.total_label = QLabel("$ 0")
        layout.addRow("Total:", self.total_label)
        self.profit_label = QLabel("$ 0")
        layout.addRow("Profit:", self.profit_label)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

        # Initial calculations
        self.update_total()

        # Keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self.validate_and_accept)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, self.validate_and_accept)

    def format_price_display(self, value: int) -> None:
        """Format the price display with dots as thousand separators."""
        formatted = f"$ {value:,}".replace(",", ".")
        self.price_input.setSpecialValueText("")  # Prevents "$ 0" from showing when empty
        self.price_input.setPrefix("")  # Clear prefix temporarily
        self.price_input.setSuffix(f" ({formatted})")  # Show formatted value as suffix

    def update_total(self) -> None:
        """Calculate total and profit with proper rounding for Chilean Pesos."""
        try:
            quantity = self.quantity_input.value()
            unit_price = self.price_input.value()
            total = int(quantity * unit_price)
            
            # Calculate profit
            if self.product.cost_price is not None:
                profit = int(round(quantity * (unit_price - self.product.cost_price)))
                self.profit_label.setText(f"$ {profit:,}".replace(",", "."))
            else:
                profit = 0
            
            self.total_label.setText(format_price(total))
            self.profit_label.setText(format_price(profit))
        except Exception as e:
            logger.error(f"Error updating totals: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, show_dialog=True)
    def validate_and_accept(self):
        try:
            # Validate quantity (3 decimal places)
            quantity = round(self.quantity_input.value(), 3)
            if quantity <= 0:
                raise ValidationException("Quantity must be positive")
            
            # Validate price (integer)
            price = int(self.price_input.value())
            if price <= 0:
                raise ValidationException("Price must be positive")
            
            self.accept()
            
        except (ValueError, TypeError) as e:
            raise ValidationException(f"Invalid input: {str(e)}")

    def get_item_data(self) -> Dict[str, Any]:
        """Get the sale item data with proper types."""
        try:
            quantity = round(self.quantity_input.value(), 3)
            sell_price = int(self.price_input.value())
            
            # Calculate profit with proper rounding
            if self.product.cost_price is not None:
                cost_price = int(self.product.cost_price)
                profit = int(round(quantity * (sell_price - cost_price)))
            else:
                profit = 0

            return {
                "product_id": self.product.id,
                "product_name": self.product.name,
                "quantity": quantity,
                "sell_price": sell_price,
                "profit": profit
            }
        except (ValueError, TypeError) as e:
            logger.error(f"Error preparing item data: {str(e)}")
            raise ValidationException("Invalid item data")

    def setup_product_details(self, product: Product):
        """Set up product details in the form."""
        try:
            self.product = product
            self.product_name_label.setText(product.name)
            self.quantity_input.setValue(1)
            self.quantity_input.setFocus()
        except Exception as e:
            logger.error(f"Error setting up product details: {str(e)}")
            show_error_message("Error", f"Failed to set up product details: {str(e)}")


class SaleView(QWidget):
    sale_updated = Signal()

    def __init__(self):
        super().__init__()
        self.sale_service = SaleService()
        self.customer_service = CustomerService()
        self.product_service = ProductService()
        self.setup_ui()
        self.setup_scan_sound()
        event_system.sale_added.connect(self.load_sales)

    def setup_scan_sound(self) -> None:
        """Initialize the sound system."""
        self.scan_sound = SoundEffect("scan.wav")


    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Customer section
        customer_layout = QHBoxLayout()
        
        self.customer_id_input = QLineEdit()
        self.customer_id_input.setPlaceholderText("Enter Department number")
        self.customer_id_input.returnPressed.connect(self.select_customer)
        
        # Single label for all customer info
        self.customer_info_label = QLabel()
        self.customer_info_label.setStyleSheet("""
            QLabel {
                color: #666;
                padding: 5px;
                background-color: #f5f5f5;
                border-radius: 4px;
            }
        """)
        
        # Add input section to main customer layout
        customer_layout.addWidget(QLabel("Customer:"))
        customer_layout.addWidget(self.customer_id_input, stretch=1)  # Give input field more space
        customer_layout.addWidget(self.customer_info_label, stretch=2)  # Give info label even more space
        
        # Add select button
        select_button = QPushButton("Select")
        select_button.clicked.connect(self.select_customer)
        select_button.setFixedWidth(80)
        select_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        customer_layout.addWidget(select_button)
        
        layout.addLayout(customer_layout)

        # Barcode and search section
        barcode_layout = QHBoxLayout()
        
        # Barcode input
        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Scan barcode...")
        self.barcode_input.returnPressed.connect(self.handle_barcode_scan)
        self.barcode_input.textChanged.connect(self.handle_barcode_input)
        
        # Manual search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search products...")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_products)
        
        barcode_layout.addWidget(QLabel("Barcode:"))
        barcode_layout.addWidget(self.barcode_input)
        barcode_layout.addWidget(QLabel("Manual Search:"))
        barcode_layout.addWidget(self.search_input)
        barcode_layout.addWidget(search_button)
        layout.addLayout(barcode_layout)

        # Date selection
        date_layout = QHBoxLayout()
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        self.date_input.setMinimumWidth(120)
        date_layout.addWidget(QLabel("Date:"))
        date_layout.addWidget(self.date_input)
        date_layout.addStretch()
        layout.addLayout(date_layout)

        # Sale items table
        self.sale_items_table = create_table(
            ["Product ID", "Product Name", "Quantity", "Unit Price", "Total", "Actions"]
        )
        self.sale_items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.sale_items_table)

        # Total amount display
        total_layout = QHBoxLayout()
        self.total_amount_label = QLabel("Total: $ 0")
        self.total_amount_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        total_layout.addStretch()
        total_layout.addWidget(self.total_amount_label)
        layout.addLayout(total_layout)

        # Action buttons
        button_layout = QHBoxLayout()
        complete_sale_button = QPushButton("Complete Sale")
        complete_sale_button.clicked.connect(self.complete_sale)
        complete_sale_button.setStyleSheet("background-color: #4CAF50; color: white;")
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.clear_sale)
        cancel_button.setStyleSheet("background-color: #f44336; color: white;")
        button_layout.addWidget(complete_sale_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        # Sales history table
        self.sale_table = create_table(
            ["ID", "Customer ID-9", "Department", "Customer Name", "Date", 
             "Total Amount", "Total Profit", "Receipt ID", "Actions"]
        )
        self.sale_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sale_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sale_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sale_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sale_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.sale_table)

        # Set up shortcuts
        self.setup_shortcuts()

        # Load initial data
        self.load_sales()
        self.sale_items = []
        
        # Focus barcode input
        self.barcode_input.setFocus()

    def setup_shortcuts(self):
        # Barcode field focus (Ctrl+B)
        barcode_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        barcode_shortcut.activated.connect(lambda: self.barcode_input.setFocus())
        
        # Clear sale (Esc)
        clear_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        clear_shortcut.activated.connect(self.clear_sale)
        
        # Complete sale (Ctrl+Enter)
        complete_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        complete_shortcut.activated.connect(self.complete_sale)
        
        # Refresh (F5)
        refresh_shortcut = QAction("Refresh", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_sales)
        self.addAction(refresh_shortcut)

    def handle_barcode_input(self, text: str):
        """Handle barcode input changes."""
        # If text is longer than typical barcode, clear it
        if len(text) > 14:  # EAN-14 is the longest common barcode
            self.barcode_input.clear()

    def handle_barcode_scan(self):
        """Handle barcode scan completion."""
        barcode = self.barcode_input.text().strip()
        if not barcode:
            return

        try:
            # Find product by barcode
            product = self.product_service.get_product_by_barcode(barcode)
            if product:
                self.scan_sound.play()
                
                # Show product dialog
                dialog = SaleItemDialog(product, self)
                if dialog.exec():
                    self.add_sale_item(dialog.get_item_data())
                
                # Clear and refocus barcode input
                self.barcode_input.clear()
                self.barcode_input.setFocus()
            else:
                # Visual feedback for error
                self.barcode_input.setStyleSheet("background-color: #ffebee;")
                QTimer.singleShot(1000, lambda: self.barcode_input.setStyleSheet(""))
                show_error_message("Error", f"No product found with barcode: {barcode}")
        except Exception as e:
            logger.error(f"Error processing barcode: {str(e)}")
            show_error_message("Error", f"Failed to process barcode: {str(e)}")
        finally:
            self.barcode_input.clear()

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def select_customer(self):
        """Handle customer selection."""
        identifier = self.customer_id_input.text().strip()
        if not identifier:
            show_error_message("Error", "Please enter a customer identifier")
            return

        try:
            customer = None
            if len(identifier) == 9:
                # Try 9-digit identifier first
                customer = self.customer_service.get_customer_by_identifier_9(identifier)
            elif len(identifier) in (3, 4):
                # Try 3/4-digit identifier
                customers = self.customer_service.get_customers_by_identifier_3or4(identifier)
                
                # Add logging to check for duplicates
                logger.debug(f"Found {len(customers)} customers for identifier {identifier}")
                for c in customers:
                    logger.debug(f"Customer found: ID={c.id}, identifier_9={c.identifier_9}, identifier_3or4={c.identifier_3or4}")
                
                # Remove duplicates based on identifier_9 (phone number)
                unique_customers = []
                seen_phones = set()
                for c in customers:
                    if c.identifier_9 not in seen_phones:
                        unique_customers.append(c)
                        seen_phones.add(c.identifier_9)
                    else:
                        logger.warning(f"Duplicate customer found with phone {c.identifier_9} for department {identifier}")
                
                if len(unique_customers) == 1:
                    customer = unique_customers[0]
                elif len(unique_customers) > 1:
                    customer = self.show_customer_selection_dialog(unique_customers)
                
            else:
                show_error_message("Error", "Please enter a 3/4-digit or 9-digit identifier")
                return

            if customer:
                self.selected_customer_id = customer.id
                # Format customer info in the requested format: "3/4 digits id - Name - 9 digits id"
                display_parts = []
                if customer.identifier_3or4:
                    display_parts.append(customer.identifier_3or4)
                if customer.name:
                    display_parts.append(customer.name)
                display_parts.append(customer.identifier_9)
                
                customer_info = " - ".join(display_parts)
                self.customer_info_label.setText(customer_info)
                self.customer_id_input.clear()  # Clear the input field
                self.barcode_input.setFocus()  # Move focus to barcode input
            else:
                show_error_message("Error", "No customer found with the given identifier")
                self.customer_info_label.clear()

        except Exception as e:
            logger.error(f"Error selecting customer: {str(e)}")
            show_error_message("Error", str(e))

    def show_customer_selection_dialog(self, customers: List[Customer]) -> Optional[Customer]:
        """Show dialog for selecting from multiple matching customers."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Customer")
        layout = QVBoxLayout(dialog)

        customer_list = QComboBox()
        for customer in customers:
            # Format display text with all available information
            display_parts = []
            if customer.identifier_3or4:
                display_parts.append(f"Dept: {customer.identifier_3or4}")
            if customer.name:
                display_parts.append(f"Name: {customer.name}")
            display_parts.append(f"Phone: {customer.identifier_9}")
            display_text = " | ".join(display_parts)
            customer_list.addItem(display_text, customer)

        layout.addWidget(QLabel("Multiple customers found. Please select one:"))
        layout.addWidget(customer_list)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return customer_list.currentData()
        return None

    def add_sale_item(self, item_data: Dict[str, Any]):
        """Add an item to the sale."""
        self.sale_items.append(item_data)
        self.update_sale_items_table()

    def remove_sale_item(self, row: int):
        """Remove an item from the sale."""
        if 0 <= row < len(self.sale_items):
            del self.sale_items[row]
            self.update_sale_items_table()

    def update_sale_items_table(self):
        """Update the sale items table display."""
        self.sale_items_table.setRowCount(len(self.sale_items))
        for row, item in enumerate(self.sale_items):
            # Create display for the row
            self.create_item_display(item, row)
        self.update_totals_display()

    def create_item_display(self, item: Dict[str, Any], row: int):
        """Create display widgets for a sale item row with proper formatting."""
        # Product ID and Name (unchanged)
        self.sale_items_table.setItem(row, 0, NumericTableWidgetItem(item["product_id"]))
        self.sale_items_table.setItem(row, 1, QTableWidgetItem(item["product_name"]))
        
        # Quantity with 3 decimal places
        quantity_item = NumericTableWidgetItem(round(item["quantity"], 3))
        quantity_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.sale_items_table.setItem(row, 2, quantity_item)
        
        # Unit price as integer with thousands separator
        price_item = PriceTableWidgetItem(item["sell_price"], format_price)
        self.sale_items_table.setItem(row, 3, price_item)
        
        # Total as integer with thousands separator
        total = int(round(item["quantity"] * item["sell_price"]))
        total_item = PriceTableWidgetItem(total, format_price)
        self.sale_items_table.setItem(row, 4, total_item)

        # Actions
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda _, i=row: self.remove_sale_item(i))
        remove_button.setMaximumWidth(60)
        actions_layout.addWidget(remove_button)

        self.sale_items_table.setCellWidget(row, 5, actions_widget)

    def update_totals_display(self):
        """Update the total amount display with proper Chilean Peso formatting."""
        total_amount = 0
        for item in self.sale_items:
            # Calculate total with proper rounding
            item_total = int(round(item["quantity"] * item["sell_price"]))
            total_amount += item_total
        
        # Format with thousands separator
        formatted_total = f"Total: {format_price(total_amount)}"
        self.total_amount_label.setText(formatted_total)

    def search_products(self):
        """Search for products manually."""
        search_term = self.search_input.text().strip()
        if not search_term:
            return

        try:
            products = self.product_service.search_products(search_term)
            if not products:
                show_error_message("Not Found", "No products found matching the search term")
                return

            # If only one product found, show it directly
            if len(products) == 1:
                dialog = SaleItemDialog(products[0], self)
                if dialog.exec():
                    self.add_sale_item(dialog.get_item_data())
                return

            # If multiple products, show selection dialog
            product = self.show_product_selection_dialog(products)
            if product:
                dialog = SaleItemDialog(product, self)
                if dialog.exec():
                    self.add_sale_item(dialog.get_item_data())

        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            show_error_message("Error", str(e))

    def show_product_selection_dialog(self, products: List[Product]) -> Optional[Product]:
        """Show dialog for selecting from multiple matching products."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Product")
        layout = QVBoxLayout(dialog)

        product_list = QComboBox()
        for product in products:
            display_text = f"{product.name}"
            if product.barcode:
                display_text += f" (Barcode: {product.barcode})"
            product_list.addItem(display_text, product)

        layout.addWidget(QLabel("Select a product:"))
        layout.addWidget(product_list)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return product_list.currentData()
        return None

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def complete_sale(self):
        """Complete the current sale with proper money handling."""
        if not hasattr(self, "selected_customer_id"):
            raise ValidationException("Please select a customer first")

        if not self.sale_items:
            raise ValidationException("Please add at least one item to the sale")

        try:
            date = validate_date(self.date_input.date().toString("yyyy-MM-dd"))
            
            # Process items to ensure proper types
            processed_items = []
            for item in self.sale_items:
                processed_item = {
                    "product_id": int(item["product_id"]),
                    "product_name": str(item["product_name"]),
                    "quantity": round(float(item["quantity"]), 3),  # 3 decimal places
                    "sell_price": int(item["sell_price"]),  # Integer Chilean Pesos
                    "profit": int(item["profit"])  # Integer Chilean Pesos
                }
                processed_items.append(processed_item)

            sale_id = self.sale_service.create_sale(
                self.selected_customer_id,
                date,
                processed_items
            )

            if sale_id:
                self.load_sales()
                self.clear_sale()
                show_info_message("Success", "Sale completed successfully")
                
            else:
                raise DatabaseException("Failed to create sale")
                
        except Exception as e:
            logger.error(f"Error completing sale: {str(e)}")
            raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_sales(self, sale_id=None):
        """Load all sales."""
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            sales = self.sale_service.get_all_sales()
            QTimer.singleShot(0, lambda: self.update_sale_table(sales))
            logger.info(f"Loaded {len(sales)} sales")
        except Exception as e:
            logger.error(f"Error loading sales: {str(e)}")
            raise DatabaseException(f"Failed to load sales: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def update_sale_table(self, sales: List[Sale]):
        """Update the sales history table with proper formatting."""
        self.sale_table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            customer = self.customer_service.get_customer(sale.customer_id)
            
            # Basic sale information
            self.sale_table.setItem(row, 0, NumericTableWidgetItem(sale.id))
            
            # Customer information
            if customer:
                self.sale_table.setItem(row, 1, QTableWidgetItem(customer.identifier_9))
                self.sale_table.setItem(row, 2, QTableWidgetItem(customer.identifier_3or4 or "N/A"))
                self.sale_table.setItem(row, 3, QTableWidgetItem(customer.name or ""))
            else:
                self.sale_table.setItem(row, 1, QTableWidgetItem("Unknown"))
                self.sale_table.setItem(row, 2, QTableWidgetItem("N/A"))
                self.sale_table.setItem(row, 3, QTableWidgetItem(""))
            
            # Date
            date_item = QTableWidgetItem(sale.date.strftime("%Y-%m-%d"))
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sale_table.setItem(row, 4, date_item)
            
            # Money values with proper formatting
            self.sale_table.setItem(row, 5, PriceTableWidgetItem(sale.total_amount, format_price))
            self.sale_table.setItem(row, 6, PriceTableWidgetItem(sale.total_profit, format_price))
            
            # Receipt ID
            receipt_item = QTableWidgetItem(sale.receipt_id or "")
            receipt_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sale_table.setItem(row, 7, receipt_item)

            # Actions
            self.create_sale_actions(row, sale)

    def create_sale_actions(self, row: int, sale: Sale) -> None:
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        view_button = QPushButton("View")
        view_button.clicked.connect(lambda: self._safe_view_sale(sale))
        view_button.setToolTip("View sale details")
        view_button.setMaximumWidth(60)

        edit_button = QPushButton("Edit")
        edit_button.clicked.connect(lambda: self._safe_edit_sale(sale))
        edit_button.setToolTip("Edit sale")
        edit_button.setMaximumWidth(60)

        print_button = QPushButton("Print")
        print_button.clicked.connect(lambda: self._safe_print_receipt(sale))
        print_button.setToolTip("Print receipt")
        print_button.setMaximumWidth(60)

        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(lambda: self._safe_delete_sale(sale))
        delete_button.setToolTip("Delete this sale")
        delete_button.setMaximumWidth(60)
        
        if (sale.date is not None and 
            datetime.now() - sale.date > timedelta(hours=1240)):
            edit_button.setEnabled(False)
            edit_button.setToolTip("Sales can only be edited within 1240 hours")
            delete_button.setEnabled(False)
            delete_button.setToolTip("Sales can only be deleted within 1240 hours")

        for btn in [view_button, edit_button, print_button, delete_button]:
            actions_layout.addWidget(btn)

        self.sale_table.setCellWidget(row, 8, actions_widget)

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def edit_sale(self, sale: Sale) -> None:
        """Edit an existing sale."""
        if sale is None:
            raise ValidationException("No sale selected for editing")

        if datetime.now() - sale.date > timedelta(hours=1240):
            raise ValidationException("Sales can only be edited within 1240 hours of creation")

        try:
            dialog = EditSaleDialog(
                sale=sale,
                sale_service=self.sale_service,
                customer_service=self.customer_service,
                product_service=self.product_service,
                parent=self
            )
            
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.load_sales()
                show_info_message("Success", "Sale updated successfully")
                
        except Exception as e:
            logger.error(f"Error editing sale: {str(e)}")
            raise

    def _safe_edit_sale(self, sale: Optional[Sale]) -> None:
        """Safely handle edit sale action with null check."""
        if sale is None:
            show_error_message("Error", "No sale selected")
            return
        self.edit_sale(sale)

    def _safe_view_sale(self, sale: Optional[Sale]) -> None:
        """Safely handle view sale action with null check."""
        if sale is None:
            show_error_message("Error", "No sale selected")
            return
        self.view_sale(sale)

    def _safe_print_receipt(self, sale: Optional[Sale]) -> None:
        """Safely handle print receipt action with null check."""
        if sale is None:
            show_error_message("Error", "No sale selected")
            return
        self.print_receipt(sale)

    def _safe_delete_sale(self, sale: Optional[Sale]) -> None:
        """Safely handle delete sale action with null check."""
        if sale is None:
            show_error_message("Error", "No sale selected")
            return
        self.delete_sale(sale)

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def delete_sale(self, sale: Optional[Sale]) -> None:
        """Delete a sale with validation."""
        if sale is None:
            raise ValidationException("No sale selected for deletion")

        if not confirm_action(
            self,
            "Delete Sale",
            f"Are you sure you want to delete sale {sale.receipt_id or sale.id}?\n"
            f"Total amount: {format_price(sale.total_amount)}"
        ):
            return

        try:
            self.sale_service.delete_sale(sale.id)
            self.load_sales()
            show_info_message("Success", "Sale deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting sale: {str(e)}")
            raise

    def clear_sale(self):
        """Clear current sale data."""
        self.sale_items = []
        self.update_sale_items_table()
        self.customer_id_input.clear()
        self.customer_info_label.clear()
        if hasattr(self, 'selected_customer_id'):
            del self.selected_customer_id
        self.barcode_input.clear()
        self.barcode_input.setFocus()
        self.search_input.clear()
        self.total_amount_label.setText("Total: $ 0")

    def show_context_menu(self, position: QPoint) -> None:
        menu = QMenu()
        view_action = menu.addAction("View")
        edit_action = menu.addAction("Edit")
        print_action = menu.addAction("Print")
        delete_action = menu.addAction("Delete")

        row = self.sale_table.rowAt(position.y())
        if row >= 0:
            sale_id = int(self.sale_table.item(row, 0).text())
            try:
                sale = self.sale_service.get_sale(sale_id)
                if sale is None:
                    show_error_message("Error", "Sale not found")
                    return
                
                # Disable edit/delete actions for old sales
                if sale.date and datetime.now() - sale.date > timedelta(hours=1240):
                    edit_action.setEnabled(False)
                    delete_action.setEnabled(False)
                
                action = menu.exec(self.sale_table.mapToGlobal(position))
                if action:
                    if action == view_action:
                        self._safe_view_sale(sale)
                    elif action == edit_action and action.isEnabled():
                        self._safe_edit_sale(sale)
                    elif action == print_action:
                        self._safe_print_receipt(sale)
                    elif action == delete_action and action.isEnabled():
                        self._safe_delete_sale(sale)
                        
            except Exception as e:
                show_error_message("Error", str(e))

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def print_receipt(self, sale: Sale) -> None:
        """Print a sale receipt with proper money formatting."""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Receipt",
                f"receipt_{sale.id}.pdf",
                "PDF Files (*.pdf)"
            )
            
            if file_path:
                self.sale_service.save_receipt_as_pdf(sale.id, file_path)
                show_info_message("Success", f"Receipt saved to {file_path}")
                
                # Optional: preview receipt
                preview = self.generate_receipt_preview(sale)
                show_info_message("Receipt Preview", preview)
                
        except Exception as e:
            logger.error(f"Error printing receipt: {str(e)}")
            show_error_message("Error", f"Failed to print receipt: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def view_sale(self, sale: Sale) -> None:
        """View sale details with proper money formatting."""
        try:
            items = self.sale_service.get_sale_items(sale.id)
            customer = self.customer_service.get_customer(sale.customer_id)
            
            receipt_id = sale.receipt_id or self.sale_service.generate_receipt(sale.id)

            # Format customer display
            if customer:
                customer_text = customer.identifier_9
                if customer.identifier_3or4:
                    customer_text += f" ({customer.identifier_3or4})"
                if customer.name:
                    customer_text += f" - {customer.name}"
            else:
                customer_text = "Unknown Customer"

            message = f"<pre>"
            message += f"{'Recibo #' + receipt_id:^64}\n\n"
            message += f"{' Detalles de venta ':=^64}\n\n"
            message += f"Cliente: {customer_text}\n"
            message += f"Fecha: {sale.date.strftime('%d-%m-%Y')}\n"
            message += f"{'':=^64}\n\n"
            message += f"{'Producto':<30}{'Cantidad':>10}{'P.Unit.':>12}{'Total':>12}\n"
            message += f"{'':-^64}\n"
            
            for item in items:
                product = self.product_service.get_product(item.product_id)
                product_name = product.name if product else "Unknown Product"
                message += (
                    f"{product_name[:30]:<30}"
                    f"{item.quantity:>10.3f}"
                    f"{format_price(item.unit_price):>12}"
                    f"{format_price(item.total_price()):>12}\n"
                )
            
            message += f"{'':-^64}\n"
            message += f"{'Total:':<45}{format_price(sale.total_amount):>19}\n"
            message += "</pre>"

            show_info_message("Sale Details", message)

            # Offer to print receipt
            reply = QMessageBox.question(
                self,
                "Print Receipt",
                "Would you like to print this receipt?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.print_receipt(sale)

        except Exception as e:
            logger.error(f"Error viewing sale: {str(e)}")
            raise UIException(f"Failed to view sale: {str(e)}")

    def generate_receipt_preview(self, sale: Sale) -> str:
        """Generate a text preview of the receipt with proper formatting."""
        try:
            customer = self.customer_service.get_customer(sale.customer_id)
            items = self.sale_service.get_sale_items(sale.id)
            
            receipt = []
            receipt.append(f"{'Recibo #' + str(sale.receipt_id or sale.id):^64}")
            receipt.append("\n")
            
            # Customer info
            if customer:
                customer_text = f"{customer.identifier_9}"
                if customer.identifier_3or4:
                    customer_text += f" ({customer.identifier_3or4})"
                if customer.name:
                    customer_text += f" - {customer.name}"
            else:
                customer_text = "Cliente no identificado"
            receipt.append(f"Cliente: {customer_text}")
            
            # Date
            if sale.date:
                receipt.append(f"Fecha: {sale.date.strftime('%d-%m-%Y')}")
            receipt.append("=" * 64)
            
            # Headers
            headers = "{:<30}{:>10}{:>12}{:>12}".format(
                "Producto", "Cantidad", "P.Unit.", "Total")
            receipt.append(headers)
            receipt.append("-" * 64)
            
            # Items with proper formatting
            for item in items:
                name = item.product_name if item.product_name else "Unknown Product"
                line = "{:<30}{:>10.3f}{:>12}{:>12}".format(
                    name[:30],
                    item.quantity,
                    format_price(item.unit_price),
                    format_price(item.total_price())
                )
                receipt.append(line)
            
            # Totals
            receipt.append("-" * 64)
            receipt.append("{:<52}{:>12}".format(
                "Total:",
                format_price(sale.total_amount)
            ))
            
            return "\n".join(receipt)
        except Exception as e:
            logger.error(f"Error generating receipt preview: {str(e)}")
            return "Error generating receipt preview"

    def refresh(self):
        """Refresh the sales view."""
        self.load_sales()
        self.barcode_input.setFocus()

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_F5:
            self.refresh()
        elif event.key() == Qt.Key.Key_Delete:
            selected_rows = self.sale_table.selectionModel().selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                sale_id = int(self.sale_table.item(row, 0).text())
                try:
                    sale = self.sale_service.get_sale(sale_id)
                    if sale:
                        self.delete_sale(sale)
                except Exception as e:
                    show_error_message("Error", str(e))
        elif event.key() == Qt.Key.Key_Escape:
            self.clear_sale()
        else:
            super().keyPressEvent(event)
