import os
from typing import Any, List, Optional

from PySide6.QtCore import QDate, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.purchase import Purchase
from services.product_service import ProductService
from services.purchase_service import PurchaseService
from utils.decorators import handle_exceptions, ui_operation
from utils.exceptions import DatabaseException, UIException, ValidationException
from utils.helpers import (
    create_table,
    format_price,
    show_error_message,
    show_info_message,
)
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.ui.table_items import NumericTableWidgetItem, PriceTableWidgetItem
from utils.validation.validators import validate_float, validate_string


class PurchaseItemDialog(QDialog):
    def __init__(self, product, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(f"Add {product.name}")
        self.setup_ui()

        # Focus quantity input by default
        self.quantity_input.setFocus()
        self.quantity_input.selectAll()

    def setup_ui(self):
        layout = QFormLayout(self)

        # Product info
        product_info = QLabel(f"{self.product.name}")
        if self.product.barcode:
            product_info.setToolTip(f"Barcode: {self.product.barcode}")
        layout.addRow("Product:", product_info)

        # Quantity input
        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setMinimum(0.001)
        self.quantity_input.setMaximum(1000000.000)
        self.quantity_input.setDecimals(3)
        self.quantity_input.setValue(1.00)
        self.quantity_input.valueChanged.connect(self.update_total)
        layout.addRow("Quantity:", self.quantity_input)

        # Cost price input
        self.cost_price_input = QDoubleSpinBox()
        self.cost_price_input.setMinimum(1)
        self.cost_price_input.setMaximum(1000000)
        self.cost_price_input.setDecimals(0)
        if self.product.cost_price:
            self.cost_price_input.setValue(self.product.cost_price)
        self.cost_price_input.valueChanged.connect(self.update_total)
        layout.addRow("Cost Price:", self.cost_price_input)

        # Total preview
        self.total_label = QLabel("0")
        layout.addRow("Total:", self.total_label)

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

    def update_total(self):
        quantity = self.quantity_input.value()
        price = self.cost_price_input.value()
        total = round(quantity * price)
        self.total_label.setText(format_price(total))

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, show_dialog=True)
    def validate_and_accept(self):
        try:
            validate_float(self.quantity_input.value(), min_value=0.001)
            validate_float(self.cost_price_input.value(), min_value=1)
            self.accept()
        except ValidationException as e:
            raise ValidationException(str(e))

    def get_item_data(self):
        return {
            "product_id": self.product.id,
            "product_name": self.product.name,
            "quantity": self.quantity_input.value(),
            "cost_price": round(self.cost_price_input.value()),
        }


