from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidgetItem,
    QMessageBox, QHeaderView, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QDoubleSpinBox, QProgressBar, QAbstractItemView, QMenu, QApplication)
from PySide6.QtCore import Qt, QDate, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence
from services.purchase_service import PurchaseService
from services.product_service import ProductService
from models.purchase import Purchase
from utils.helpers import create_table, show_info_message, show_error_message, format_price
from utils.system.event_system import event_system
from utils.ui.table_items import NumericTableWidgetItem, PriceTableWidgetItem
from typing import List, Optional
from utils.decorators import ui_operation, validate_input

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
        self.product_combo.currentIndexChanged.connect(self.update_price)
        layout.addRow("Product:", self.product_combo)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setMinimum(0.01)
        self.quantity_input.setMaximum(1000000.00)
        self.quantity_input.setDecimals(2)
        layout.addRow("Quantity:", self.quantity_input)

        self.cost_price_input = QDoubleSpinBox()
        self.cost_price_input.setMinimum(0.01)
        self.cost_price_input.setMaximum(1000000.00)
        self.cost_price_input.setDecimals(2)
        layout.addRow("Cost Price:", self.cost_price_input)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addRow(self.buttons)

    def update_price(self):
        product_id = self.product_combo.currentData()
        product = next((p for p in self.products if p.id == product_id), None)
        if product and product.cost_price is not None:
            self.cost_price_input.setValue(product.cost_price)
        else:
            self.cost_price_input.setValue(0.00)

    @validate_input(show_dialog=True)
    def validate_and_accept(self):
        if self.quantity_input.value() <= 0:
            raise ValueError("Quantity must be greater than 0.")
        if self.cost_price_input.value() <= 0:
            raise ValueError("Cost price must be greater than 0.")
        self.accept()

    def get_item_data(self):
        return {
            "product_id": self.product_combo.currentData(),
            "product_name": self.product_combo.currentText(),
            "quantity": self.quantity_input.value(),
            "cost_price": self.cost_price_input.value()
        }

class PurchaseView(QWidget):
    purchase_updated = Signal()

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
        self.search_input.returnPressed.connect(self.search_purchases)
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
        self.date_input.setFixedWidth(150)

        input_layout.addWidget(QLabel("Supplier:"))
        input_layout.addWidget(self.supplier_input)
        input_layout.addWidget(QLabel("Date:"))
        input_layout.addWidget(self.date_input)

        add_button = QPushButton("Add Purchase")
        add_button.clicked.connect(self.add_purchase)
        add_button.setToolTip("Add a new purchase (Ctrl+N)")
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Purchase table
        self.purchase_table = create_table(["ID", "Supplier", "Date", "Total Amount", "Actions"])
        self.purchase_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.purchase_table.setSortingEnabled(True)
        self.purchase_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.purchase_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.purchase_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.purchase_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.purchase_table)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.load_purchases()

        # Set up shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        add_shortcut = QAction("Add Purchase", self)
        add_shortcut.setShortcut(QKeySequence("Ctrl+N"))
        add_shortcut.triggered.connect(self.add_purchase)
        self.addAction(add_shortcut)

        refresh_shortcut = QAction("Refresh", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_purchases)
        self.addAction(refresh_shortcut)

    @ui_operation(show_dialog=True)
    def load_purchases(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            purchases = self.purchase_service.get_all_purchases()
            QTimer.singleShot(0, lambda: self.update_purchase_table(purchases))
        finally:
            QApplication.restoreOverrideCursor()
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    @ui_operation(show_dialog=True)
    def update_purchase_table(self, purchases: List[Purchase]):
        self.purchase_table.setRowCount(len(purchases))
        for row, purchase in enumerate(purchases):
            self.purchase_table.setItem(row, 0, NumericTableWidgetItem(purchase.id))
            self.purchase_table.setItem(row, 1, QTableWidgetItem(purchase.supplier))
            self.purchase_table.setItem(row, 2, QTableWidgetItem(purchase.date.strftime("%Y-%m-%d")))
            self.purchase_table.setItem(row, 3, PriceTableWidgetItem(purchase.total_amount, format_price))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            view_button = QPushButton("View")
            view_button.clicked.connect(lambda _, p=purchase: self.view_purchase(p))
            view_button.setToolTip("View purchase details")
            actions_layout.addWidget(view_button)

            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, p=purchase: self.delete_purchase(p))
            delete_button.setToolTip("Delete this purchase")
            actions_layout.addWidget(delete_button)

            self.purchase_table.setCellWidget(row, 4, actions_widget)

    @ui_operation(show_dialog=True)
    def add_purchase(self):
        supplier = self.supplier_input.text().strip()
        date = self.date_input.date().toString("yyyy-MM-dd")

        if not supplier:
            raise ValueError("Supplier is required.")

        products = self.product_service.get_all_products()
        items = []
        while True:
            dialog = PurchaseItemDialog(products, self)
            if dialog.exec():
                items.append(dialog.get_item_data())
                reply = QMessageBox.question(
                    self, "Add Another Item", "Do you want to add another item?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                    QMessageBox.StandardButton.No
                )
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
                self.purchase_updated.emit()
            else:
                raise ValueError("Failed to add purchase.")
        else:
            raise ValueError("No items added to the purchase.")

    @ui_operation(show_dialog=True)
    def view_purchase(self, purchase):
        items = self.purchase_service.get_purchase_items(purchase.id)
        message = f"Purchase Details:\n\nSupplier: {purchase.supplier}\nDate: {purchase.date.strftime('%Y-%m-%d')}\n\nItems:\n"
        for item in items:
            product = self.product_service.get_product(item.product_id)
            product_name = product.name if product else "Unknown Product"
            message += f"- {product_name}: {item.quantity:.2f} @ {format_price(item.price)}\n"
        message += f"\nTotal Amount: {format_price(purchase.total_amount)}"
        show_info_message("Purchase Details", message)

    @ui_operation(show_dialog=True)
    def delete_purchase(self, purchase):
        reply = QMessageBox.question(
            self, 'Delete Purchase', 
            f'Are you sure you want to delete this purchase from {purchase.supplier}?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.purchase_service.delete_purchase(purchase.id)
            self.load_purchases()
            show_info_message("Success", "Purchase deleted successfully.")
            event_system.purchase_deleted.emit(purchase.id)
            self.purchase_updated.emit()

    @ui_operation(show_dialog=True)
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

    def refresh(self):
        self.load_purchases()

    def show_context_menu(self, position):
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
                show_error_message("Error", f"Purchase with ID {purchase_id} not found.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_rows = self.purchase_table.selectionModel().selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                purchase_id = int(self.purchase_table.item(row, 0).text())
                purchase = self.purchase_service.get_purchase(purchase_id)
                if purchase:
                    self.delete_purchase(purchase)
        else:
            super().keyPressEvent(event)
