from PySide6.QtWidgets import QTableWidget
from PySide6.QtCore import QSettings
from config import COMPANY_NAME, APP_NAME
from typing import Union, Any

class ColumnResizer:
    def __init__(self, table_widget: QTableWidget, settings_prefix: str):
        self.table_widget = table_widget
        self.settings_prefix = settings_prefix
        self.settings = QSettings(COMPANY_NAME, APP_NAME)

        self.restore_column_widths()
        self.table_widget.horizontalHeader().sectionResized.connect(self.on_section_resized)

    def restore_column_widths(self):
        for i in range(self.table_widget.columnCount()):
            width = self.get_int_setting(f"{self.settings_prefix}/column_{i}_width")
            if width is not None:
                self.table_widget.setColumnWidth(i, width)

    def save_column_widths(self):
        for i in range(self.table_widget.columnCount()):
            width = self.table_widget.columnWidth(i)
            self.settings.setValue(f"{self.settings_prefix}/column_{i}_width", width)

    def on_section_resized(self, logical_index: int, old_size: int, new_size: int):
        self.save_column_widths()

    def get_int_setting(self, key: str) -> Union[int, None]:
        value: Any = self.settings.value(key)
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None