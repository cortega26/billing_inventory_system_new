from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidgetItem, QMessageBox,
                               QDialog, QDialogButtonBox, QComboBox, QFormLayout,
                               QTableWidget, QHeaderView, QAbstractItemView, QProgressBar)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from services.product_service import ProductService
from services.category_service import CategoryService
from utils.utils import create_table, show_error_message, show_info_message
from utils.event_system import event_system
from utils.logger import logger
from ui.category_management_dialog import CategoryManagementDialog
from typing import List, Optional, Dict, Any, Sequence
from models.product import Product
from models.category import Category  # Ensure we're using the correct Category class

class EditProductDialog(QDialog):
    def __init__(self, product: Optional[Dict[str, Any]], categories: Sequence[Category], parent=None):
        super().__init__(parent)
        self.product = product
        self.categories = categories
        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit(self.product['name'] if self.product else "")
        layout.addRow("Name:", self.name_input)
        
        self.description_input = QLineEdit(self.product['description'] if self.product and self.product['description'] else "")
        layout.addRow("Description:", self.description_input)
        
        self.category_combo = QComboBox()
        self.category_combo.addItem("Uncategorized", None)
        for category in self.categories:
            self.category_combo.addItem(category.name, category.id)
        if self.product and self.product.get('category_id'):
            index = self.category_combo.findData(self.product['category_id'])
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
        layout.addRow("Category:", self.category_combo)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    def validate_and_accept(self):
        name = self.name_input.text().strip()
        description = self.description_input.text().strip()
        category_id = self.category_combo.currentData()

        if not name:
            show_error_message("Validation Error", "Product name cannot be empty.")
            return
        if len(name) > 100:
            show_error_message("Validation Error", "Product name cannot exceed 100 characters.")
            return
        if description and len(description) > 500:
            show_error_message("Validation Error", "Product description cannot exceed 500 characters.")
            return

        self.product = self.product or {}
        self.product['name'] = name
        self.product['description'] = description
        self.product['category_id'] = category_id
        self.accept()

