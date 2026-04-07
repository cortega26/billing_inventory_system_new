from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QCheckBox,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.customer import Customer
from services.customer_service import CustomerService
from utils.decorators import handle_exceptions, ui_operation
from utils.exceptions import DatabaseException, UIException, ValidationException
from utils.helpers import (
    create_table,
    format_price,
    show_error_message,
    show_info_message,
)
from utils.system.event_system import event_system
from utils.system.logger import logger
from utils.ui.table_items import (
    DepartmentIdentifierTableWidgetItem,
    NumericTableWidgetItem,
    PriceTableWidgetItem,
)
from utils.validation.validators import validate_string


class EditCustomerDialog(QDialog):
    def __init__(self, customer: Optional[Customer], parent=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Editar Cliente" if customer else "Agregar Cliente")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)

        # 9-digit identifier
        self.identifier_9_input = QLineEdit(
            self.customer.identifier_9 if self.customer else ""
        )
        self.identifier_9_input.setPlaceholderText("Ingrese N° Celular (9 dígitos)")
        layout.addRow("N° Celular:", self.identifier_9_input)

        # 3 or 4-digit identifier
        self.identifier_3or4_input = QLineEdit(
            self.customer.identifier_3or4 or "" if self.customer else ""
        )
        self.identifier_3or4_input.setPlaceholderText(
            "Ingrese N° Departamento (opcional)"
        )
        layout.addRow("N° Departamento:", self.identifier_3or4_input)

        # Name field
        self.name_input = QLineEdit(self.customer.name or "" if self.customer else "")
        self.name_input.setPlaceholderText("Ingrese nombre (opcional)")
        layout.addRow("Nombre:", self.name_input)

        # Add help text for name requirements
        name_help = QLabel(
            "El nombre puede contener letras, tildes y espacios (máx 50 carac.)"
        )
        name_help.setStyleSheet("color: gray; font-size: 10px;")
        layout.addRow("", name_help)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

    @ui_operation(show_dialog=True)
    @handle_exceptions(ValidationException, show_dialog=True)
    def validate_and_accept(self):
        try:
            # Create a temporary customer to validate the input
            Customer(
                id=0,
                identifier_9=self.identifier_9_input.text().strip(),
                identifier_3or4=self.identifier_3or4_input.text().strip() or None,
                name=self.name_input.text().strip() or None,
            )
            self.accept()
        except ValidationException as e:
            raise ValidationException(str(e))


class CustomerView(QWidget):
    customer_updated = Signal()

    def __init__(self):
        super().__init__()
        self.customer_service = CustomerService()
        self._connections = []
        self.setup_ui()
        self.connect_signals()

    def connect_signals(self):
        """Connect signals and track them for cleanup."""
        self._connections.append((event_system.customer_added, self.load_customers))
        self._connections.append((event_system.customer_updated, self.load_customers))
        self._connections.append((event_system.customer_deleted, self.load_customers))

        for signal, slot in self._connections:
            signal.connect(slot)

    def disconnect_signals(self):
        """Safely disconnect all signals."""
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except Exception:
                pass
        self._connections.clear()

    def cleanup(self):
        """Cleanup method to properly disconnect signals."""
        self.disconnect_signals()

    def closeEvent(self, event):
        """Clean up on close."""
        self.disconnect_signals()
        super().closeEvent(event)

    def __del__(self):
        """Destructor cleanup."""
        self.disconnect_signals()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Search field
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por ID o nombre...")
        self.search_input.returnPressed.connect(self.search_customers)
        search_button = QPushButton("Buscar")
        search_button.clicked.connect(self.search_customers)
        self.show_archived_checkbox = QCheckBox("Mostrar archivados")
        self.show_archived_checkbox.toggled.connect(self.load_customers)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        search_layout.addWidget(self.show_archived_checkbox)
        layout.addLayout(search_layout)

        # Customer table
        self.customer_table = create_table(
            [
                "ID",
                "N° Celular",
                "N° Departamento",
                "Nombre",
                "Estado",
                "Compras Totales",
                "Monto Total",
                "Acciones",
            ]
        )
        self.customer_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.customer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.customer_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.customer_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customer_table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.customer_table)

        # Add customer button
        add_button = QPushButton("Agregar Cliente")
        add_button.clicked.connect(self.add_customer)
        add_button.setToolTip("Agregar nuevo cliente (Ctrl+N)")
        layout.addWidget(add_button)

        self.load_customers()

        # Set up shortcuts
        self.setup_shortcuts()

    def setup_shortcuts(self):
        add_shortcut = QAction("Agregar Cliente", self)
        add_shortcut.setShortcut(QKeySequence("Ctrl+N"))
        add_shortcut.triggered.connect(self.add_customer)
        self.addAction(add_shortcut)

        refresh_shortcut = QAction("Actualizar", self)
        refresh_shortcut.setShortcut(QKeySequence("F5"))
        refresh_shortcut.triggered.connect(self.load_customers)
        self.addAction(refresh_shortcut)

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def load_customers(self, _ignored_id=None) -> None:
        """
        Load all customers into the table (re-fetch from the DB).
        _ignored_id is an unused parameter (emitted by the signal).
        """
        logger.debug(f"(load_customers) Called with _ignored_id={_ignored_id}")

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # Force a fresh read from DB
            self.customer_service.clear_cache()
            customers = self.customer_service.get_all_customers(
                active_only=not self.show_archived_checkbox.isChecked()
            )
            logger.debug(f"(load_customers) Fetched {len(customers)} customers from DB")

            # Now populate the table
            self.populate_customer_table(customers)

        except Exception as e:
            logger.error(f"(load_customers) Error loading customers: {str(e)}")
            show_error_message("Error", f"Error al cargar clientes: {str(e)}")

        finally:
            QApplication.restoreOverrideCursor()

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def populate_customer_table(self, customers: List[Customer]) -> None:
        """
        Populate the customer table with a list of Customer objects,
        ensuring stable row→customer_id mapping and preserving any pre-existing sort.
        """
        try:
            logger.debug(
                f"(populate_customer_table) Starting with {len(customers)} raw customers"
            )

            # 1) Capture the current sorting state (column + order) if any
            prev_col = self.customer_table.horizontalHeader().sortIndicatorSection()
            prev_order = self.customer_table.horizontalHeader().sortIndicatorOrder()

            # 2) Disable sorting while we repopulate rows
            self.customer_table.setSortingEnabled(False)

            # 3) Deduplicate or transform as needed
            displayed_ids = set()
            unique_customers = []
            for cust in customers:
                if cust.id not in displayed_ids:
                    unique_customers.append(cust)
                    displayed_ids.add(cust.id)
                else:
                    logger.warning(f"Skipping duplicate customer ID: {cust.id}")

            logger.debug(
                f"(populate_customer_table) Unique customers count: {len(unique_customers)}"
            )

            # 4) Clear old rows, set to new count
            self.customer_table.setRowCount(0)
            self.customer_table.setRowCount(len(unique_customers))

            # 5) Fill each row
            for row, cust in enumerate(unique_customers):
                try:
                    total_purchases, total_amount = (
                        self.customer_service.get_customer_stats(cust.id)
                    )

                    # Column 0: Customer ID
                    self.customer_table.setItem(row, 0, NumericTableWidgetItem(cust.id))

                    # Column 1: 9-digit Identifier
                    self.customer_table.setItem(
                        row, 1, QTableWidgetItem(cust.identifier_9)
                    )

                    # Column 2: 3 or 4-digit Identifier
                    identifier_item = DepartmentIdentifierTableWidgetItem(
                        cust.identifier_3or4 or "N/A"
                    )
                    self.customer_table.setItem(row, 2, identifier_item)

                    # Column 3: Name
                    name_item = QTableWidgetItem(cust.name or "")
                    name_item.setToolTip(
                        cust.name if cust.name else "No se proporcionó nombre"
                    )
                    self.customer_table.setItem(row, 3, name_item)

                    # Column 4: Estado
                    status_text = "Activo" if cust.is_active else "Archivado"
                    self.customer_table.setItem(row, 4, QTableWidgetItem(status_text))

                    # Column 5: Total Purchases
                    self.customer_table.setItem(
                        row, 5, NumericTableWidgetItem(total_purchases)
                    )

                    # Column 6: Total Amount
                    self.customer_table.setItem(
                        row, 6, PriceTableWidgetItem(total_amount, format_price)
                    )

                    # Column 7: Actions (Edit / Archive/Restore)
                    actions_widget = QWidget()
                    actions_layout = QHBoxLayout(actions_widget)
                    actions_layout.setContentsMargins(0, 0, 0, 0)
                    actions_layout.setSpacing(6)
                    actions_layout.setAlignment(Qt.AlignCenter)

                    edit_button = QPushButton("Editar")
                    edit_button.setFixedWidth(80)
                    edit_button.setFixedHeight(24)
                    edit_button.setStyleSheet("padding: 2px 8px;")
                    edit_button.clicked.connect(
                        lambda _, cid=cust.id: self.edit_customer_by_id(cid)
                    )

                    action_label = "Eliminar" if cust.is_active else "Restaurar"
                    delete_button = QPushButton(action_label)
                    delete_button.setFixedWidth(80)
                    delete_button.setFixedHeight(24)
                    delete_button.setStyleSheet("padding: 2px 8px;")
                    delete_button.clicked.connect(
                        lambda _, cid=cust.id: self.delete_customer_by_id(cid)
                    )

                    actions_layout.addWidget(edit_button)
                    actions_layout.addWidget(delete_button)
                    self.customer_table.setCellWidget(row, 7, actions_widget)
                    self.customer_table.setRowHeight(row, 36)

                except Exception as row_error:
                    logger.error(
                        f"Error filling row {row} for customer {cust.id}: {row_error}"
                    )
                    continue

            # 6) Resize columns for a neat look
            self.customer_table.resizeColumnsToContents()

            # 7) Re-enable sorting
            self.customer_table.setSortingEnabled(True)

            # 8) Restore the previous sort (column + order), so if the user
            #    had it sorted by column #2 descending, it stays that way.
            self.customer_table.sortItems(prev_col, prev_order)

            logger.debug(
                f"(populate_customer_table) Finished with {len(unique_customers)} rows"
            )

        except Exception as e:
            logger.error(f"Error populating customer table: {str(e)}")
            raise UIException(f"Failed to populate customer table: {str(e)}")

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def edit_customer_by_id(self, customer_id: int):
        """
        Edit a customer identified by customer_id.
        This approach always re-fetches from DB, ensuring correct data
        even if the table was sorted or partially re-drawn.
        """
        logger.debug(f"[edit_customer_by_id] Editing customer with ID={customer_id}")
        try:
            customer = self.customer_service.get_customer(customer_id)
            if not customer:
                show_error_message(
                    "Error", f"No se encontró el cliente con ID={customer_id}"
                )
                return

            dialog = EditCustomerDialog(customer, self)
            if dialog.exec():
                # Get the new values
                new_identifier_9 = dialog.identifier_9_input.text().strip()
                new_identifier_3or4 = (
                    dialog.identifier_3or4_input.text().strip() or None
                )
                # Changed to handle empty string case
                new_name = dialog.name_input.text().strip() or None

                # Validate the name before updating
                if new_name:
                    try:
                        validate_string(new_name, max_length=50)
                    except ValidationException as e:
                        show_error_message("Error de Validación", str(e))
                        return

                # Update the customer
                self.customer_service.update_customer(
                    customer.id,
                    identifier_9=new_identifier_9,
                    name=new_name,
                    identifier_3or4=new_identifier_3or4,
                )

                self.load_customers()
                show_info_message("Éxito", "Cliente actualizado exitosamente.")
                self.customer_updated.emit()
                logger.info(f"Customer updated successfully: ID {customer.id}")
        except Exception as e:
            logger.error(
                f"[edit_customer_by_id] Error updating customer ID={customer_id}: {str(e)}"
            )
            raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def delete_customer_by_id(self, customer_id: int):
        """
        Delete a customer identified by customer_id.
        """
        logger.debug(f"[delete_customer_by_id] Deleting customer with ID={customer_id}")
        try:
            customer = self.customer_service.get_customer(customer_id)
            if not customer:
                raise ValidationException(
                    f"Cliente con ID {customer_id} no encontrado."
                )

            display_name = customer.get_display_name()
            is_active = customer.is_active
            action_text = "archivar" if is_active else "restaurar"
            title_text = "Archivar Cliente" if is_active else "Restaurar Cliente"
            reply = QMessageBox.question(
                self,
                title_text,
                f"¿Está seguro que desea {action_text} al cliente {display_name}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                if is_active:
                    self.customer_service.delete_customer(customer_id)
                    show_info_message("Éxito", "Cliente archivado exitosamente.")
                else:
                    self.customer_service.restore_customer(customer_id)
                    show_info_message("Éxito", "Cliente restaurado exitosamente.")
                self.load_customers()
                self.customer_updated.emit()
                logger.info(
                    "Customer status updated",
                    extra={"customer_id": customer_id, "is_active": not is_active},
                )
        except Exception as e:
            logger.error(
                f"[delete_customer_by_id] Error deleting customer ID={customer_id}: {str(e)}"
            )
            raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def add_customer(self):
        dialog = EditCustomerDialog(None, self)
        if dialog.exec():
            try:
                customer_id = self.customer_service.create_customer(
                    identifier_9=dialog.identifier_9_input.text().strip(),
                    name=dialog.name_input.text().strip() or None,
                    identifier_3or4=dialog.identifier_3or4_input.text().strip() or None,
                )
                if customer_id is not None:
                    self.load_customers()
                    show_info_message("Éxito", "Cliente agregado exitosamente.")
                    self.customer_updated.emit()
                    logger.info(f"Customer added successfully: ID {customer_id}")
                else:
                    raise DatabaseException("Error al agregar cliente.")
            except Exception as e:
                logger.error(f"Error adding customer: {str(e)}")
                raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def edit_customer(self, customer: Optional[Customer]):
        """
        Edit a customer's info (9-digit, 3/4-digit, name).
        Updates DB, then reloads the table.
        """
        if customer is None:
            raise ValidationException("Ningún cliente seleccionado para editar.")

        logger.debug(
            f"[edit_customer] Starting edit for Customer ID={customer.id}, current name='{customer.name}'"
        )

        dialog = EditCustomerDialog(customer, self)
        if dialog.exec():
            try:
                new_name = dialog.name_input.text().strip()
                # If user typed nothing, keep old name
                if not new_name:
                    new_name = customer.name
                    logger.debug(
                        f"[edit_customer] User left name blank; reusing old name='{new_name}'"
                    )

                self.customer_service.update_customer(
                    customer.id,
                    identifier_9=dialog.identifier_9_input.text().strip(),
                    name=new_name,
                    identifier_3or4=dialog.identifier_3or4_input.text().strip() or None,
                )

                logger.debug(
                    f"[edit_customer] Done updating DB for ID={customer.id}, calling load_customers() next"
                )

                self.load_customers()

                show_info_message("Éxito", "Cliente actualizado exitosamente.")
                self.customer_updated.emit()
                logger.info(f"Customer updated successfully: ID {customer.id}")

            except Exception as e:
                logger.error(
                    f"[edit_customer] Error updating customer ID={customer.id}: {str(e)}"
                )
                raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def delete_customer(self, customer: Optional[Customer]):
        if customer is None:
            raise ValidationException("Ningún cliente seleccionado para eliminar.")

        display_name = customer.get_display_name()
        is_active = customer.is_active
        action_text = "archivar" if is_active else "restaurar"
        title_text = "Archivar Cliente" if is_active else "Restaurar Cliente"
        reply = QMessageBox.question(
            self,
            title_text,
            f"¿Está seguro que desea {action_text} al cliente {display_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if is_active:
                    self.customer_service.delete_customer(customer.id)
                    show_info_message("Éxito", "Cliente archivado exitosamente.")
                else:
                    self.customer_service.restore_customer(customer.id)
                    show_info_message("Éxito", "Cliente restaurado exitosamente.")
                self.load_customers()
                self.customer_updated.emit()
                logger.info(
                    "Customer status updated",
                    extra={"customer_id": customer.id, "is_active": not is_active},
                )
            except Exception as e:
                logger.error(f"Error updating customer status: {str(e)}")
                raise

    @ui_operation(show_dialog=True)
    @handle_exceptions(
        ValidationException, DatabaseException, UIException, show_dialog=True
    )
    def search_customers(self):
        search_term = self.search_input.text().strip()
        search_term = validate_string(search_term, max_length=50)
        if search_term:
            try:
                customers = self.customer_service.search_customers(
                    search_term,
                    active_only=not self.show_archived_checkbox.isChecked(),
                )
                self.populate_customer_table(customers)
                logger.info(f"Customer search performed: '{search_term}'")
            except Exception as e:
                logger.error(f"Error searching customers: {str(e)}")
                raise
        else:
            self.load_customers()

    def show_context_menu(self, position):
        row = self.customer_table.rowAt(position.y())
        if row < 0:
            return

        customer_id = self.customer_table.item(row, 0).text()
        customer = self.customer_service.get_customer(int(customer_id))

        if customer is None:
            show_error_message("Error", f"No se encontró cliente con ID {customer_id}.")
            return

        menu = QMenu()
        edit_action = menu.addAction("Editar")
        delete_label = "Eliminar" if customer.is_active else "Restaurar"
        delete_action = menu.addAction(delete_label)
        action = menu.exec(self.customer_table.mapToGlobal(position))
        if action == edit_action:
            self.edit_customer(customer)
        elif action == delete_action:
            self.delete_customer(customer)

    def refresh(self):
        self.load_customers()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            selected_rows = self.customer_table.selectionModel().selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                customer_id = int(self.customer_table.item(row, 0).text())
                customer = self.customer_service.get_customer(customer_id)
                if customer:
                    self.delete_customer(customer)
        else:
            super().keyPressEvent(event)
