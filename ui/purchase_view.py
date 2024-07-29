from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidget, QTableWidgetItem, QMessageBox,
                               QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout)
from PySide6.QtCore import Qt, QDate
from models.purchase import Purchase
from services.purchase_service import PurchaseService
from services.product_service import ProductService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system
from typing import List, Dict, Any

class PurchaseItemDialog(QDialog):
    def __init__(self, products, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Purchase Item")
        self.products = products
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.product_combo = QComboBox()
        for product in self.products:
            self.product_combo.addItem(product.name, product.id)
        layout.addRow("Product:", self.product_combo)

        self.quantity_input = QLineEdit()
        layout.addRow("Quantity:", self.quantity_input)

        self.price_input = QLineEdit()
        layout.addRow("Price:", self.price_input)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def get_item_data(self):
        return {
            "product_id": self.product_combo.currentData(),
            "quantity": int(self.quantity_input.text()),
            "price": float(self.price_input.text())
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
        self.supplier_combo = QComboBox()
        self.supplier_combo.setEditable(True)
        self.date_input = QDateEdit()
        self.date_input.setDate(QDate.currentDate())
        self.date_input.setCalendarPopup(True)
        
        input_layout.addWidget(QLabel("Supplier:"))
        input_layout.addWidget(self.supplier_combo)
        input_layout.addWidget(QLabel("Date:"))
        input_layout.addWidget(self.date_input)
        
        add_button = QPushButton("Add Purchase")
        add_button.clicked.connect(self.add_purchase)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Purchase table
        self.purchase_table = create_table(["ID", "Supplier", "Date", "Total Amount", "Actions"])
        layout.addWidget(self.purchase_table)

        self.load_suppliers()
        self.load_purchases()

    def load_suppliers(self):
        try:
            suppliers = self.purchase_service.get_suppliers()
            self.supplier_combo.clear()
            self.supplier_combo.addItems(suppliers)
        except Exception as e:
            show_error_message("Error", f"Failed to load suppliers: {str(e)}")

    def load_purchases(self):
        try:
            purchases = self.purchase_service.get_all_purchases()
            self.update_purchase_table(purchases)
        except Exception as e:
            show_error_message("Error", f"Failed to load purchases: {str(e)}")

    def update_purchase_table(self, purchases: List[Purchase]):
        self.purchase_table.setRowCount(len(purchases))
        for row, purchase in enumerate(purchases):
            self.purchase_table.setItem(row, 0, QTableWidgetItem(str(purchase.id)))
            self.purchase_table.setItem(row, 1, QTableWidgetItem(purchase.supplier))
            self.purchase_table.setItem(row, 2, QTableWidgetItem(purchase.date.strftime("%Y-%m-%d")))
            self.purchase_table.setItem(row, 3, QTableWidgetItem(f"{purchase.total_amount:,.2f}"))

            
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

    def add_purchase(self):
        supplier = self.supplier_combo.currentText().strip()
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
                                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        break
                else:
                    break

            if items:
                purchase_id = self.purchase_service.create_purchase(supplier, date, items)
                if purchase_id is not None:
                    self.load_purchases()
                    self.load_suppliers()
                    QMessageBox.information(self, "Success", "Purchase added successfully.")
                else:
                    show_error_message("Error", "Failed to add purchase.")
            else:
                show_error_message("Error", "No items added to the purchase.")
        except Exception as e:
            show_error_message("Error", str(e))

    def view_purchase(self, purchase):
        items = self.purchase_service.get_purchase_items(purchase.id)
        message = f"Purchase Details:\n\nSupplier: {purchase.supplier}\nDate: {purchase.date.strftime('%Y-%m-%d')}\n\nItems:\n"
        for item in items:
            product = self.product_service.get_product(item.product_id)
            product_name = product.name if product else "Unknown Product"
            message += f"- {product_name}: {item.quantity} @ {item.price:.2f}\n"
        message += f"\nTotal Amount: {purchase.total_amount:.2f}"
        QMessageBox.information(self, "Purchase Details", message)

    def delete_purchase(self, purchase):
        reply = QMessageBox.question(self, 'Delete Purchase', 
                                     f'Are you sure you want to delete this purchase from {purchase.supplier}?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.purchase_service.delete_purchase(purchase.id)
                self.load_purchases()
                QMessageBox.information(self, "Success", "Purchase deleted successfully.")
            except Exception as e:
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