class ProductView(QWidget):
    def __init__(self):
        super().__init__()
        self.product_service = ProductService()
        self.category_service = CategoryService()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search products...")
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
        self.category_filter.currentIndexChanged.connect(self.filter_products)
        filter_layout.addWidget(QLabel("Filter by Category:"))
        filter_layout.addWidget(self.category_filter)
        layout.addLayout(filter_layout)

        # Product table
        self.product_table = create_table(["ID", "Name", "Description", "Category", "Avg. Purchase Price", "Actions"])
        self.product_table.setSortingEnabled(True)
        self.product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.product_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.product_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.product_table)

        # Buttons
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add Product")
        add_button.clicked.connect(self.add_product)
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

        # Connect to event system
        event_system.product_added.connect(self.load_products)
        event_system.product_updated.connect(self.load_products)
        event_system.product_deleted.connect(self.load_products)

    def load_categories(self):
        try:
            categories = self.category_service.get_all_categories()
            self.category_filter.clear()
            self.category_filter.addItem("All Categories", None)
            for category in categories:
                self.category_filter.addItem(category.name, category.id)
        except Exception as e:
            logger.error(f"Failed to load categories: {str(e)}")
            show_error_message("Error", f"Failed to load categories: {str(e)}")

    def load_products(self):
        logger.debug("Loading products")
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            products = self.product_service.get_all_products()
            self.update_product_table(products)
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))
        except Exception as e:
            logger.error(f"Failed to load products: {str(e)}")
            show_error_message("Error", f"Failed to load products: {str(e)}")
            self.progress_bar.setVisible(False)

    def update_product_table(self, products: List[Product]):
        self.product_table.setRowCount(len(products))
        for row, product in enumerate(products):
            logger.debug(f"Loading product: {product}")
            try:
                avg_price = self.product_service.get_average_purchase_price(product.id)
                self.product_table.setItem(row, 0, QTableWidgetItem(str(product.id)))
                self.product_table.setItem(row, 1, QTableWidgetItem(product.name))
                self.product_table.setItem(row, 2, QTableWidgetItem(product.description or ""))
                self.product_table.setItem(row, 3, QTableWidgetItem(product.category.name if product.category else ""))
                self.product_table.setItem(row, 4, QTableWidgetItem(f"{avg_price:.2f}"))
                
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(0, 0, 0, 0)
                
                edit_button = QPushButton("Edit")
                edit_button.setFixedWidth(60)
                edit_button.clicked.connect(lambda _, p=product: self.edit_product(p))
                
                delete_button = QPushButton("Delete")
                delete_button.setFixedWidth(60)
                delete_button.clicked.connect(lambda _, p=product: self.delete_product(p))
                
                actions_layout.addWidget(edit_button)
                actions_layout.addWidget(delete_button)
                self.product_table.setCellWidget(row, 5, actions_widget)

            except Exception as e:
                logger.error(f"Error populating product row: {str(e)}")

        logger.debug(f"Loaded {len(products)} products")

    def manage_categories(self):
        dialog = CategoryManagementDialog(self)
        if dialog.exec():
            self.load_categories()
            self.load_products()

    def add_product(self):
        categories = self.category_service.get_all_categories()
        dialog = EditProductDialog(None, categories, self)
        if dialog.exec():
            try:
                if dialog.product:
                    product_id = self.product_service.create_product(
                        dialog.product['name'],
                        dialog.product['description'],
                        dialog.product['category_id']
                    )
                    if product_id is not None:
                        logger.debug(f"Product added successfully with ID: {product_id}")
                        self.load_products()
                        show_info_message("Success", "Product added successfully.")
                        event_system.product_added.emit(product_id)
                    else:
                        logger.error("Failed to add product")
                        show_error_message("Error", "Failed to add product.")
                else:
                    logger.error("No product data available")
                    show_error_message("Error", "No product data available.")
            except Exception as e:
                logger.error(f"Error adding product: {str(e)}")
                show_error_message("Error", str(e))

    def edit_product(self, product: Product):
        categories = self.category_service.get_all_categories()
        product_dict = product.to_dict()
        dialog = EditProductDialog(product_dict, categories, self)
        if dialog.exec():
            try:
                if dialog.product:
                    self.product_service.update_product(
                        product.id,
                        dialog.product['name'],
                        dialog.product['description'],
                        dialog.product['category_id']
                    )
                    self.load_products()
                    show_info_message("Success", "Product updated successfully.")
                    event_system.product_updated.emit(product.id)
                else:
                    logger.error("No product data available")
                    show_error_message("Error", "No product data available.")
            except Exception as e:
                logger.error(f"Error updating product: {str(e)}")
                show_error_message("Error", str(e))

    def delete_product(self, product: Product):
        reply = QMessageBox.question(self, 'Delete Product', 
                                     f'Are you sure you want to delete product {product.name}?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.product_service.delete_product(product.id)
                self.load_products()
                show_info_message("Success", "Product deleted successfully.")
                event_system.product_deleted.emit(product.id)
            except Exception as e:
                logger.error(f"Error deleting product: {str(e)}")
                show_error_message("Error", str(e))

    def search_products(self):
        search_term = self.search_input.text().strip()
        category_id = self.category_filter.currentData()
        self.filter_products(search_term, category_id)

    def filter_products(self, search_term: Optional[str] = None, category_id: Optional[int] = None):
        if search_term is None:
            search_term = self.search_input.text().strip()
        if category_id is None:
            category_id = self.category_filter.currentData()
        
        try:
            filtered_products = self.product_service.search_products(search_term)
            if category_id is not None:
                filtered_products = [p for p in filtered_products if p.category and p.category.id == category_id]
            self.update_product_table(filtered_products)
        except Exception as e:
            logger.error(f"Error filtering products: {str(e)}")
            show_error_message("Error", f"Failed to filter products: {str(e)}")