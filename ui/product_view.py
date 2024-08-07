from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QMessageBox,
    QSpinBox,
    QDialog,
    QDialogButtonBox,
    QComboBox,
    QFormLayout,
    QHeaderView,
    QAbstractItemView,
    QProgressBar,
    QMenu,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence
from services.product_service import ProductService
from services.category_service import CategoryService
from utils.helpers import (
    create_table,
    show_info_message,
    show_error_message,
    format_price,
)
from utils.system.event_system import event_system
from ui.category_management_dialog import CategoryManagementDialog
from utils.ui.table_items import (
    NumericTableWidgetItem,
    PercentageTableWidgetItem,
    PriceTableWidgetItem,
)
from typing import Optional, List
from models.product import Product
from models.category import Category
from utils.decorators import ui_operation, validate_input


class EditProductDialog(QDialog):
    def __init__(
        self, product: Optional[Product], categories: List[Category], parent=None
    ):
        super().__init__(parent)
        self.product = product
        self.categories = categories
        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.name_input = QLineEdit(self.product.name if self.product else "")
        self.description_input = QLineEdit(
            self.product.description or "" if self.product else ""
        )

        self.category_combo = QComboBox()
        self.category_combo.addItem("Uncategorized", None)
        for category in self.categories:
            self.category_combo.addItem(category.name, category.id)
        if self.product and self.product.category:
            index = self.category_combo.findData(self.product.category.id)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)

        self.cost_price_input = QSpinBox()
        self.cost_price_input.setMaximum(1000000000)
        self.cost_price_input.setValue(
            self.product.cost_price or 0 if self.product else 0
        )

        self.sell_price_input = QSpinBox()
        self.sell_price_input.setMaximum(1000000000)
        self.sell_price_input.setValue(
            self.product.sell_price or 0 if self.product else 0
        )

        layout.addRow("Name:", self.name_input)
        layout.addRow("Description:", self.description_input)
        layout.addRow("Category:", self.category_combo)
        layout.addRow("Cost Price:", self.cost_price_input)
        layout.addRow("Sell Price:", self.sell_price_input)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    @validate_input(show_dialog=True)
    def validate_and_accept(self):
        name = self.name_input.text().strip()
        description = self.description_input.text().strip()
        category_id = self.category_combo.currentData()
        cost_price = self.cost_price_input.value()
        sell_price = self.sell_price_input.value()

        if not name:
            raise ValueError("Product name cannot be empty.")
        if len(name) > 100:
            raise ValueError("Product name cannot exceed 100 characters.")
        if description and len(description) > 500:
            raise ValueError("Product description cannot exceed 500 characters.")
        if cost_price < 0 or sell_price < 0:
            raise ValueError("Prices cannot be negative.")

        self.product_data = {
            "name": name,
            "description": description,
            "category_id": category_id,
            "cost_price": cost_price,
            "sell_price": sell_price,
        }
        self.accept()


