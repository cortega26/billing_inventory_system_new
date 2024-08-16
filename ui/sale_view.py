from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFormLayout, QDoubleSpinBox, QProgressBar, QHeaderView, QMenu, QApplication,
    QFileDialog
)
from PySide6.QtCore import Qt, QDate, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from services.sale_service import SaleService
from services.customer_service import CustomerService
from services.product_service import ProductService
from models.customer import Customer
from models.sale import Sale
from models.product import Product
from utils.helpers import (
    create_table, show_error_message, show_info_message, format_price, confirm_action
)
from utils.system.logger import logger
from utils.system.event_system import event_system
from utils.ui.table_items import NumericTableWidgetItem, PriceTableWidgetItem
from typing import List, Optional
from utils.decorators import ui_operation #, validate_input
from datetime import datetime, timedelta

class SaleItemDialog(QDialog):
    def __init__(self, products: List[Product], parent=None):
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
        self.quantity_input.setValue(1.00)
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

    #@validate_input(show_dialog=True)
    def validate_and_accept(self):
        if self.quantity_input.value() <= 0:
            raise ValueError("Quantity must be greater than 0.")
        if self.price_input.value() <= 0:
            raise ValueError("Price must be greater than 0.")
        self.accept()

    def get_item_data(self):
        product = self.product_combo.currentData()
        return {
            "product_id": product.id,
            "product_name": product.name,
            "quantity": self.quantity_input.value(),
            "sell_price": self.price_input.value(),
        }

class EditSaleDialog(QDialog):
    def __init__(self, sale: Sale, customers: List[Customer], products: List[Product], parent=None):
        super().__init__(parent)
        self.sale = sale
        self.customers = customers
        self.products = products
        self.setWindowTitle(f"Edit Sale {sale.id}")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        # Customer selection
        self.customer_combo = QComboBox()
        for customer in self.customers:
            self.customer_combo.addItem(f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})", customer.id)
        self.customer_combo.setCurrentIndex(self.customer_combo.findData(self.sale.customer_id))
        layout.addRow("Customer:", self.customer_combo)

        # Date selection
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate(self.sale.date.year, self.sale.date.month, self.sale.date.day))
        self.date_edit.setCalendarPopup(True)
        layout.addRow("Date:", self.date_edit)

        # Items table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels(["Product", "Quantity", "Price", "Total", ""])
        layout.addRow("Items:", self.items_table)

        # Add item button
        add_item_button = QPushButton("Add Item")
        add_item_button.clicked.connect(self.add_item)
        layout.addRow("", add_item_button)

        # Total amount
        self.total_label = QLabel()
        layout.addRow("Total:", self.total_label)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

        self.load_items()

    def load_items(self):
        for item in self.sale.items:
            self.add_item_row(item.product_id, item.quantity, item.unit_price)
        self.update_total()

    def add_item(self):
        dialog = SaleItemDialog(self.products, self)
        if dialog.exec():
            item_data = dialog.get_item_data()
            self.add_item_row(item_data['product_id'], item_data['quantity'], item_data['sell_price'])
            self.update_total()

    def add_item_row(self, product_id, quantity, price):
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)
        
        product = next((p for p in self.products if p.id == product_id), None)
        product_name = product.name if product else "Unknown Product"
        
        self.items_table.setItem(row, 0, QTableWidgetItem(product_name))
        self.items_table.setItem(row, 1, QTableWidgetItem(str(quantity)))
        self.items_table.setItem(row, 2, QTableWidgetItem(str(price)))
        self.items_table.setItem(row, 3, QTableWidgetItem(str(quantity * price)))
        
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(lambda: self.delete_item(row))
        self.items_table.setCellWidget(row, 4, delete_button)

    def delete_item(self, row):
        self.items_table.removeRow(row)
        self.update_total()

    def update_total(self):
        total = sum(float(self.items_table.item(row, 3).text()) for row in range(self.items_table.rowCount()))
        self.total_label.setText(f"${total:.2f}")

    def get_sale_data(self):
        return {
            'customer_id': self.customer_combo.currentData(),
            'date': self.date_edit.date().toString("yyyy-MM-dd"),
            'items': [
                {
                    'product_id': next(p.id for p in self.products if p.name == self.items_table.item(row, 0).text()),
                    'quantity': float(self.items_table.item(row, 1).text()),
                    'sell_price': float(self.items_table.item(row, 2).text())
                }
                for row in range(self.items_table.rowCount())
            ]
        }

