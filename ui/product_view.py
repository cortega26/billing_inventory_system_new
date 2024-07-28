from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                               QPushButton, QTableWidgetItem, QMessageBox,
                               QDialog, QDialogButtonBox)
from PySide6.QtCore import Qt
from services.product_service import ProductService
from utils.utils import create_table, show_error_message
from utils.event_system import event_system

from utils.logger import logger

class EditProductDialog(QDialog):
    def __init__(self, product, parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle("Edit Product")
        layout = QVBoxLayout(self)
        
        self.name_input = QLineEdit(product.name)
        self.description_input = QLineEdit(product.description)
        
        layout.addWidget(QLabel("Name:"))
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.description_input)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

class ProductView(QWidget):
    def __init__(self):
        super().__init__()
        self.product_service = ProductService()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Input fields
        input_layout = QHBoxLayout()
        self.name_input = QLineEdit()
        self.description_input = QLineEdit()
        input_layout.addWidget(QLabel("Name:"))
        input_layout.addWidget(self.name_input)
        input_layout.addWidget(QLabel("Description:"))
        input_layout.addWidget(self.description_input)
        
        add_button = QPushButton("Add Product")
        add_button.clicked.connect(self.add_product)
        input_layout.addWidget(add_button)

        layout.addLayout(input_layout)

        # Product table
        self.product_table = create_table(["ID", "Name", "Description", "Avg. Purchase Price", "Edit", "Delete"])
        self.product_table.setSortingEnabled(True)  # Enable sorting
        layout.addWidget(self.product_table)

        self.load_products()

    def load_products(self):
        logger.debug("Loading products")
        try:
            products = self.product_service.get_all_products()
            self.product_table.setRowCount(len(products))
            for row, product in enumerate(products):
                logger.debug(f"Loading product: {product}")
                avg_price = self.product_service.get_average_purchase_price(product.id)
                self.product_table.setItem(row, 0, QTableWidgetItem(str(product.id)))
                self.product_table.setItem(row, 1, QTableWidgetItem(product.name))
                self.product_table.setItem(row, 2, QTableWidgetItem(product.description or ""))
                self.product_table.setItem(row, 3, QTableWidgetItem(f"{avg_price:,}"))
                
                edit_button = QPushButton("Edit")
                edit_button.clicked.connect(lambda _, p=product: self.edit_product(p))
                self.product_table.setCellWidget(row, 4, edit_button)
                
                delete_button = QPushButton("Delete")
                delete_button.clicked.connect(lambda _, p=product: self.delete_product(p))
                self.product_table.setCellWidget(row, 5, delete_button)

                logger.debug(f"Loaded {len(products)} products")
        except Exception as e:
            logger.error(f"Failed to load products: {str(e)}")
            show_error_message("Error", f"Failed to load products: {str(e)}")

    def add_product(self):
        name = self.name_input.text().strip()
        description = self.description_input.text().strip()
        logger.debug(f"Adding product with name: {name}, description: {description}")

        if not name:
            logger.error("Product name is required")
            show_error_message("Error", "Product name is required.")
            return

        try:
            product_id = self.product_service.create_product(name, description)
            if product_id is not None:
                logger.debug(f"Product added successfully with ID: {product_id}")
                self.load_products()
                self.name_input.clear()
                self.description_input.clear()
                QMessageBox.information(self, "Success", "Product added successfully.")
                event_system.product_added.emit()  # Emit the event
            else:
                logger.error("Failed to add product")
                show_error_message("Error", "Failed to add product.")
        except Exception as e:
            logger.error(f"Error adding product: {str(e)}")
            show_error_message("Error", str(e))

    def edit_product(self, product):
        dialog = EditProductDialog(product, self)
        if dialog.exec():
            new_name = dialog.name_input.text().strip()
            new_description = dialog.description_input.text().strip()
            try:
                self.product_service.update_product(product.id, new_name, new_description)
                self.load_products()
                QMessageBox.information(self, "Success", "Product updated successfully.")
                event_system.product_added.emit()  # Emit the event to refresh other views
            except Exception as e:
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
                event_system.product_added.emit()  # Emit the event to refresh other views
            except Exception as e:
                show_error_message("Error", str(e))