class ProductView(QWidget):
    product_updated = Signal()

    def __init__(self):
        super().__init__()
        self.product_service = ProductService()
        self.category_service = CategoryService()
        self.current_category_id = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search products...")
        self.search_input.returnPressed.connect(self.search_products)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_products)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Category filter
        filter_layout = QHBoxLayout()
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", None)
        self.load_categories()
        self.category_filter.currentIndexChanged.connect(self.on_category_changed)
        filter_layout.addWidget(QLabel("Filter by Category:"))
        filter_layout.addWidget(self.category_filter)
        layout.addLayout(filter_layout)

        # Product table
        self.product_table = create_table(
            [
                "ID",
                "Name",
                "Description",
                "Category",
                "Cost Price",
                "Sell Price",
                "Profit Margin",
                "Actions",
            ]
        )
        self.product_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self.product_table.setSortingEnabled(True)
        self.product_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.product_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.product_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.product_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.product_table)

        # Buttons
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add Product")
        add_button.clicked.connect(self.add_product)
        add_button.setToolTip("Add a new product (Ctrl+N)")
        manage_categories_button = QPushButton("Manage Categories")
        manage_categories_button.clicked.connect(self.manage_categories)
        button_layout.addWidget(add_button)
        button_layout.addWidget(manage_categories_button)
        layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.load_products()

        # Set up shortcuts
        self.setup_shortcuts()

        # Connect to event system
        event_system.product_added.connect(self.load_products)
        event_system.product_updated.connect(self.load_products)
        event_system.product_deleted.connect(self.load_products)

    def setup_shortcuts(self):
        add_shortcut = QAction("Add Product", self)
        add_shortcut.setShortcut(QKeySequence("Ctrl+N"))
        add_shortcut.triggered.connect(self.add_product)
        self.addAction(add_shortcut)

        refresh_shortcut = QAction("Refresh", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_products)
        self.addAction(refresh_shortcut)

    @ui_operation(show_dialog=True)
    def on_category_changed(self, index):
        self.current_category_id = self.category_filter.itemData(index)
        self.filter_products()

    @ui_operation(show_dialog=True)
    def load_categories(self):
        categories = self.category_service.get_all_categories()
        self.category_filter.clear()
        self.category_filter.addItem("All Categories", None)
        for category in categories:
            self.category_filter.addItem(category.name, category.id)

    @ui_operation(show_dialog=True)
    def load_products(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            products = self.product_service.get_all_products()
            QTimer.singleShot(0, lambda: self.filter_products(products))
        finally:
            QApplication.restoreOverrideCursor()
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    @ui_operation(show_dialog=True)
    def update_product_table(self, products: List[Product]):
        self.product_table.setRowCount(len(products))
        for row, product in enumerate(products):
            profit_margin = self.product_service.get_product_profit_margin(product.id)
            self.product_table.setItem(row, 0, NumericTableWidgetItem(product.id))
            self.product_table.setItem(row, 1, QTableWidgetItem(product.name))
            self.product_table.setItem(
                row, 2, QTableWidgetItem(product.description or "")
            )
            self.product_table.setItem(
                row,
                3,
                QTableWidgetItem(product.category.name if product.category else ""),
            )
            self.product_table.setItem(
                row, 4, PriceTableWidgetItem(product.cost_price, format_price)
            )
            self.product_table.setItem(
                row, 5, PriceTableWidgetItem(product.sell_price, format_price)
            )
            self.product_table.setItem(row, 6, PercentageTableWidgetItem(profit_margin))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            edit_button = QPushButton("Edit")
            edit_button.setFixedWidth(80)
            edit_button.clicked.connect(lambda _, p=product: self.edit_product(p))
            edit_button.setToolTip("Edit this product")

            delete_button = QPushButton("Delete")
            delete_button.setFixedWidth(80)
            delete_button.clicked.connect(lambda _, p=product: self.delete_product(p))
            delete_button.setToolTip("Delete this product")

            actions_layout.addWidget(edit_button)
            actions_layout.addWidget(delete_button)
            self.product_table.setCellWidget(row, 7, actions_widget)

        self.product_table.resizeColumnsToContents()
        self.product_table.horizontalHeader().setSectionResizeMode(
            7, QHeaderView.ResizeMode.Stretch
        )

    @ui_operation(show_dialog=True)
    def add_product(self):
        categories = self.category_service.get_all_categories()
        dialog = EditProductDialog(None, categories, self)
        if dialog.exec():
            product_data = dialog.product_data
            product_id = self.product_service.create_product(**product_data)
            if product_id is not None:
                self.load_products()
                show_info_message("Success", "Product added successfully.")
                event_system.product_added.emit(product_id)
                self.product_updated.emit()
            else:
                show_error_message("Error", "Failed to add product.")

    @ui_operation(show_dialog=True)
    def edit_product(self, product: Product):
        categories = self.category_service.get_all_categories()
        dialog = EditProductDialog(product, categories, self)
        if dialog.exec():
            product_data = dialog.product_data
            self.product_service.update_product(product.id, **product_data)
            self.load_products()
            show_info_message("Success", "Product updated successfully.")
            event_system.product_updated.emit(product.id)
            self.product_updated.emit()

    @ui_operation(show_dialog=True)
    def delete_product(self, product: Product):
        reply = QMessageBox.question(
            self,
            "Delete Product",
            f"Are you sure you want to delete product {product.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.product_service.delete_product(product.id)
            self.load_products()
            show_info_message("Success", "Product deleted successfully.")
            event_system.product_deleted.emit(product.id)
            self.product_updated.emit()

    @ui_operation(show_dialog=True)
    def search_products(self):
        search_term = self.search_input.text().strip()
        self.filter_products(search_term=search_term)

    @ui_operation(show_dialog=True)
    def filter_products(
        self,
        products: Optional[List[Product]] = None,
        search_term: Optional[str] = None,
    ):
        if products is None:
            products = self.product_service.get_all_products() or []

        if search_term is None:
            search_term = self.search_input.text().strip()

        search_term = search_term.lower()

        filtered_products = [
            p
            for p in products
            if (
                not search_term
                or search_term in p.name.lower()
                or (p.description and search_term in p.description.lower())
            )
            and (
                self.current_category_id is None
                or (p.category and p.category.id == self.current_category_id)
            )
        ]

        self.update_product_table(filtered_products)

    def refresh(self):
        self.load_products()

    @ui_operation(show_dialog=True)
    def manage_categories(self):
        dialog = CategoryManagementDialog(self)
        if dialog.exec():
            self.load_categories()
            self.load_products()

    def show_context_menu(self, position):
        menu = QMenu()
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")

        action = menu.exec(self.product_table.mapToGlobal(position))
        if action:
            row = self.product_table.rowAt(position.y())
            product_id = int(self.product_table.item(row, 0).text())
            product = self.product_service.get_product(product_id)

            if product is not None:
                if action == edit_action:
                    self.edit_product(product)
                elif action == delete_action:
                    self.delete_product(product)
            else:
                show_error_message("Error", f"Product with ID {product_id} not found.")

    @ui_operation(show_dialog=True)
    def export_products(self):
        # TODO: Implement export functionality
        # TODO: This is a placeholder for future implementation
        show_info_message("Info", "Export functionality not implemented yet.")

    @ui_operation(show_dialog=True)
    def import_products(self):
        # TODO: Implement import functionality
        # TODO: This is a placeholder for future implementation
        show_info_message("Info", "Import functionality not implemented yet.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_rows = self.product_table.selectionModel().selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                product_id = int(self.product_table.item(row, 0).text())
                product = self.product_service.get_product(product_id)
                if product:
                    self.delete_product(product)
        else:
            super().keyPressEvent(event)