class SaleView(QWidget):
    sale_updated = Signal()

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
        self.search_input.returnPressed.connect(self.search_sales)
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
        add_button.setToolTip("Add a new sale (Ctrl+N)")
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Sale table
        self.sale_table = create_table(
            ["ID", "Customer", "Date", "Total Amount", "Receipt ID", "Actions"]
        )
        self.sale_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sale_table.setSortingEnabled(True)
        self.sale_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sale_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sale_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.sale_table)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.load_sales()

        # Set up shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        add_shortcut = QAction("Add Sale", self)
        add_shortcut.setShortcut(QKeySequence("Ctrl+N"))
        add_shortcut.triggered.connect(self.add_sale)
        self.addAction(add_shortcut)

        refresh_shortcut = QAction("Refresh", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_sales)
        self.addAction(refresh_shortcut)

    @ui_operation(show_dialog=True)
    def load_sales(self):
        logger.debug("Loading sales")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            sales = self.sale_service.get_all_sales()
            QTimer.singleShot(0, lambda: self.update_sale_table(sales))
        finally:
            QApplication.restoreOverrideCursor()
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    @ui_operation(show_dialog=True)
    def update_sale_table(self, sales: List[Sale]):
        self.sale_table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            customer = self.customer_service.get_customer(sale.customer_id)

            self.sale_table.setItem(row, 0, NumericTableWidgetItem(sale.id))

            customer_text = f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})" if customer else "Unknown Customer"
            self.sale_table.setItem(row, 1, QTableWidgetItem(customer_text))

            self.sale_table.setItem(row, 2, QTableWidgetItem(sale.date.strftime("%Y-%m-%d")))
            self.sale_table.setItem(row, 3, PriceTableWidgetItem(sale.total_amount, format_price))
            self.sale_table.setItem(row, 4, QTableWidgetItem(sale.receipt_id or ""))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            view_button = QPushButton("View")
            view_button.clicked.connect(lambda _, s=sale: self.view_sale(s))
            view_button.setToolTip("View sale details")
            actions_layout.addWidget(view_button)

            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(lambda _, s=sale: self.edit_sale(s))
            edit_button.setToolTip("Edit this sale")
            actions_layout.addWidget(edit_button)

            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, s=sale: self.delete_sale(s))
            delete_button.setToolTip("Delete this sale")
            actions_layout.addWidget(delete_button)

            self.sale_table.setCellWidget(row, 5, actions_widget)

    @ui_operation(show_dialog=True)
    def edit_sale(self, sale: Sale):
        if datetime.now() - sale.date > timedelta(hours=48):
            show_error_message("Edit not allowed", "Sales can only be edited within 48 hours of creation.")
            return

        customers = self.customer_service.get_all_customers()
        products = self.product_service.get_all_products()
        dialog = EditSaleDialog(sale, customers, products, self)
        if dialog.exec():
            sale_data = dialog.get_sale_data()
            try:
                self.sale_service.update_sale(sale.id, **sale_data)
                self.load_sales()
                show_info_message("Success", "Sale updated successfully.")
                self.sale_updated.emit()
            except Exception as e:
                show_error_message("Error", str(e))

    @ui_operation(show_dialog=True)
    def view_sale(self, sale: Sale):
        items = self.sale_service.get_sale_items(sale.id)
        customer = self.customer_service.get_customer(sale.customer_id)
        customer_text = f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})" if customer else "Unknown Customer"

        receipt_id = sale.receipt_id or self.sale_service.generate_receipt(sale.id)

        message = f"<pre>"
        message += f"{'Receipt #' + receipt_id:^64}\n\n"
        message += f"{' Sale Details ':=^64}\n\n"
        message += f"Customer: {customer_text}\n"
        message += f"Date: {sale.date.strftime('%d-%m-%Y')}\n"
        message += f"{'':=^64}\n\n"
        message += f"{'Product':<30}{'Quantity':>10}{'P.Unitario':>12}{'Subtotal':>12}\n"
        message += f"{'':-^64}\n"
        for item in items:
            product = self.product_service.get_product(item.product_id)
            product_name = product.name if product else "Unknown Product"
            message += f"{product_name[:30]:<30}{item.quantity:>10.2f}{format_price(item.unit_price):>12}{format_price(item.total_price()):>12}\n"
        message += f"{'':-^64}\n"
        message += f"{'Total amount:':<45}{format_price(sale.total_amount):>19}\n"
        message += "</pre>"

        show_info_message("Sale Details", message)

        # Add options to save as PDF or send via WhatsApp
        reply = QMessageBox.question(self, "Receipt Options", 
                                     "Would you like to save the receipt as PDF or send via WhatsApp?",
                                     QMessageBox.StandardButton.SaveAll | QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.SaveAll:
            self.save_receipt_as_pdf(sale.id)
        elif reply == QMessageBox.StandardButton.Yes:
            self.send_receipt_via_whatsapp(sale.id)

    @ui_operation(show_dialog=True)
    def save_receipt_as_pdf(self, sale_id: int):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Receipt", "", "PDF Files (*.pdf)")
        if file_path:
            try:
                self.sale_service.save_receipt_as_pdf(sale_id, file_path)
                show_info_message("Success", f"Receipt saved as {file_path}")
            except Exception as e:
                show_error_message("Error", f"Failed to save receipt: {str(e)}")

    @ui_operation(show_dialog=True)
    def send_receipt_via_whatsapp(self, sale_id: int):
        sale = self.sale_service.get_sale(sale_id)
        if sale:
            customer = self.customer_service.get_customer(sale.customer_id)
            if customer:
                phone_number = f"+56{customer.identifier_9}"
                try:
                    self.sale_service.send_receipt_via_whatsapp(sale_id, phone_number)
                    show_info_message("Success", f"Receipt sent to WhatsApp number {phone_number}")
                except Exception as e:
                    show_error_message("Error", f"Failed to send receipt via WhatsApp: {str(e)}")
            else:
                show_error_message("Error", "Customer information not found")
        else:
            show_error_message("Error", f"Sale with ID {sale_id} not found")

    @ui_operation(show_dialog=True)
    def select_customer(self):
        identifier = self.customer_input.text().strip()
        logger.debug(f"Selecting customer with identifier: {identifier}")
        if len(identifier) == 9:
            customer = self.customer_service.get_customer_by_identifier_9(identifier)
        elif len(identifier) in (3, 4):
            customers = self.customer_service.get_customers_by_identifier_3or4(identifier)
            if len(customers) == 1:
                customer = customers[0]
            elif len(customers) > 1:
                # If multiple customers found, show a dialog to select one
                customer = self.show_customer_selection_dialog(customers)
            else:
                customer = None
        else:
            raise ValueError("Invalid identifier length")

        if customer:
            self.selected_customer_id = customer.id
            self.customer_input.setText(f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})")
        else:
            raise ValueError("No customer found with the given identifier.")

    def show_customer_selection_dialog(self, customers: List[Customer]) -> Optional[Customer]:
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Customer")
        layout = QVBoxLayout(dialog)

        customer_list = QComboBox()
        for customer in customers:
            customer_list.addItem(f"{customer.identifier_9} ({customer.identifier_3or4 or 'N/A'})", customer)

        layout.addWidget(QLabel("Select a customer:"))
        layout.addWidget(customer_list)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            return customer_list.currentData()
        return None

    @ui_operation(show_dialog=True)
    def add_sale(self):
        if not hasattr(self, "selected_customer_id"):
            raise ValueError("Please select a customer first.")

        date = self.date_input.date().toString("yyyy-MM-dd")

        products = self.product_service.get_all_products()
        items = []
        while True:
            dialog = SaleItemDialog(products, self)
            if dialog.exec():
                items.append(dialog.get_item_data())
                reply = QMessageBox.question(
                    self,
                    "Add Another Item",
                    "Do you want to add another item?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
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
                self.sale_updated.emit()
            else:
                raise ValueError("Failed to add sale.")
        else:
            raise ValueError("No items added to the sale.")

    @ui_operation(show_dialog=True)
    def delete_sale(self, sale: Sale):
        reply = QMessageBox.question(
            self,
            "Delete Sale",
            f"Are you sure you want to delete this sale?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.sale_service.delete_sale(sale.id)
            self.load_sales()
            show_info_message("Success", "Sale deleted successfully.")
            event_system.sale_deleted.emit(sale.id)
            self.sale_updated.emit()

    @ui_operation(show_dialog=True)
    def search_sales(self):
        search_term = self.search_input.text().strip().lower()
        if search_term:
            sales = self.sale_service.get_all_sales()
            filtered_sales = [
                s for s in sales
                if search_term in str(s.id).lower()
                or search_term in s.date.strftime("%Y-%m-%d").lower()
                or search_term in str(s.total_amount).lower()
                or (s.receipt_id and search_term in s.receipt_id.lower())
            ]
            self.update_sale_table(filtered_sales)
        else:
            self.load_sales()

    @ui_operation(show_dialog=True)
    def on_product_updated(self, product_id):
        self.load_sales()

    @ui_operation(show_dialog=True)
    def on_product_deleted(self, product_id):
        self.load_sales()

    def refresh(self):
        self.load_sales()

    def show_context_menu(self, position):
        menu = QMenu()
        view_action = menu.addAction("View")
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")

        action = menu.exec(self.sale_table.mapToGlobal(position))
        if action:
            row = self.sale_table.rowAt(position.y())
            sale_id = int(self.sale_table.item(row, 0).text())
            sale = self.sale_service.get_sale(sale_id)

            if sale is not None:
                if action == view_action:
                    self.view_sale(sale)
                elif action == edit_action:
                    self.edit_sale(sale)
                elif action == delete_action:
                    self.delete_sale(sale)
            else:
                show_error_message("Error", f"Sale with ID {sale_id} not found.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_rows = self.sale_table.selectionModel().selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                sale_id = int(self.sale_table.item(row, 0).text())
                sale = self.sale_service.get_sale(sale_id)
                if sale:
                    self.delete_sale(sale)
        else:
            super().keyPressEvent(event)