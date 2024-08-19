from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidgetItem, QMessageBox, QDoubleSpinBox, QDialog, QDialogButtonBox, 
    QComboBox, QFormLayout, QHeaderView, QAbstractItemView, QProgressBar, 
    QMenu, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence
from services.product_service import ProductService
from services.category_service import CategoryService
from utils.helpers import create_table, show_info_message, show_error_message, format_price
from utils.system.event_system import event_system
from ui.category_management_dialog import CategoryManagementDialog
from utils.ui.table_items import NumericTableWidgetItem, PercentageTableWidgetItem, PriceTableWidgetItem
from typing import Optional, List
from models.product import Product
from models.category import Category
from utils.decorators import ui_operation, handle_exceptions
from utils.validation.validators import validate_string, validate_float, validate_integer
from utils.exceptions import ValidationException, DatabaseException, UIException
from utils.system.logger import logger

class EditProductDialog(QDialog):
    def __init__(self, product: Optional[Product], categories: List[Category], parent=None):
        super().__init__(parent)
        self.product = product
        self.categories = categories
        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.name_input = QLineEdit(self.product.name if self.product else "")
        self.description_input = QLineEdit(self.product.description or "" if self.product else "")

        self.category_combo = QComboBox()
        self.category_combo.addItem("Uncategorized", None)
        for category in self.categories:
            self.category_combo.addItem(category.name, category.id)
        if self.product and self.product.category:
            index = self.category_combo.findData(self.product.category.id)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)

        self.cost_price_input = QDoubleSpinBox()
        self.cost_price_input.setMaximum(1000000000)
        self.cost_price_input.setValue(self.product.cost_price or 0 if self.product else 0)

        self.sell_price_input = QDoubleSpinBox()
        self.sell_price_input.setMaximum(1000000000)
        self.sell_price_input.setValue(self.product.sell_price or 0 if self.product else 0)

        layout.addRow("Name:", self.name_input)
        layout.addRow("Description:", self.description_input)
        layout.addRow("Category:", self.category_combo)
        layout.addRow("Cost Price:", self.cost_price_input)
        layout.addRow("Sell Price:", self.sell_price_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, show_dialog=True)
    def validate_and_accept(self):
        try:
            name = validate_string(self.name_input.text().strip(), min_length=1, max_length=100)
            description = validate_string(self.description_input.text().strip(), min_length=0, max_length=500)
            category_id = self.category_combo.currentData()
            cost_price = validate_float(self.cost_price_input.value(), min_value=0)
            sell_price = validate_float(self.sell_price_input.value(), min_value=0)

            self.product_data = {
                "name": name,
                "description": description,
                "category_id": category_id,
                "cost_price": cost_price,
                "sell_price": sell_price,
            }
            self.accept()
        except ValidationException as e:
            raise ValidationException(str(e))

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
        self.product_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.product_table.setSortingEnabled(True)
        self.product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
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
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def on_category_changed(self, index):
        try:
            self.current_category_id = self.category_filter.itemData(index)
            self.filter_products()
        except Exception as e:
            logger.error(f"Error changing category: {str(e)}")
            raise UIException(f"Failed to change category: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_categories(self):
        try:
            categories = self.category_service.get_all_categories()
            self.category_filter.clear()
            self.category_filter.addItem("All Categories", None)
            for category in categories:
                self.category_filter.addItem(category.name, category.id)
            logger.info("Categories loaded successfully")
        except Exception as e:
            logger.error(f"Error loading categories: {str(e)}")
            raise DatabaseException(f"Failed to load categories: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_products(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            products = self.product_service.get_all_products()
            QTimer.singleShot(0, lambda: self.filter_products(products))
            logger.info("Products loaded successfully")
        except Exception as e:
            logger.error(f"Error loading products: {str(e)}")
            raise DatabaseException(f"Failed to load products: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def update_product_table(self, products: List[Product]):
        try:
            self.product_table.setRowCount(len(products))
            for row, product in enumerate(products):
                profit_margin = self.product_service.get_product_profit_margin(product.id)
                self.product_table.setItem(row, 0, NumericTableWidgetItem(product.id))
                self.product_table.setItem(row, 1, QTableWidgetItem(product.name))
                self.product_table.setItem(row, 2, QTableWidgetItem(product.description or ""))
                self.product_table.setItem(row, 3, QTableWidgetItem(product.category.name if product.category else ""))
                self.product_table.setItem(row, 4, PriceTableWidgetItem(product.cost_price, format_price))
                self.product_table.setItem(row, 5, PriceTableWidgetItem(product.sell_price, format_price))
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
            self.product_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
            logger.info("Product table updated successfully")
        except Exception as e:
            logger.error(f"Error updating product table: {str(e)}")
            raise UIException(f"Failed to update product table: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def add_product(self):
        categories = self.category_service.get_all_categories()
        dialog = EditProductDialog(None, categories, self)
        if dialog.exec():
            product_data = dialog.product_data
            try:
                product_id = self.product_service.create_product(**product_data)
                if product_id is not None:
                    self.load_products()
                    show_info_message("Success", "Product added successfully.")
                    event_system.product_added.emit(product_id)
                    self.product_updated.emit()
                    logger.info(f"Product added successfully: ID {product_id}")
                else:
                    raise DatabaseException("Failed to add product.")
            except Exception as e:
                logger.error(f"Error adding product: {str(e)}")
                raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def edit_product(self, product: Optional[Product] = None):
        if product is None:
            selected_rows = self.product_table.selectionModel().selectedRows()
            if not selected_rows:
                raise ValidationException("No product selected for editing.")
            row = selected_rows[0].row()
            product_id = int(self.product_table.item(row, 0).text())
            product = self.product_service.get_product(product_id)

        if product:
            categories = self.category_service.get_all_categories()
            dialog = EditProductDialog(product, categories, self)
            if dialog.exec():
                product_data = dialog.product_data
                try:
                    self.product_service.update_product(product.id, product_data)
                    self.load_products()
                    show_info_message("Success", "Product updated successfully.")
                    event_system.product_updated.emit(product.id)
                    self.product_updated.emit()
                    logger.info(f"Product updated successfully: ID {product.id}")
                except Exception as e:
                    logger.error(f"Error updating product: {str(e)}")
                    raise
        else:
            raise ValidationException(f"Product with ID {product_id} not found.")

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def delete_product(self, product: Product):
        reply = QMessageBox.question(
            self,
            "Delete Product",
            f"Are you sure you want to delete product {product.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.product_service.delete_product(product.id)
                self.load_products()
                show_info_message("Success", "Product deleted successfully.")
                event_system.product_deleted.emit(product.id)
                self.product_updated.emit()
                logger.info(f"Product deleted successfully: ID {product.id}")
            except Exception as e:
                logger.error(f"Error deleting product: {str(e)}")
                raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def search_products(self):
        search_term = self.search_input.text().strip()
        search_term = validate_string(search_term, max_length=100)
        self.filter_products(search_term=search_term)

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def filter_products(self, products: Optional[List[Product]] = None, search_term: Optional[str] = None):
        if products is None:
            products = self.product_service.get_all_products() or []

        if search_term is None:
            search_term = self.search_input.text().strip()

        search_term = search_term.lower()

        filtered_products = [
            p for p in products
            if (not search_term or search_term in p.name.lower() or (p.description and search_term in p.description.lower()))
            and (self.current_category_id is None or (p.category and p.category.id == self.current_category_id))
        ]

        self.update_product_table(filtered_products)
        logger.info(f"Products filtered: {len(filtered_products)} results")

    def refresh(self):
        self.load_products()

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def manage_categories(self):
        dialog = CategoryManagementDialog(self)
        if dialog.exec():
            self.load_categories()
            self.load_products()
            logger.info("Categories managed successfully")

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
        show_info_message("Info", "Export functionality not implemented yet.")
        logger.info("Export products functionality not implemented")

    @ui_operation(show_dialog=True)
    def import_products(self):
        # TODO: Implement import functionality
        show_info_message("Info", "Import functionality not implemented yet.")
        logger.info("Import products functionality not implemented")

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
