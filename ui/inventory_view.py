from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidgetItem, QDialog, QFormLayout, QProgressBar, QMenu, QApplication,
    QComboBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.category_service import CategoryService
from utils.helpers import (
    create_table, show_error_message, show_info_message
)
from utils.system.event_system import event_system
from utils.ui.table_items import NumericTableWidgetItem
from typing import List, Dict, Any
from utils.decorators import ui_operation, handle_exceptions
from utils.exceptions import ValidationException, DatabaseException, UIException
from utils.validation.validators import validate_string
from utils.system.logger import logger
from utils.ui.sound import SoundEffect
import string
import random

class EditInventoryDialog(QDialog):
    def __init__(self, item: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle(f"Edit {item['product_name']}")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        # Show barcode if exists
        if self.item.get('barcode'):
            barcode_label = QLabel(self.item['barcode'])
            layout.addRow("Barcode:", barcode_label)

        # Quantity input
        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setMinimum(0)
        self.quantity_input.setMaximum(1000000)
        self.quantity_input.setDecimals(3)
        self.quantity_input.setValue(self.item["quantity"])
        layout.addRow("Quantity:", self.quantity_input)

        # Adjustment input
        self.adjustment_input = QDoubleSpinBox()
        self.adjustment_input.setMinimum(-1000000)
        self.adjustment_input.setMaximum(1000000)
        self.adjustment_input.setDecimals(3)
        self.adjustment_input.setValue(0)
        layout.addRow("Adjust Quantity (+ or -):", self.adjustment_input)

        # Reason for adjustment
        self.reason_input = QLineEdit()
        layout.addRow("Reason for Adjustment:", self.reason_input)

        # Keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self.validate_and_accept)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, self.validate_and_accept)

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, show_dialog=True)
    def validate_and_accept(self):
        if self.adjustment_input.value() != 0 and not self.reason_input.text().strip():
            raise ValidationException("Please provide a reason for the adjustment.")
        self.accept()

    def get_new_quantity(self) -> float:
        return self.quantity_input.value()

    def get_adjustment(self) -> float:
        return self.adjustment_input.value()

    def get_reason(self) -> str:
        return self.reason_input.text().strip()


