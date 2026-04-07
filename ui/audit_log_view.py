import csv
import json
from typing import Any

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.audit_service import AuditService
from utils.decorators import handle_exceptions, ui_operation
from utils.exceptions import DatabaseException, UIException
from utils.helpers import create_table, show_info_message, truncate_string
from utils.system.logger import logger


class AuditLogView(QWidget):
    def __init__(self):
        super().__init__()
        self.audit_service = AuditService()
        self.current_entries: list[dict[str, Any]] = []
        self.setup_ui()
        self.refresh()

    @handle_exceptions(UIException, show_dialog=True)
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addLayout(self._build_filters_layout())

        self.audit_table = create_table(
            [
                "ID",
                "Fecha",
                "Operación",
                "Entidad",
                "ID Entidad",
                "Actor",
                "Resumen",
            ]
        )
        self.audit_table.itemSelectionChanged.connect(self.show_selected_entry_details)
        layout.addWidget(self.audit_table)

        layout.addWidget(QLabel("Detalle"))
        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText(
            "Seleccione un registro para ver el payload completo."
        )
        layout.addWidget(self.detail_text)

        self.setLayout(layout)

    def _build_filters_layout(self):
        filter_layout = QGridLayout()

        self.entity_type_combo = QComboBox()
        self.entity_type_combo.addItem("Todas", None)
        for entity_type in ["sale", "purchase", "inventory", "customer", "product"]:
            self.entity_type_combo.addItem(entity_type.capitalize(), entity_type)

        self.operation_input = QLineEdit()
        self.operation_input.setPlaceholderText("Operación exacta, por ejemplo create_sale")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar en payload, actor, entidad o ID")

        self.actor_input = QLineEdit()
        self.actor_input.setPlaceholderText("Actor")

        self.date_filter_checkbox = QCheckBox("Filtrar por fecha")
        self.date_filter_checkbox.toggled.connect(self.toggle_date_filters)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-7))

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())

        self.limit_spinbox = QSpinBox()
        self.limit_spinbox.setRange(10, 1000)
        self.limit_spinbox.setSingleStep(10)
        self.limit_spinbox.setValue(200)

        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self.refresh)
        export_button = QPushButton("Exportar CSV")
        export_button.clicked.connect(self.export_current_view)

        filter_layout.addWidget(QLabel("Entidad:"), 0, 0)
        filter_layout.addWidget(self.entity_type_combo, 0, 1)
        filter_layout.addWidget(QLabel("Operación:"), 0, 2)
        filter_layout.addWidget(self.operation_input, 0, 3)
        filter_layout.addWidget(QLabel("Actor:"), 0, 4)
        filter_layout.addWidget(self.actor_input, 0, 5)

        filter_layout.addWidget(QLabel("Buscar:"), 1, 0)
        filter_layout.addWidget(self.search_input, 1, 1, 1, 3)
        filter_layout.addWidget(self.date_filter_checkbox, 1, 4)
        filter_layout.addWidget(QLabel("Límite:"), 1, 5)
        filter_layout.addWidget(self.limit_spinbox, 1, 6)

        filter_layout.addWidget(QLabel("Desde:"), 2, 0)
        filter_layout.addWidget(self.start_date, 2, 1)
        filter_layout.addWidget(QLabel("Hasta:"), 2, 2)
        filter_layout.addWidget(self.end_date, 2, 3)

        button_layout = QHBoxLayout()
        button_layout.addWidget(refresh_button)
        button_layout.addWidget(export_button)
        button_layout.addStretch()
        filter_layout.addLayout(button_layout, 2, 4, 1, 3)

        self.toggle_date_filters(False)
        return filter_layout

    def toggle_date_filters(self, enabled: bool) -> None:
        self.start_date.setEnabled(enabled)
        self.end_date.setEnabled(enabled)

    @ui_operation(show_dialog=True)
    @handle_exceptions(DatabaseException, UIException, show_dialog=True)
    def refresh(self) -> None:
        try:
            entries = self.audit_service.search_entries(
                entity_type=self.entity_type_combo.currentData(),
                operation=self._normalized_text(self.operation_input),
                actor=self._normalized_text(self.actor_input),
                search_term=self._normalized_text(self.search_input),
                start_date=(
                    self.start_date.date().toString("yyyy-MM-dd")
                    if self.date_filter_checkbox.isChecked()
                    else None
                ),
                end_date=(
                    self.end_date.date().toString("yyyy-MM-dd")
                    if self.date_filter_checkbox.isChecked()
                    else None
                ),
                limit=self.limit_spinbox.value(),
            )
            self.current_entries = entries
            self.populate_table(entries)
            logger.info("Audit log view refreshed", extra={"count": len(entries)})
        except Exception as e:
            logger.error(f"Error refreshing audit log view: {str(e)}")
            raise UIException(f"No fue posible cargar la bitácora: {str(e)}")

    def populate_table(self, entries: list[dict[str, Any]]) -> None:
        self.audit_table.setRowCount(len(entries))

        for row_index, entry in enumerate(entries):
            cells = [
                str(entry["id"]),
                entry["timestamp"],
                entry["operation"],
                entry["entity_type"],
                "" if entry["entity_id"] is None else str(entry["entity_id"]),
                entry.get("actor") or "Sistema",
                self._build_summary(entry.get("payload")),
            ]
            for column_index, value in enumerate(cells):
                self.audit_table.setItem(
                    row_index, column_index, QTableWidgetItem(value)
                )

        if entries:
            self.audit_table.selectRow(0)
            self.show_selected_entry_details()
        else:
            self.detail_text.clear()

    def show_selected_entry_details(self) -> None:
        selected_rows = self.audit_table.selectionModel().selectedRows()
        if not selected_rows:
            self.detail_text.clear()
            return

        row_index = selected_rows[0].row()
        if not 0 <= row_index < len(self.current_entries):
            self.detail_text.clear()
            return

        entry = self.current_entries[row_index]
        payload_text = self._format_payload(entry.get("payload"))
        detail = (
            f"ID: {entry['id']}\n"
            f"Fecha: {entry['timestamp']}\n"
            f"Operación: {entry['operation']}\n"
            f"Entidad: {entry['entity_type']}\n"
            f"ID entidad: {entry.get('entity_id')}\n"
            f"Actor: {entry.get('actor') or 'Sistema'}\n\n"
            f"Payload:\n{payload_text}"
        )
        self.detail_text.setPlainText(detail)

    @ui_operation(show_dialog=True)
    @handle_exceptions(UIException, show_dialog=True)
    def export_current_view(self) -> None:
        if not self.current_entries:
            show_info_message("Sin datos", "No hay registros visibles para exportar.")
            return

        default_name = f"audit_log_{QDate.currentDate().toString('yyyyMMdd')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar bitácora",
            default_name,
            "CSV Files (*.csv)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=[
                        "id",
                        "timestamp",
                        "operation",
                        "entity_type",
                        "entity_id",
                        "actor",
                        "payload",
                    ],
                )
                writer.writeheader()
                for entry in self.current_entries:
                    writer.writerow(
                        {
                            "id": entry["id"],
                            "timestamp": entry["timestamp"],
                            "operation": entry["operation"],
                            "entity_type": entry["entity_type"],
                            "entity_id": entry.get("entity_id"),
                            "actor": entry.get("actor") or "",
                            "payload": entry.get("payload") or "",
                        }
                    )
        except OSError as e:
            logger.error(f"Error exporting audit log: {str(e)}")
            raise UIException(f"No fue posible exportar la bitácora: {str(e)}")

        show_info_message("Exportación exitosa", f"Bitácora exportada en {file_path}")

    @staticmethod
    def _normalized_text(widget: QLineEdit) -> str | None:
        text = widget.text().strip()
        return text or None

    @staticmethod
    def _build_summary(payload: Any) -> str:
        if not payload:
            return "Sin payload"

        try:
            parsed_payload = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            return truncate_string(str(payload), 80)

        if isinstance(parsed_payload, dict):
            parts = [f"{key}={value}" for key, value in list(parsed_payload.items())[:3]]
            return truncate_string(", ".join(parts) if parts else "Payload vacío", 80)

        return truncate_string(str(parsed_payload), 80)

    @staticmethod
    def _format_payload(payload: Any) -> str:
        if not payload:
            return "Sin payload"

        try:
            parsed_payload = json.loads(payload)
            return json.dumps(parsed_payload, ensure_ascii=False, indent=2, sort_keys=True)
        except (TypeError, json.JSONDecodeError):
            return str(payload)