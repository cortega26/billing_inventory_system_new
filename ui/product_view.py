from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidgetItem, QMessageBox,
    QSpinBox, QDialog, QDialogButtonBox, QComboBox, QFormLayout, QHeaderView, QAbstractItemView, QProgressBar
    )
from PySide6.QtCore import Qt, QTimer
from services.product_service import ProductService
from services.category_service import CategoryService
from utils.utils import create_table, show_error_message, show_info_message, format_price
from utils.event_system import event_system
from utils.logger import logger
from ui.category_management_dialog import CategoryManagementDialog
from utils.table_items import NumericTableWidgetItem, PercentageTableWidgetItem, PriceTableWidgetItem
from typing import List, Optional, Dict, Any
from models.product import Product
from models.category import Category

class EditProductDialog(QDialog):
    def __init__(self, product: Optional[Dict[str, Any]], categories: List[Category], parent=None):
        super().__init__(parent)
        self.product = product or {}
        self.categories = categories
        self.setWindowTitle("Edit Product" if product else "Add Product")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit(self.product.get('name', ''))
        layout.addRow("Name:", self.name_input)
        
        self.description_input = QLineEdit(self.product.get('description', ''))
        layout.addRow("Description:", self.description_input)
        
        self.category_combo = QComboBox()
        self.category_combo.addItem("Uncategorized", None)
        for category in self.categories:
            self.category_combo.addItem(category.name, category.id)
        if self.product.get('category_id'):
            index = self.category_combo.findData(self.product['category_id'])
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
        layout.addRow("Category:", self.category_combo)
        
        self.cost_price_input = QSpinBox()
        self.cost_price_input.setMaximum(1000000000)
        self.cost_price_input.setValue(self.product.get('cost_price', 0) or 0)
        layout.addRow("Cost Price:", self.cost_price_input)
        
        self.sell_price_input = QSpinBox()
        self.sell_price_input.setMaximum(1000000000)
        self.sell_price_input.setValue(self.product.get('sell_price', 0) or 0)
        layout.addRow("Sell Price:", self.sell_price_input)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    def validate_and_accept(self):
        name = self.name_input.text().strip()
        description = self.description_input.text().strip()
        category_id = self.category_combo.currentData()
        cost_price = self.cost_price_input.value()
        sell_price = self.sell_price_input.value()

        if not name:
            show_error_message("Validation Error", "Product name cannot be empty.")
            return
        if len(name) > 100:
            show_error_message("Validation Error", "Product name cannot exceed 100 characters.")
            return
        if description and len(description) > 500:
            show_error_message("Validation Error", "Product description cannot exceed 500 characters.")
            return
        if cost_price < 0 or sell_price < 0:
            show_error_message("Validation Error", "Prices cannot be negative.")
            return

        self.product = {
            'name': name,
            'description': description,
            'category_id': category_id,
            'cost_price': cost_price,
            'sell_price': sell_price
        }
        self.accept()

class ProductView(QWidget):
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
        self.product_table = create_table(["ID", "Name", "Description", "Category", "Cost Price", "Sell Price", "Profit Margin", "Actions"])
        self.product_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.product_table.setSortingEnabled(True)
        self.product_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
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

    def on_category_changed(self, index):
        self.current_category_id = self.category_filter.itemData(index)
        self.filter_products(category_id=self.current_category_id)

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
            # Apply the current category filter if set
            if self.current_category_id is not None:
                products = [p for p in products if p.category and p.category.id == self.current_category_id]
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
                profit_margin = self.product_service.get_product_profit_margin(product.id)
                self.product_table.setItem(row, 0, NumericTableWidgetItem(product.id))
                self.product_table.setItem(row, 1, QTableWidgetItem(product.name))
                self.product_table.setItem(row, 2, QTableWidgetItem(product.description or ""))
                self.product_table.setItem(row, 3, QTableWidgetItem(product.category.name if product.category else ""))
                
                cost_price_item = QTableWidgetItem(format_price(product.cost_price) if product.cost_price is not None else "N/A")
                cost_price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.product_table.setItem(row, 4, PriceTableWidgetItem(product.cost_price, format_price))

                sell_price_item = QTableWidgetItem(format_price(product.sell_price) if product.sell_price is not None else "N/A")
                sell_price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.product_table.setItem(row, 5, PriceTableWidgetItem(product.sell_price, format_price))

                profit_margin_item = QTableWidgetItem(f"{profit_margin:.2f}%".replace('.', ',') if profit_margin is not None else "N/A")
                profit_margin_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.product_table.setItem(row, 6, PercentageTableWidgetItem(profit_margin))

                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(0, 0, 0, 0)
                
                edit_button = QPushButton("Edit")
                edit_button.setFixedWidth(80)
                edit_button.clicked.connect(lambda _, p=product: self.edit_product(p))
                
                delete_button = QPushButton("Delete")
                delete_button.setFixedWidth(80)
                delete_button.clicked.connect(lambda _, p=product: self.delete_product(p))
                
                actions_layout.addWidget(edit_button)
                actions_layout.addWidget(delete_button)
                self.product_table.setCellWidget(row, 7, actions_widget)

                # Set column widths
                self.product_table.setColumnWidth(0, 50)  # ID
                self.product_table.setColumnWidth(1, 300)  # Name
                self.product_table.setColumnWidth(2, 200)  # Description
                self.product_table.setColumnWidth(3, 200)  # Category
                self.product_table.setColumnWidth(4, 100)  # Cost Price
                self.product_table.setColumnWidth(5, 100)  # Sell Price
                self.product_table.setColumnWidth(6, 100)  # Profit Margin
                self.product_table.setColumnWidth(7, 150)  # Actions

                # Set the last column (Actions) to stretch
                self.product_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)


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
                        dialog.product['category_id'],
                        dialog.product['cost_price'],
                        dialog.product['sell_price']
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
                        dialog.product['category_id'],
                        dialog.product['cost_price'],
                        dialog.product['sell_price']
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
        search_term = str(self.search_input.text().strip())
        category_id = self.category_filter.currentData()
        self.filter_products(search_term, category_id)

    def filter_products(self, search_term: Optional[str] = None, category_id: Optional[int] = None):
        if search_term is None:
            search_term = str(self.search_input.text().strip())
        else:
            search_term = str(search_term)  # Ensure search_term is a string
        
        if category_id is None:
            category_id = self.category_filter.currentData()
        
        try:
            all_products = self.product_service.get_all_products()
            filtered_products = []

            for p in all_products:
                logger.debug(f"Filtering product: id={p.id}, name={p.name}, description={p.description}, category={p.category}")
                
                matches_search = False
                if not search_term:
                    matches_search = True
                else:
                    name_match = search_term.lower() in str(p.name).lower() if p.name is not None else False
                    desc_match = search_term.lower() in str(p.description).lower() if p.description is not None else False
                    matches_search = name_match or desc_match

                matches_category = (
                    category_id is None or  # "All Categories" selected
                    (p.category and p.category.id == category_id)  # Product has a category and it matches
                )

                if matches_search and matches_category:
                    filtered_products.append(p)

            logger.debug(f"Filtered products count: {len(filtered_products)}")
            self.update_product_table(filtered_products)
        except Exception as e:
            logger.error(f"Error filtering products: {str(e)}")
            logger.exception("Stack trace:")
            show_error_message("Error", f"Failed to filter products: {str(e)}")