class InventoryView(QWidget):
    inventory_updated = Signal()

    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryService()
        self.product_service = ProductService()
        self.category_service = CategoryService()
        self.current_inventory = []
        self.setup_ui()
        self.setup_scan_sound()
        self.connect_signals()

    def connect_signals(self):
        """Set up event connections with delay to ensure database operations complete."""
        event_system.product_added.connect(self.handle_product_change)
        event_system.product_updated.connect(self.handle_product_change)
        event_system.product_deleted.connect(self.handle_product_change)
        event_system.inventory_changed.connect(self.handle_product_change)

    def handle_product_change(self, product_id: int) -> None:
        """Handle product changes with a small delay to ensure DB operations complete."""
        logger.debug(f"Received product change event for product {product_id}")
        # Use QTimer to add a small delay before reloading
        QTimer.singleShot(100, self.refresh)

    def setup_scan_sound(self) -> None:
        """Initialize the sound system."""
        self.scan_sound = SoundEffect("scan.wav")

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Input fields
        input_layout = QHBoxLayout()

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

        # Category filter
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", None)
        self.load_categories()
        self.category_filter.currentIndexChanged.connect(self.filter_inventory)

        # Barcode filter
        self.barcode_filter = QComboBox()
        self.barcode_filter.addItems(["All Products", "With Barcode", "Without Barcode"])
        self.barcode_filter.currentIndexChanged.connect(self.filter_inventory)

        layout.addLayout(input_layout)
        layout.addLayout(barcode_layout)

        # Add category and barcode filters
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Category:"))
        filter_layout.addWidget(self.category_filter)
        filter_layout.addWidget(QLabel("Barcode:"))
        filter_layout.addWidget(self.barcode_filter)
        layout.addLayout(filter_layout)

        # Inventory table
        self.inventory_table = create_table(
            ["Product ID", "Product Name", "Category", "Barcode", "Quantity", "Actions"]
        )
        self.inventory_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.inventory_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.inventory_table)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.load_inventory()
        
        # Connect to event system
        event_system.product_added.connect(self.load_inventory)
        event_system.product_updated.connect(self.load_inventory)
        event_system.product_deleted.connect(self.load_inventory)
        event_system.inventory_changed.connect(self.load_inventory)

    def handle_barcode_scan(self) -> None:
        """Handle barcode scan completion."""
        barcode = self.barcode_input.text().strip()
        if not barcode:
            return

        try:
            # Find product by barcode
            product = self.product_service.get_product_by_barcode(barcode)
            if product:
                # Play success sound
                self.scan_sound.play()
                
                # Filter inventory to show only this product
                filtered_items = [
                    item for item in self.current_inventory 
                    if item['product_id'] == product.id
                ]
                self.update_inventory_table(filtered_items)
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

    def handle_barcode_input(self, text: str) -> None:
        """Handle barcode input changes."""
        # If text is longer than typical barcode, clear it
        if len(text) > 14:  # EAN-14 is the longest common barcode
            self.barcode_input.clear()

    def search_products(self) -> None:
        """Search for products manually."""
        search_term = self.search_input.text().strip()
        if not search_term:
            return

        try:
            # Filter current inventory based on search term
            filtered_items = [
                item for item in self.current_inventory 
                if search_term.lower() in item['product_name'].lower() or
                search_term.lower() in str(item['product_id']).lower() or
                (item.get('barcode') and search_term in item['barcode']) or
                search_term.lower() in item['category_name'].lower()
            ]
            
            self.update_inventory_table(filtered_items)
            if not filtered_items:
                show_error_message("Not Found", "No products found matching the search term")
                
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            show_error_message("Error", str(e))

    def setup_shortcuts(self):
        # Barcode field focus (Ctrl+B)
        barcode_shortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        barcode_shortcut.activated.connect(lambda: self.barcode_input.setFocus())
        
        # Refresh (F5)
        refresh_shortcut = QAction("Refresh", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_inventory)
        self.addAction(refresh_shortcut)

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_categories(self):
        try:
            categories = self.category_service.get_all_categories()
            self.category_filter.clear()
            self.category_filter.addItem("All Categories", None)
            for category in categories:
                self.category_filter.addItem(category.name, category.id)
            logger.info(f"Loaded {len(categories)} categories")
        except Exception as e:
            logger.error(f"Error loading categories: {str(e)}")
            raise DatabaseException(f"Failed to load categories: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_inventory(self, _: Any = None) -> None:
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # Force a fresh read by clearing the cache first
            self.inventory_service.clear_cache()
            inventory_items = self.inventory_service.get_all_inventory()
            self.current_inventory = inventory_items
            
            # Use QTimer to update the UI in the next event loop iteration
            QTimer.singleShot(0, lambda: self.update_inventory_table(inventory_items))
            logger.info(f"Loaded {len(inventory_items)} inventory items")
        except Exception as e:
            logger.error(f"Error loading inventory: {str(e)}")
            raise DatabaseException(f"Failed to load inventory: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    def update_inventory_table(self, inventory_items: List[Dict[str, Any]]):
        """Update the inventory table display."""
        try:
            self.inventory_table.setRowCount(len(inventory_items))
            for row, item in enumerate(inventory_items):
                self.inventory_table.setItem(row, 0, NumericTableWidgetItem(item["product_id"]))
                self.inventory_table.setItem(row, 1, QTableWidgetItem(item["product_name"]))
                self.inventory_table.setItem(row, 2, QTableWidgetItem(item["category_name"]))
                
                # Barcode column
                barcode_item = QTableWidgetItem(item.get("barcode", ""))
                if not item.get("barcode"):
                    barcode_item.setForeground(Qt.GlobalColor.gray)
                    barcode_item.setText("No barcode")
                self.inventory_table.setItem(row, 3, barcode_item)
                
                self.inventory_table.setItem(row, 4, NumericTableWidgetItem(item["quantity"]))

                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(0, 0, 0, 0)

                edit_button = QPushButton("Edit")
                edit_button.clicked.connect(lambda _, i=item: self.edit_inventory(i))
                edit_button.setMaximumWidth(60)
                actions_layout.addWidget(edit_button)
                self.inventory_table.setCellWidget(row, 5, actions_widget)

            logger.info(f"Updated inventory table with {len(inventory_items)} items")
        except Exception as e:
            logger.error(f"Error updating inventory table: {str(e)}")
            raise UIException(f"Failed to update inventory table: {str(e)}")

    def generate_barcode(self, item: Dict[str, Any]) -> None:
        """Generate a new barcode for a product."""
        try:
            # Generate a unique 12-digit barcode
            while True:
                barcode = ''.join(random.choices(string.digits, k=12))
                # Check if barcode already exists
                if not self.product_service.get_product_by_barcode(barcode):
                    break
            
            # Update product with new barcode
            product = self.product_service.get_product(item['product_id'])
            if product:
                self.product_service.update_product(product.id, {'barcode': barcode})
                self.scan_sound.play()
                show_info_message("Success", f"Generated barcode: {barcode}")
                self.load_inventory()
            else:
                raise ValidationException(f"Product with ID {item['product_id']} not found")
        except Exception as e:
            logger.error(f"Error generating barcode: {str(e)}")
            show_error_message("Error", str(e))

    def handle_barcode_search(self):
        """Handle barcode search."""
        barcode = self.barcode_input.text().strip()
        if not barcode:
            return

        try:
            product = self.product_service.get_product_by_barcode(barcode)
            if product:
                self.scan_sound.play()
                # Filter inventory to show only this product
                filtered_items = [
                    item for item in self.current_inventory 
                    if item['product_id'] == product.id
                ]
                self.update_inventory_table(filtered_items)
            else:
                self.barcode_input.setStyleSheet("background-color: #ffebee;")
                QTimer.singleShot(1000, lambda: self.barcode_input.setStyleSheet(""))
                show_error_message("Error", f"No product found with barcode: {barcode}")
        except Exception as e:
            logger.error(f"Error searching by barcode: {str(e)}")
            show_error_message("Error", str(e))
        finally:
            self.barcode_input.clear()
            self.barcode_input.setFocus()

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def edit_inventory(self, item: Dict[str, Any]):
        """Edit inventory item."""
        dialog = EditInventoryDialog(item, self)
        if dialog.exec():
            new_quantity = dialog.get_new_quantity()
            adjustment = dialog.get_adjustment()
            reason = dialog.get_reason()

            try:
                if adjustment != 0:
                    self.inventory_service.adjust_inventory(
                        item["product_id"], 
                        adjustment, 
                        reason
                    )
                else:
                    self.inventory_service.set_quantity(
                        item["product_id"], 
                        new_quantity
                    )

                """
                # Generate barcode if requested
                if dialog.should_generate_barcode():
                    self.generate_barcode(item)
                """

                self.load_inventory()
                show_info_message("Success", "Inventory updated successfully")
                self.inventory_updated.emit()
                logger.info(f"Inventory updated for product ID: {item['product_id']}")
            except Exception as e:
                logger.error(f"Error updating inventory: {str(e)}")
                raise DatabaseException(f"Failed to update inventory: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def search_inventory(self):
        """Search inventory items."""
        search_term = validate_string(self.search_input.text().strip(), max_length=100)
        self.filter_inventory()

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def filter_inventory(self):
        """Filter inventory based on category and barcode status."""
        try:
            category_id = self.category_filter.currentData()
            barcode_filter = self.barcode_filter.currentText()
            search_term = self.search_input.text().strip().lower()

            filtered_items = [
                item for item in self.current_inventory
                if (category_id is None or item["category_id"] == category_id) and
                (barcode_filter == "All Products" or 
                 (barcode_filter == "With Barcode" and item.get("barcode")) or
                 (barcode_filter == "Without Barcode" and not item.get("barcode"))) and
                (not search_term or
                 search_term in item["product_name"].lower() or
                 search_term in str(item["product_id"]).lower() or
                 search_term in item["category_name"].lower() or
                 (item.get("barcode") and search_term in item["barcode"].lower()))
            ]

            self.update_inventory_table(filtered_items)
            logger.info(f"Filtered inventory: {len(filtered_items)} items")
        except Exception as e:
            logger.error(f"Error filtering inventory: {str(e)}")
            raise DatabaseException(f"Failed to filter inventory: {str(e)}")

    def show_context_menu(self, position):
        """Show context menu for inventory table."""
        menu = QMenu()
        edit_action = menu.addAction("Edit")
        generate_action = None
        
        row = self.inventory_table.rowAt(position.y())
        if row >= 0:
            barcode = self.inventory_table.item(row, 3).text()
            if barcode == "No barcode":
                generate_action = menu.addAction("Generate Barcode")

        action = menu.exec(self.inventory_table.mapToGlobal(position))
        if action:
            if row >= 0:
                product_id = int(self.inventory_table.item(row, 0).text())
                item = next((item for item in self.current_inventory if item["product_id"] == product_id), None)
                
                if item:
                    if action == edit_action:
                        self.edit_inventory(item)
                    elif action == generate_action:
                        self.generate_barcode(item)
                else:
                    show_error_message("Error", f"Inventory item for product ID {product_id} not found")

    def refresh(self):
        """Refresh the inventory view with cache clearing."""
        try:
            logger.debug("Refreshing inventory view")
            # Clear the cache before loading
            self.inventory_service.clear_cache()
            self.load_inventory()
            self.barcode_input.setFocus()
        except Exception as e:
            logger.error(f"Error refreshing inventory: {str(e)}")
            show_error_message("Error", f"Failed to refresh inventory: {str(e)}")

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key.Key_F5:
            self.refresh()
        elif event.key() == Qt.Key.Key_Escape:
            self.barcode_input.clear()
            self.search_input.clear()
            self.category_filter.setCurrentIndex(0)
            self.barcode_filter.setCurrentIndex(0)
            self.load_inventory()
        else:
            super().keyPressEvent(event)