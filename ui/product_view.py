from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidgetItem, QMessageBox,
                               QDialog, QDialogButtonBox, QComboBox, QFormLayout)
from PySide6.QtCore import Qt
from services.product_service import ProductService
from services.category_service import CategoryService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system
from utils.logger import logger

class EditProductDialog(QDialog):
    def __init__(self, product, categories, parent=None):
        super().__init__(parent)
        self.product = product
        self.categories = categories
        self.setWindowTitle("Edit Product")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit(self.product.name)
        layout.addRow("Name:", self.name_input)
        
        self.description_input = QLineEdit(self.product.description or "")
        layout.addRow("Description:", self.description_input)
        
        self.category_combo = QComboBox()
        for category in self.categories:
            self.category_combo.addItem(category.name, category.id)
        if self.product.category:
            index = self.category_combo.findData(self.product.category.id)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
        layout.addRow("Category:", self.category_combo)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

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

        # Input fields
        input_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.description_input = QLineEdit()
        self.category_combo = QComboBox()
        self.load_categories()
        
        input_layout.addRow("Name:", self.name_input)
        input_layout.addRow("Description:", self.description_input)
        input_layout.addRow("Category:", self.category_combo)
        
        add_button = QPushButton("Add Product")
        add_button.clicked.connect(self.add_product)
        input_layout.addRow(add_button)

        layout.addLayout(input_layout)

        # Product table
        self.product_table = create_table(["ID", "Name", "Description", "Category", "Avg. Purchase Price", "Edit", "Delete"])
        self.product_table.setSortingEnabled(True)  # Enable sorting
        layout.addWidget(self.product_table)

        self.load_products()

    def load_categories(self):
        try:
            categories = self.category_service.get_all_categories()
            self.category_combo.clear()
            for category in categories:
                self.category_combo.addItem(category.name, category.id)
        except Exception as e:
            logger.error(f"Failed to load categories: {str(e)}")
            show_error_message("Error", f"Failed to load categories: {str(e)}")

    def load_products(self):
        logger.debug("Loading products")
        try:
            products = self.product_service.get_all_products()
            self.update_product_table(products)
        except Exception as e:
            logger.error(f"Failed to load products: {str(e)}")
            show_error_message("Error", f"Failed to load products: {str(e)}")

    def update_product_table(self, products):
        self.product_table.setRowCount(len(products))
        for row, product in enumerate(products):
            logger.debug(f"Loading product: {product}")
            avg_price = self.product_service.get_average_purchase_price(product.id)
            self.product_table.setItem(row, 0, QTableWidgetItem(str(product.id)))
            self.product_table.setItem(row, 1, QTableWidgetItem(product.name))
            self.product_table.setItem(row, 2, QTableWidgetItem(product.description or ""))
            self.product_table.setItem(row, 3, QTableWidgetItem(product.category.name if product.category else ""))
            self.product_table.setItem(row, 4, QTableWidgetItem(f"{avg_price:,.2f}"))
            
            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(lambda _, p=product: self.edit_product(p))
            self.product_table.setCellWidget(row, 5, edit_button)
            
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda _, p=product: self.delete_product(p))
            self.product_table.setCellWidget(row, 6, delete_button)

        logger.debug(f"Loaded {len(products)} products")

    def add_product(self):
        name = self.name_input.text().strip()
        description = self.description_input.text().strip()
        category_id = self.category_combo.currentData()
        logger.debug(f"Adding product with name: {name}, description: {description}, category_id: {category_id}")

        if not name:
            logger.error("Product name is required")
            show_error_message("Error", "Product name is required.")
            return

        try:
            product_id = self.product_service.create_product(name, description, category_id)
            if product_id is not None:
                logger.debug(f"Product added successfully with ID: {product_id}")
                self.load_products()
                self.name_input.clear()
                self.description_input.clear()
                self.category_combo.setCurrentIndex(0)
                QMessageBox.information(self, "Success", "Product added successfully.")
                event_system.product_added.emit(product_id)  # Emit the event
            else:
                logger.error("Failed to add product")
                show_error_message("Error", "Failed to add product.")
        except Exception as e:
            logger.error(f"Error adding product: {str(e)}")
            show_error_message("Error", str(e))

    def edit_product(self, product):
        categories = self.category_service.get_all_categories()
        dialog = EditProductDialog(product, categories, self)
        if dialog.exec():
            new_name = dialog.name_input.text().strip()
            new_description = dialog.description_input.text().strip()
            new_category_id = dialog.category_combo.currentData()
            try:
                self.product_service.update_product(product.id, new_name, new_description, new_category_id)
                self.load_products()
                QMessageBox.information(self, "Success", "Product updated successfully.")
                event_system.product_updated.emit(product.id)  # Emit the event to refresh other views
            except Exception as e:
                logger.error(f"Error updating product: {str(e)}")
                show_error_message("Error", str(e))

    def delete_product(self, product):
        reply = QMessageBox.question(self, 'Delete Product', 
                                     f'Are you sure you want to delete product {product.name}?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.product_service.delete_product(product.id)
                self.load_products()
                QMessageBox.information(self, "Success", "Product deleted successfully.")
                event_system.product_deleted.emit(product.id)  # Emit the event to refresh other views
            except Exception as e:
                logger.error(f"Error deleting product: {str(e)}")
                show_error_message("Error", str(e))

    def search_products(self):
        search_term = self.search_input.text().strip()
        if search_term:
            try:
                products = self.product_service.search_products(search_term)
                self.update_product_table(products)
            except Exception as e:
                logger.error(f"Error searching products: {str(e)}")
                show_error_message("Error", f"Failed to search products: {str(e)}")
        else:
            self.load_products()