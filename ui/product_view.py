from typing import Any, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.category import Category
from models.product import Product
from services.category_service import CategoryService
from services.product_service import ProductService
from ui.category_management_dialog import CategoryManagementDialog
from utils.decorators import handle_exceptions, ui_operation
from utils.exceptions import (
    DatabaseException,
    NotFoundException,
    UIException,
    ValidationException,
)
from utils.helpers import (
    create_table,
    format_price,
    show_error_message,
    show_info_message,
)
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.ui.table_items import (
    NumericTableWidgetItem,
    PercentageTableWidgetItem,
    PriceTableWidgetItem,
)
from utils.validation.validators import validate_float, validate_string


class EditProductDialog(QDialog):
    def __init__(
        self, product: Optional[Product], categories: List[Category], parent=None
    ):
        super().__init__(parent)
        self.product = product
        self.categories = categories
        self.setWindowTitle("Editar Producto" if product else "Agregar Producto")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        self.name_input = QLineEdit(self.product.name if self.product else "")
        self.description_input = QLineEdit(
            self.product.description or "" if self.product else ""
        )
        self.barcode_input = QLineEdit(
            self.product.barcode or "" if self.product else ""
        )

        self.category_combo = QComboBox()
        self.category_combo.addItem("Sin Categoría", None)
        for category in self.categories:
            self.category_combo.addItem(category.name, category.id)
        if self.product and self.product.category_id:
            index = self.category_combo.findData(self.product.category_id)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)

        self.cost_price_input = QDoubleSpinBox()
        self.cost_price_input.setMaximum(1000000000)
        self.cost_price_input.setValue(
            float(self.product.cost_price)
            if self.product and self.product.cost_price
            else 0
        )

        self.sell_price_input = QDoubleSpinBox()
        self.sell_price_input.setMaximum(1000000000)
        self.sell_price_input.setValue(
            float(self.product.sell_price)
            if self.product and self.product.sell_price
            else 0
        )

        layout.addRow("Nombre:", self.name_input)
        layout.addRow("Descripción:", self.description_input)
        layout.addRow("Código de Barras:", self.barcode_input)
        layout.addRow("Categoría:", self.category_combo)
        layout.addRow("Precio Costo:", self.cost_price_input)
        layout.addRow("Precio Venta:", self.sell_price_input)

        # Add help text for barcode
        barcode_help = QLabel("Opcional - Debe tener 8, 12, 13 o 14 dígitos si se ingresa")
        barcode_help.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow("", barcode_help)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, show_dialog=True)
    def validate_and_accept(self):
        name = validate_string(
            self.name_input.text().strip(), min_length=1, max_length=100
        )
        description = validate_string(
            self.description_input.text().strip(), min_length=0, max_length=500
        )
        category_id = self.category_combo.currentData()
        cost_price = validate_float(self.cost_price_input.value(), min_value=0)
        sell_price = validate_float(self.sell_price_input.value(), min_value=0)

        # Get barcode value and validate if not empty
        barcode = self.barcode_input.text().strip()
        if barcode:
            try:
                Product.validate_barcode(barcode)
            except ValidationException as e:
                raise ValidationException(str(e))

        self.product_data = {
            "name": name,
            "description": description,
            "category_id": category_id,
            "cost_price": cost_price,
            "sell_price": sell_price,
            "barcode": barcode if barcode else None,
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
        self.search_input.setPlaceholderText("Buscar productos...")
        self.search_input.returnPressed.connect(self.search_products)
        search_button = QPushButton("Buscar")
        search_button.clicked.connect(self.search_products)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Category filter
        filter_layout = QHBoxLayout()
        self.category_filter = QComboBox()
        self.category_filter.addItem("Todas las Categorías", None)
        self.load_categories()
        self.category_filter.currentIndexChanged.connect(self.on_category_changed)
        filter_layout.addWidget(QLabel("Filtrar por Categoría:"))
        filter_layout.addWidget(self.category_filter)
        layout.addLayout(filter_layout)

        # Product table
        self.product_table = create_table(
            [
                "ID",
                "Nombre",
                "Descripción",
                "Categoría",
                "Precio Costo",
                "Precio Venta",
                "Margen Ganancia",
                "Acciones",
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
        add_button = QPushButton("Agregar Producto")
        add_button.clicked.connect(self.add_product)
        add_button.setToolTip("Agregar nuevo producto (Ctrl+N)")
        manage_categories_button = QPushButton("Gestionar Categorías")
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

        # Set up shortcuts
        self.setup_shortcuts()

        self.load_products()

        # Connect to event system
        event_system.product_added.connect(self.load_products)
        event_system.product_updated.connect(self.load_products)
        event_system.product_deleted.connect(self.load_products)

    def setup_shortcuts(self):
        add_shortcut = QAction("Agregar Producto", self)
        add_shortcut.setShortcut(QKeySequence("Ctrl+N"))
        add_shortcut.triggered.connect(self.add_product)
        self.addAction(add_shortcut)

        refresh_shortcut = QAction("Actualizar", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_products)
        self.addAction(refresh_shortcut)

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def on_category_changed(self, index):
        try:
            self.current_category_id = self.category_filter.itemData(index)
            # Get fresh data and apply new filter
            fresh_products = self.product_service.get_all_products()
            self.filter_products(products=fresh_products)
        except Exception as e:
            logger.error(f"Error changing category: {str(e)}")
            raise UIException(f"Failed to change category: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_categories(self):
        try:
            categories = self.category_service.get_all_categories()
            self.category_filter.clear()
            self.category_filter.addItem("Todas las Categorías", None)
            for category in categories:
                self.category_filter.addItem(category.name, category.id)
            logger.info("Categories loaded successfully")
        except Exception as e:
            logger.error(f"Error loading categories: {str(e)}")
            raise DatabaseException(f"Failed to load categories: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_products(self, _: Any = None) -> None:
        """Load all products and maintain current filters."""
        logger.debug("Loading products list")
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            fresh_products = self.product_service.get_all_products()
            logger.debug(f"Loaded {len(fresh_products)} products")
            # Use filter_products to maintain current filters
            self.filter_products(products=fresh_products)
            logger.info("Products loaded successfully")
        except Exception as e:
            logger.error(f"Error loading products: {str(e)}")
            raise DatabaseException(f"Failed to load products: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def update_product_table(self, products: List[Product]):
        """Update the product table display."""
        logger.debug(f"Updating product table with {len(products)} products")
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            # Clear existing rows
            self.product_table.setRowCount(0)
            self.product_table.setRowCount(len(products))

            for row, product in enumerate(products):
                logger.debug(f"Adding row {row}: Product ID={product.id}")

                try:
                    self.product_table.setItem(
                        row, 0, NumericTableWidgetItem(product.id)
                    )
                    self.product_table.setItem(row, 1, QTableWidgetItem(product.name))
                    self.product_table.setItem(
                        row, 2, QTableWidgetItem(product.description or "")
                    )
                    self.product_table.setItem(
                        row,
                        3,
                        QTableWidgetItem(product.category_name or "Sin Categoría"),
                    )
                    self.product_table.setItem(
                        row,
                        4,
                        PriceTableWidgetItem(
                            float(product.cost_price) if product.cost_price else 0,
                            format_price,
                        ),
                    )
                    self.product_table.setItem(
                        row,
                        5,
                        PriceTableWidgetItem(
                            float(product.sell_price) if product.sell_price else 0,
                            format_price,
                        ),
                    )
                    self.product_table.setItem(
                        row,
                        6,
                        PercentageTableWidgetItem(
                            float(product.calculate_profit_margin())
                        ),
                    )

                    # Create action buttons
                    actions_widget = QWidget()
                    actions_layout = QHBoxLayout(actions_widget)
                    actions_layout.setContentsMargins(0, 0, 0, 0)

                    edit_button = QPushButton("Editar")
                    edit_button.setFixedWidth(80)
                    edit_button.clicked.connect(
                        lambda _, p=product: self.edit_product(p)
                    )

                    delete_button = QPushButton("Eliminar")
                    delete_button.setFixedWidth(80)
                    delete_button.clicked.connect(
                        lambda _, p=product: self.delete_product(p)
                    )

                    actions_layout.addWidget(edit_button)
                    actions_layout.addWidget(delete_button)
                    self.product_table.setCellWidget(row, 7, actions_widget)
                except Exception as e:
                    logger.error(f"Error updating row {row}: {str(e)}")
                    continue

            # Adjust table display
            self.product_table.resizeColumnsToContents()
            self.product_table.horizontalHeader().setSectionResizeMode(
                7, QHeaderView.ResizeMode.Stretch
            )

            logger.info("Product table updated successfully")
        except Exception as e:
            logger.error(f"Error updating product table: {str(e)}")
            raise UIException(f"Failed to update product table: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def add_product(self):
        try:
            categories = self.category_service.get_all_categories()
            dialog = EditProductDialog(None, categories, self)
            if dialog.exec():
                product_data = dialog.product_data
                logger.debug("Creating new product", extra={"data": product_data})
                product_id = self.product_service.create_product(product_data)
                logger.debug(f"Product created with ID: {product_id}")

                if product_id is not None:
                    # Get fresh data but maintain filters
                    fresh_products = self.product_service.get_all_products()
                    self.filter_products(products=fresh_products)

                    show_info_message("Éxito", "Producto agregado exitosamente.")
                    event_system.product_added.emit(product_id)
                    self.product_updated.emit()
                    logger.info(f"Product added successfully: ID {product_id}")
                else:
                    raise DatabaseException("Failed to add product.")
        except Exception as e:
            logger.error(f"Error adding product: {str(e)}")
            raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
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

                    # Get fresh data but maintain current filter
                    fresh_products = self.product_service.get_all_products()
                    self.filter_products(products=fresh_products)

                    show_info_message("Éxito", "Producto actualizado exitosamente.")
                    event_system.product_updated.emit(product.id)
                    self.product_updated.emit()
                    logger.info(f"Product updated successfully: ID {product.id}")
                except Exception as e:
                    logger.error(f"Error updating product: {str(e)}")
                    raise
        else:
            raise ValidationException(f"Product with ID {product_id} not found.")

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def delete_product(self, product: Product):
        try:
            reply = QMessageBox.question(
                self,
                "Eliminar Producto",
                f"¿Está seguro que desea eliminar el producto {product.name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    self.product_service.delete_product(product.id)

                    # Get fresh data but maintain filters
                    fresh_products = self.product_service.get_all_products()
                    self.filter_products(products=fresh_products)

                    show_info_message("Éxito", "Producto eliminado exitosamente.")
                    event_system.product_deleted.emit(product.id)
                    self.product_updated.emit()
                    logger.info(f"Product deleted successfully: ID {product.id}")
                finally:
                    QApplication.restoreOverrideCursor()
        except Exception as e:
            logger.error(f"Error deleting product: {str(e)}")
            raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def search_products(self):
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            search_term = self.search_input.text().strip()
            search_term = validate_string(search_term, max_length=100)
            # Get fresh data and apply new search
            fresh_products = self.product_service.get_all_products()
            self.filter_products(products=fresh_products, search_term=search_term)
        finally:
            QApplication.restoreOverrideCursor()

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def filter_products(
        self,
        products: Optional[List[Product]] = None,
        search_term: Optional[str] = None,
    ):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # Store current search term if none provided
            if search_term is None:
                search_term = self.search_input.text().strip()

            # Only fetch all products if no products were provided
            if products is None:
                products = self.product_service.get_all_products() or []

            search_term = search_term.lower()

            # First apply category filter
            if self.current_category_id is not None:
                products = [
                    p for p in products if p.category_id == self.current_category_id
                ]

            # Then apply search filter
            if search_term:
                products = [
                    p
                    for p in products
                    if search_term in p.name.lower()
                    or (p.description and search_term in p.description.lower())
                ]

            self.update_product_table(products)
            logger.info(f"Products filtered: {len(products)} results")
        finally:
            QApplication.restoreOverrideCursor()

    def refresh(self):
        """Refresh the product view while maintaining current filters."""
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            fresh_products = self.product_service.get_all_products()
            self.filter_products(products=fresh_products)
        except Exception as e:
            logger.error(f"Error in refresh: {str(e)}")
            show_error_message("Error", "Falló al actualizar lista de productos")
        finally:
            QApplication.restoreOverrideCursor()

    def on_product_deleted(self, product_id: int):
        """Handle product deleted event gracefully."""
        try:
            logger.info(f"Product deleted event received: {product_id}")
            # Simply refresh the view - don't try to access the deleted product
            self.refresh()
        except Exception as e:
            logger.error(f"Error handling product deletion: {str(e)}")
            # Don't raise the exception - just log it

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def manage_categories(self):
        dialog = CategoryManagementDialog(self)
        if dialog.exec():
            self.load_categories()
            self.load_products()
            logger.info("Categories managed successfully")

    def show_context_menu(self, position):
        try:
            row = self.product_table.rowAt(position.y())
            if row < 0:  # No valid row selected
                return

            menu = QMenu()
            edit_action = menu.addAction("Editar")
            delete_action = menu.addAction("Eliminar")
            refresh_action = menu.addAction("Actualizar")

            action = menu.exec(self.product_table.mapToGlobal(position))
            if action:
                product_id = int(self.product_table.item(row, 0).text())
                try:
                    product = self.product_service.get_product(product_id)
                    if product is None:
                        raise NotFoundException(
                            f"Product with ID {product_id} not found."
                        )

                    if action == edit_action:
                        self.edit_product(product)
                    elif action == delete_action:
                        if product:
                            self.delete_product(product)
                    elif action == refresh_action:
                        self.filter_products()
                except Exception as e:
                    logger.error(f"Error in context menu action: {str(e)}")
                    show_error_message("Error", str(e))
        except Exception as e:
            logger.error(f"Error showing context menu: {str(e)}")
            show_error_message("Error", "Failed to show context menu")
            if action:
                if action == edit_action:
                    self.edit_product(product)
                elif action == delete_action and product:
                    self.delete_product(product)
                elif action == refresh_action:
                    self.filter_products()
                else:
                    show_error_message(
                        "Error", f"No se encontró producto con ID {product_id}"
                    )

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
        """Handle keyboard events."""
        try:
            if event.key() == Qt.Key.Key_Delete:
                selected_rows = self.product_table.selectionModel().selectedRows()
                if selected_rows:
                    row = selected_rows[0].row()
                    product_id = int(self.product_table.item(row, 0).text())
                    try:
                        product = self.product_service.get_product(product_id)
                        if product:
                            self.delete_product(product)
                    except Exception as e:
                        logger.error(f"Error handling delete key event: {str(e)}")
                        show_error_message(
                            "Error", f"Failed to delete product: {str(e)}"
                        )
            else:
                super().keyPressEvent(event)
        except Exception as e:
            logger.error(f"Error in keyPressEvent: {str(e)}")
            super().keyPressEvent(event)

    def cleanup(self):
        """Cleanup resources when the widget is being destroyed."""
        try:
            # Disconnect from event system
            event_system.product_added.disconnect(self.load_products)
            event_system.product_updated.disconnect(self.load_products)
            event_system.product_deleted.disconnect(self.load_products)
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
