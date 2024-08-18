from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QInputDialog,
    QPushButton, QTableWidgetItem, QDoubleSpinBox, QComboBox, QDialog,
    QFormLayout, QDialogButtonBox, QHeaderView, QProgressBar, QMenu, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence
from services.inventory_service import InventoryService
from services.product_service import ProductService
from services.category_service import CategoryService
from utils.helpers import (
    create_table, show_info_message, show_error_message, format_price
)
from utils.system.event_system import event_system
from utils.ui.table_items import NumericTableWidgetItem, PriceTableWidgetItem
from typing import List, Dict, Any, Optional
from utils.decorators import ui_operation, handle_exceptions
from utils.exceptions import ValidationException, DatabaseException, UIException
from utils.validation.validators import validate_string
from utils.system.logger import logger

class EditInventoryDialog(QDialog):
    def __init__(self, product: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.product = product
        self.setWindowTitle(f"Edit {product['product_name']}")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setMinimum(0)
        self.quantity_input.setMaximum(1000000)
        self.quantity_input.setDecimals(2)
        self.quantity_input.setValue(self.product["quantity"])
        layout.addRow("Quantity:", self.quantity_input)

        self.adjustment_input = QDoubleSpinBox()
        self.adjustment_input.setMinimum(-1000000)
        self.adjustment_input.setMaximum(1000000)
        self.adjustment_input.setDecimals(2)
        self.adjustment_input.setValue(0)
        layout.addRow("Adjust Quantity (+ or -):", self.adjustment_input)

        self.reason_input = QLineEdit()
        layout.addRow("Reason for Adjustment:", self.reason_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

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
        self.connect_signals()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search and filter
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search inventory...")
        self.search_input.returnPressed.connect(self.search_inventory)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.search_inventory)
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories", None)
        self.load_categories()
        self.category_filter.currentIndexChanged.connect(self.filter_inventory)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        search_layout.addWidget(QLabel("Category:"))
        search_layout.addWidget(self.category_filter)
        layout.addLayout(search_layout)

        # Inventory table
        self.inventory_table = create_table(
            ["ID", "Product Name", "Category", "Quantity", "Actions"]
        )
        self.inventory_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.inventory_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.inventory_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.inventory_table)

        # Low stock alert button
        low_stock_button = QPushButton("Show Low Stock Items")
        low_stock_button.clicked.connect(self.show_low_stock_alert)
        layout.addWidget(low_stock_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.load_inventory()

        # Set up shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        refresh_shortcut = QAction("Refresh", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_inventory)
        self.addAction(refresh_shortcut)

    def connect_signals(self):
        event_system.product_added.connect(self.on_product_added)
        event_system.product_updated.connect(self.load_inventory)
        event_system.product_deleted.connect(self.load_inventory)
        event_system.sale_added.connect(self.load_inventory)
        event_system.purchase_added.connect(self.load_inventory)
        event_system.inventory_changed.connect(self.on_inventory_changed)

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def on_inventory_changed(self, product_id):
        self.load_inventory()
        logger.info(f"Inventory changed for product ID: {product_id}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_categories(self):
        try:
            categories = self.category_service.get_all_categories()
            for category in categories:
                self.category_filter.addItem(category.name, category.id)
            logger.info(f"Loaded {len(categories)} categories")
        except Exception as e:
            logger.error(f"Error loading categories: {str(e)}")
            raise DatabaseException(f"Failed to load categories: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def on_product_added(self, product_id: int):
        try:
            self.inventory_service.update_quantity(product_id, 0)  # Add new product with quantity 0
            self.load_inventory()
            logger.info(f"New product added to inventory: ID {product_id}")
        except Exception as e:
            logger.error(f"Error adding new product to inventory: {str(e)}")
            raise DatabaseException(f"Failed to add new product to inventory: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_inventory(self):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            inventory_items = self.inventory_service.get_all_inventory()
            self.current_inventory = inventory_items
            QTimer.singleShot(0, lambda: self.update_inventory_table(inventory_items))
            logger.info(f"Loaded {len(inventory_items)} inventory items")
        except Exception as e:
            logger.error(f"Error loading inventory: {str(e)}")
            raise DatabaseException(f"Failed to load inventory: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()
            self.progress_bar.setValue(100)
            QTimer.singleShot(1000, lambda: self.progress_bar.setVisible(False))

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def update_inventory_table(self, inventory_items: List[Dict[str, Any]]):
        try:
            self.inventory_table.setSortingEnabled(False)  # Disable sorting temporarily
            self.inventory_table.setRowCount(len(inventory_items))
            for row, item in enumerate(inventory_items):
                self.inventory_table.setItem(
                    row, 0, NumericTableWidgetItem(item["product_id"])
                )
                self.inventory_table.setItem(row, 1, QTableWidgetItem(item["product_name"]))
                self.inventory_table.setItem(
                    row, 2, QTableWidgetItem(item["category_name"])
                )
                self.inventory_table.setItem(
                    row, 3, PriceTableWidgetItem(item["quantity"], format_price)
                )

                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(0, 0, 0, 0)

                edit_button = QPushButton("Edit")
                edit_button.clicked.connect(lambda _, i=item: self.edit_inventory(i))
                edit_button.setToolTip("Edit inventory for this product")

                actions_layout.addWidget(edit_button)
                self.inventory_table.setCellWidget(row, 4, actions_widget)

                # Store the item data in the row for later retrieval
                for col, key in enumerate(["product_id", "product_name", "category_name", "quantity"]):
                    self.inventory_table.item(row, col).setData(Qt.ItemDataRole.DisplayRole, item[key])

            self.inventory_table.setSortingEnabled(True)  # Re-enable sorting
            logger.info(f"Updated inventory table with {len(inventory_items)} items")
        except Exception as e:
            logger.error(f"Error updating inventory table: {str(e)}")
            raise UIException(f"Failed to update inventory table: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def edit_inventory(self, item: Optional[Dict[str, Any]] = None):
        if item is None:
            # Get the selected row
            selected_rows = self.inventory_table.selectionModel().selectedRows()
            if not selected_rows:
                raise ValidationException("No item selected for editing.")
            row = selected_rows[0].row()
            
            # Retrieve the item data from the row
            item = {
                "product_id": self.inventory_table.item(row, 0).data(Qt.ItemDataRole.UserRole),
                "product_name": self.inventory_table.item(row, 1).data(Qt.ItemDataRole.UserRole),
                "category_name": self.inventory_table.item(row, 2).data(Qt.ItemDataRole.UserRole),
                "quantity": self.inventory_table.item(row, 3).data(Qt.ItemDataRole.UserRole)
            }

        dialog = EditInventoryDialog(item, self)
        if dialog.exec():
            new_quantity = dialog.get_new_quantity()
            adjustment = dialog.get_adjustment()
            reason = dialog.get_reason()

            try:
                if adjustment != 0:
                    self.inventory_service.adjust_inventory(
                        item["product_id"], int(adjustment), reason
                    )
                    new_quantity = item["quantity"] + adjustment
                else:
                    self.inventory_service.set_quantity(
                        item["product_id"], int(new_quantity)
                    )

                # Update the specific item in the current_inventory
                for i, inv_item in enumerate(self.current_inventory):
                    if inv_item["product_id"] == item["product_id"]:
                        self.current_inventory[i]["quantity"] = new_quantity
                        break

                # Update the specific row in the table
                self.update_inventory_table(self.current_inventory)

                show_info_message("Success", "Inventory updated successfully.")
                self.inventory_updated.emit()
                logger.info(f"Inventory updated for product ID: {item['product_id']}, New quantity: {new_quantity}")
            except Exception as e:
                logger.error(f"Error updating inventory: {str(e)}")
                raise DatabaseException(f"Failed to update inventory: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def show_low_stock_alert(self):
        threshold, ok = QInputDialog.getInt(
            self, "Low Stock Threshold", "Enter the low stock threshold:", 10, 1, 1000
        )
        if ok:
            try:
                low_stock_items = self.inventory_service.get_low_stock_products(threshold)
                if low_stock_items:
                    message = "The following items are low in stock:\n\n"
                    for item in low_stock_items:
                        message += f"{item['product_name']} ({item['category_name']}): {format_price(item['quantity'])} left\n"
                    show_info_message("Low Stock Alert", message)
                    logger.info(f"Low stock alert shown for {len(low_stock_items)} items")
                else:
                    show_info_message("Stock Status", "No items are low in stock.")
                    logger.info("No low stock items found")
            except Exception as e:
                logger.error(f"Error getting low stock items: {str(e)}")
                raise DatabaseException(f"Failed to get low stock items: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def search_inventory(self):
        search_term = validate_string(self.search_input.text().strip(), max_length=100)
        category_id = self.category_filter.currentData()
        self.filter_inventory(search_term, category_id)

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, DatabaseException, UIException, show_dialog=True)
    def filter_inventory(
        self, search_term: Optional[str] = None, category_id: Optional[int] = None
    ):
        if search_term is None:
            search_term = self.search_input.text().strip()
        if category_id is None:
            category_id = self.category_filter.currentData()

        try:
            all_items = self.inventory_service.get_all_inventory()
            filtered_items = [
                item
                for item in all_items
                if (
                    search_term.lower() in item["product_name"].lower()
                    or search_term.lower() in str(item["product_id"])
                    or search_term.lower() in item["category_name"].lower()
                )
                and (category_id is None or item["category_id"] == category_id)
            ]
            self.update_inventory_table(filtered_items)
            logger.info(f"Filtered inventory: {len(filtered_items)} items")
        except Exception as e:
            logger.error(f"Error filtering inventory: {str(e)}")
            raise DatabaseException(f"Failed to filter inventory: {str(e)}")

    def refresh(self):
        self.load_inventory()

    def show_context_menu(self, position):
        menu = QMenu()
        edit_action = menu.addAction("Edit")

        action = menu.exec(self.inventory_table.mapToGlobal(position))
        if action:
            row = self.inventory_table.rowAt(position.y())
            product_id = int(self.inventory_table.item(row, 0).text())
            item = next(
                (
                    item
                    for item in self.current_inventory
                    if item["product_id"] == product_id
                ),
                None,
            )

            if item is not None:
                if action == edit_action:
                    self.edit_inventory(item)
            else:
                show_error_message(
                    "Error", f"Inventory item for product ID {product_id} not found."
                )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F5:
            self.refresh()
        else:
            super().keyPressEvent(event)