class PurchaseView(QWidget):
    purchase_updated = Signal()

    def __init__(self):
        super().__init__()
        self.purchase_service = PurchaseService()
        self.product_service = ProductService()
        self.setup_ui()
        self.setup_scan_sound()

    def setup_scan_sound(self):
        self.scan_sound = QSoundEffect()
        sound_file = os.path.join(os.path.dirname(__file__), "resources", "scan.wav")
        self.scan_sound.setSource(QUrl.fromLocalFile(sound_file))
        self.scan_sound.setVolume(0.5)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Input fields
        input_layout = QHBoxLayout()
        self.supplier_input = QLineEdit()
        self.supplier_input.setPlaceholderText("Enter supplier name")

        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)

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

        input_layout.addWidget(QLabel("Supplier:"))
        input_layout.addWidget(self.supplier_input)
        input_layout.addWidget(QLabel("Date:"))
        input_layout.addWidget(self.date_input)

        layout.addLayout(input_layout)
        layout.addLayout(barcode_layout)

        # Purchase items table
        self.purchase_items_table = create_table(
            ["Product ID", "Product Name", "Quantity", "Cost Price", "Total", "Actions"]
        )
        self.purchase_items_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.purchase_items_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self.purchase_items_table)

        # Total amount display
        total_layout = QHBoxLayout()
        self.total_amount_label = QLabel("Total: $0")
        self.total_amount_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        total_layout.addStretch()
        total_layout.addWidget(self.total_amount_label)
        layout.addLayout(total_layout)

        # Action buttons
        button_layout = QHBoxLayout()
        complete_button = QPushButton("Complete Purchase")
        complete_button.clicked.connect(self.complete_purchase)
        complete_button.setStyleSheet("background-color: #4CAF50; color: white;")
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.clear_purchase)
        cancel_button.setStyleSheet("background-color: #f44336; color: white;")
        button_layout.addWidget(complete_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        # Purchase history table
        self.purchase_table = create_table(
            ["ID", "Supplier", "Date", "Total Amount", "Actions"]
        )
        self.purchase_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.purchase_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.purchase_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.purchase_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.purchase_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.purchase_table)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Set up shortcuts
        self.setup_shortcuts()

        # Load initial data
        self.load_purchases()
        self.purchase_items = []

        # Focus barcode input
        self.barcode_input.setFocus()

    def setup_shortcuts(self):
        # Barcode field focus (Ctrl+B)
        barcode_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        barcode_shortcut.activated.connect(lambda: self.barcode_input.setFocus())

        # Clear purchase (Esc)
        clear_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        clear_shortcut.activated.connect(self.clear_purchase)

        # Complete purchase (Ctrl+Enter)
        complete_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        complete_shortcut.activated.connect(self.complete_purchase)

        # Refresh (F5)
        refresh_shortcut = QAction("Refresh", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_purchases)
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
            product = self.find_product_by_barcode(barcode)
            if product:
                # Play success sound
                self.scan_sound.play()

                # Show product dialog
                dialog = PurchaseItemDialog(product, self)
                if dialog.exec():
                    self.add_purchase_item(dialog.get_item_data())

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

    def find_product_by_barcode(self, barcode: str) -> Optional[Any]:
        """Find a product by its barcode."""
        products = self.product_service.get_all_products()
        return next((p for p in products if p.barcode == barcode), None)

    def update_purchase_items_table(self):
        """Update the purchase items table."""
        self.purchase_items_table.setRowCount(len(self.purchase_items))
        total_amount = 0

        for row, item in enumerate(self.purchase_items):
            self.purchase_items_table.setItem(
                row, 0, NumericTableWidgetItem(item["product_id"])
            )
            self.purchase_items_table.setItem(
                row, 1, QTableWidgetItem(item["product_name"])
            )
            self.purchase_items_table.setItem(
                row, 2, NumericTableWidgetItem(item["quantity"])
            )
            self.purchase_items_table.setItem(
                row, 3, PriceTableWidgetItem(item["cost_price"], format_price)
            )

            item_total = round(item["quantity"] * item["cost_price"])
            total_amount += item_total
            self.purchase_items_table.setItem(
                row, 4, PriceTableWidgetItem(item_total, format_price)
            )

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(lambda _, i=row: self.remove_purchase_item(i))
            remove_button.setMaximumWidth(60)
            actions_layout.addWidget(remove_button)

            self.purchase_items_table.setCellWidget(row, 5, actions_widget)

        self.total_amount_label.setText(f"Total: {format_price(total_amount)}")

    def add_purchase_item(self, item_data: dict):
        """Add an item to the purchase."""
        self.purchase_items.append(item_data)
        self.update_purchase_items_table()

    def remove_purchase_item(self, row: int):
        """Remove an item from the purchase."""
        if 0 <= row < len(self.purchase_items):
            del self.purchase_items[row]
            self.update_purchase_items_table()

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def complete_purchase(self):
        """Complete the current purchase."""
        supplier = validate_string(
            self.supplier_input.text().strip(), min_length=1, max_length=100
        )
        if not supplier:
            raise ValidationException("Please enter a supplier name")

        if not self.purchase_items:
            raise ValidationException("Please add at least one item to the purchase")

        try:
            date_str = self.date_input.date().toString("yyyy-MM-dd")
            purchase_id = self.purchase_service.create_purchase(
                supplier, date_str, self.purchase_items
            )

            if purchase_id:
                self.load_purchases()
                self.clear_purchase()
                show_info_message("Success", "Purchase completed successfully")
                event_system.purchase_added.emit(purchase_id)
                self.purchase_updated.emit()
            else:
                raise DatabaseException("Failed to create purchase")

        except Exception as e:
            logger.error(f"Error completing purchase: {str(e)}")
            raise

    def update_purchase_table(self, purchases: List[Purchase]):
        """Update the purchases history table."""
        self.purchase_table.setRowCount(len(purchases))
        for row, purchase in enumerate(purchases):
            self.purchase_table.setItem(row, 0, NumericTableWidgetItem(purchase.id))
            self.purchase_table.setItem(row, 1, QTableWidgetItem(purchase.supplier))
            self.purchase_table.setItem(
                row, 2, QTableWidgetItem(purchase.date.strftime("%Y-%m-%d"))
            )
            self.purchase_table.setItem(
                row, 3, PriceTableWidgetItem(purchase.total_amount, format_price)
            )

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            view_button = QPushButton("View")
            view_button.clicked.connect(lambda _, p=purchase: self.view_purchase(p))
            view_button.setToolTip("View purchase details")

            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, p=purchase: self.delete_purchase(p))
            delete_button.setToolTip("Delete this purchase")

            for btn in [view_button, delete_button]:
                btn.setMaximumWidth(60)
                actions_layout.addWidget(btn)

            self.purchase_table.setCellWidget(row, 4, actions_widget)

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_purchases(self):
        """Load all purchases."""
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            purchases = self.purchase_service.get_all_purchases()
            QTimer.singleShot(0, lambda: self.update_purchase_table(purchases))
            logger.info(f"Loaded {len(purchases)} purchases")
        except Exception as e:
            logger.error(f"Error loading purchases: {str(e)}")
            raise DatabaseException(f"Failed to load purchases: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    def search_products(self):
        """Search for products manually."""
        search_term = self.search_input.text().strip()
        if not search_term:
            return

        try:
            products = self.product_service.search_products(search_term)
            if not products:
                show_error_message(
                    "Not Found", "No products found matching the search term"
                )
                return

            # If only one product found, show it directly
            if len(products) == 1:
                dialog = PurchaseItemDialog(products[0], self)
                if dialog.exec():
                    self.add_purchase_item(dialog.get_item_data())
                return

            # If multiple products, show selection dialog
            product = self.show_product_selection_dialog(products)
            if product:
                dialog = PurchaseItemDialog(product, self)
                if dialog.exec():
                    self.add_purchase_item(dialog.get_item_data())

        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            show_error_message("Error", str(e))

    def show_product_selection_dialog(self, products: List[Any]) -> Optional[Any]:
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

    def show_context_menu(self, position):
        """Show context menu for purchases table."""
        menu = QMenu()
        view_action = menu.addAction("View")
        delete_action = menu.addAction("Delete")

        action = menu.exec(self.purchase_table.mapToGlobal(position))
        if action:
            row = self.purchase_table.rowAt(position.y())
            purchase_id = int(self.purchase_table.item(row, 0).text())
            purchase = self.purchase_service.get_purchase(purchase_id)

            if purchase is not None:
                if action == view_action:
                    self.view_purchase(purchase)
                elif action == delete_action:
                    self.delete_purchase(purchase)
            else:
                show_error_message("Error", f"Purchase with ID {purchase_id} not found")

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def view_purchase(self, purchase: Purchase):
        """View purchase details."""
        try:
            items = self.purchase_service.get_purchase_items(purchase.id)

            message = "<pre>"
            message += f"{' Purchase Details ':=^64}\n\n"
            message += f"Supplier: {purchase.supplier}\n"
            message += f"Date: {purchase.date.strftime('%d-%m-%Y')}\n"
            message += f"{'':=^64}\n\n"
            message += (
                f"{'Product':<30}{'Quantity':>10}{'Unit Cost':>12}{'Total':>12}\n"
            )
            message += f"{'':-^64}\n"

            for item in items:
                product = self.product_service.get_product(item.product_id)
                product_name = product.name if product else "Unknown Product"
                total = item.quantity * item.price
                message += f"{product_name[:30]:<30}{item.quantity:>10.2f}{format_price(item.price):>12}{format_price(total):>12}\n"

            message += f"{'':-^64}\n"
            message += f"{'Total:':<45}{format_price(purchase.total_amount):>19}\n"
            message += "</pre>"

            show_info_message("Purchase Details", message)

        except Exception as e:
            logger.error(f"Error viewing purchase: {str(e)}")
            raise UIException(f"Failed to view purchase: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def delete_purchase(self, purchase: Purchase):
        """Delete a purchase."""
        reply = QMessageBox.question(
            self,
            "Delete Purchase",
            "Are you sure you want to delete this purchase? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.purchase_service.delete_purchase(purchase.id)
                self.load_purchases()
                show_info_message("Success", "Purchase deleted successfully")
                event_system.purchase_deleted.emit(purchase.id)
                self.purchase_updated.emit()
            except Exception as e:
                logger.error(f"Error deleting purchase: {str(e)}")
                raise

    def clear_purchase(self):
        """Clear current purchase data."""
        self.supplier_input.clear()
        self.date_input.setDate(QDate.currentDate())
        self.purchase_items = []
        self.update_purchase_items_table()
        self.barcode_input.clear()
        self.barcode_input.setFocus()
        self.search_input.clear()
        self.total_amount_label.setText("Total: $0")

    def refresh(self):
        """Refresh the purchases view."""
        self.load_purchases()
        self.barcode_input.setFocus()

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_F5:
            self.refresh()
        elif event.key() == Qt.Key.Key_Delete:
            selected_rows = self.purchase_table.selectionModel().selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                purchase_id = int(self.purchase_table.item(row, 0).text())
                purchase = self.purchase_service.get_purchase(purchase_id)
                if purchase:
                    self.delete_purchase(purchase)
        elif event.key() == Qt.Key.Key_Escape:
            self.clear_purchase()
        else:
            super().keyPressEvent(event)
