from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidgetItem,
    QMessageBox, QHeaderView, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QDoubleSpinBox, QProgressBar
    )
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QColor
from services.purchase_service import PurchaseService
from services.product_service import ProductService
from models.purchase import Purchase
from utils.utils import create_table, show_error_message, show_info_message
from utils.logger import logger
from utils.event_system import event_system
from typing import List

class PurchaseItemDialog(QDialog):
    def __init__(self, products, parent=None):
        super().__init__(parent)
        self.products = products
        self.setWindowTitle("Add Purchase Item")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.product_combo = QComboBox()
        for product in self.products:
            self.product_combo.addItem(product.name, product.id)
        layout.addRow("Product:", self.product_combo)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setMinimum(0.01)
        self.quantity_input.setMaximum(1000000.00)
        self.quantity_input.setDecimals(2)
        layout.addRow("Quantity:", self.quantity_input)

        self.price_input = QDoubleSpinBox()
        self.price_input.setMinimum(0.01)
        self.price_input.setMaximum(1000000.00)
        self.price_input.setDecimals(2)
        layout.addRow("Price:", self.price_input)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def validate_and_accept(self):
        if self.quantity_input.value() <= 0:
            show_error_message("Invalid Quantity", "Quantity must be greater than 0.")
            return
        if self.price_input.value() <= 0:
            show_error_message("Invalid Price", "Price must be greater than 0.")
            return
        self.accept()

    def get_item_data(self):
        return {
            "product_id": self.product_combo.currentData(),
            "product_name": self.product_combo.currentText(),
            "quantity": self.quantity_input.value(),
            "price": self.price_input.value()
        }

class PurchaseView(QWidget):
    def __init__(self):
        super().__init__()
        self.purchase_service = PurchaseService()
        self.product_service = ProductService()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search purchases...")
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_purchases)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Input fields
        input_layout = QHBoxLayout()
        self.supplier_input = QLineEdit()
        self.supplier_input.setPlaceholderText("Enter supplier name")
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        input_layout.addWidget(QLabel("Supplier:"))
        input_layout.addWidget(self.supplier_input)
        input_layout.addWidget(QLabel("Date:"))
        input_layout.addWidget(self.date_input)
        
        add_button = QPushButton("Add Purchase")
        add_button.clicked.connect(self.add_purchase)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Purchase table
        self.purchase_table = create_table(["ID", "Supplier", "Date", "Total Amount", "Actions"])
        self.purchase_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.purchase_table)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.load_purchases()

    def load_purchases(self):
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            purchases = self.purchase_service.get_all_purchases()
            self.update_purchase_table(purchases)
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
        except Exception as e:
            logger.error(f"Failed to load purchases: {str(e)}")
            show_error_message("Error", f"Failed to load purchases: {str(e)}")
            self.progress_bar.setVisible(False)

    def update_purchase_table(self, purchases: List[Purchase]):
        self.purchase_table.setRowCount(len(purchases))
        for row, purchase in enumerate(purchases):
            self.purchase_table.setItem(row, 0, QTableWidgetItem(str(purchase.id)))
            self.purchase_table.setItem(row, 1, QTableWidgetItem(purchase.supplier))
            self.purchase_table.setItem(row, 2, QTableWidgetItem(purchase.date.strftime("%Y-%m-%d")))
            self.purchase_table.setItem(row, 3, QTableWidgetItem(f"{purchase.total_amount:.2f}"))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            view_button = QPushButton("View")
            view_button.clicked.connect(lambda _, p=purchase: self.view_purchase(p))
            actions_layout.addWidget(view_button)
            
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, p=purchase: self.delete_purchase(p))
            actions_layout.addWidget(delete_button)
            
            self.purchase_table.setCellWidget(row, 4, actions_widget)

            # Alternate row colors
            if row % 2 == 0:
                for col in range(self.purchase_table.columnCount()):
                    self.purchase_table.item(row, col).setBackground(QColor(240, 240, 240))

    def add_purchase(self):
        supplier = self.supplier_input.text().strip()
        date = self.date_input.date().toString("yyyy-MM-dd")

        if not supplier:
            show_error_message("Error", "Supplier is required.")
            return

        try:
            products = self.product_service.get_all_products()
            items = []
            while True:
                dialog = PurchaseItemDialog(products, self)
                if dialog.exec():
                    items.append(dialog.get_item_data())
                    reply = QMessageBox.question(self, "Add Another Item", "Do you want to add another item?",
                                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                                 QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        break
                else:
                    break

            if items:
                purchase_id = self.purchase_service.create_purchase(supplier, date, items)
                if purchase_id is not None:
                    self.load_purchases()
                    self.supplier_input.clear()
                    show_info_message("Success", "Purchase added successfully.")
                    event_system.purchase_added.emit(purchase_id)
                else:
                    show_error_message("Error", "Failed to add purchase.")
            else:
                show_error_message("Error", "No items added to the purchase.")
        except Exception as e:
            logger.error(f"Error adding purchase: {str(e)}")
            show_error_message("Error", str(e))

    def view_purchase(self, purchase):
        try:
            items = self.purchase_service.get_purchase_items(purchase.id)
            message = f"Purchase Details:\n\nSupplier: {purchase.supplier}\nDate: {purchase.date.strftime('%Y-%m-%d')}\n\nItems:\n"
            for item in items:
                product = self.product_service.get_product(item.product_id)
                product_name = product.name if product else "Unknown Product"
                message += f"- {product_name}: {item.quantity:.2f} @ {item.price:.2f}\n"
            message += f"\nTotal Amount: {purchase.total_amount:.2f}"
            show_info_message("Purchase Details", message)
        except Exception as e:
            logger.error(f"Error viewing purchase details: {str(e)}")
            show_error_message("Error", f"Failed to view purchase details: {str(e)}")

    def delete_purchase(self, purchase):
        reply = QMessageBox.question(self, 'Delete Purchase', 
                                     f'Are you sure you want to delete this purchase from {purchase.supplier}?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.purchase_service.delete_purchase(purchase.id)
                self.load_purchases()
                show_info_message("Success", "Purchase deleted successfully.")
                event_system.purchase_deleted.emit(purchase.id)
            except Exception as e:
                logger.error(f"Error deleting purchase: {str(e)}")
                show_error_message("Error", str(e))

    def search_purchases(self):
        search_term = self.search_input.text().strip().lower()
        if search_term:
            purchases = self.purchase_service.get_all_purchases()
            filtered_purchases = [
                p for p in purchases
                if search_term in p.supplier.lower() or search_term in p.date.strftime("%Y-%m-%d").lower()
            ]
            self.update_purchase_table(filtered_purchases)
        else:
            self.load_purchases()