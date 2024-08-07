from PySide6.QtWidgets import QTableWidget, QHeaderView
from PySide6.QtCore import QSettings, QObject, Slot
from typing import Dict, Optional
from config import COMPANY_NAME, APP_NAME


class ColumnResizer(QObject):
    def __init__(self, table_widget: QTableWidget, settings_prefix: str):
        super().__init__()
        self.table_widget = table_widget
        self.settings_prefix = settings_prefix
        self.settings = QSettings(COMPANY_NAME, APP_NAME)
        self.column_widths: Dict[int, int] = {}

        self.restore_column_widths()
        self.table_widget.horizontalHeader().sectionResized.connect(
            self.on_section_resized
        )

    def restore_column_widths(self) -> None:
        """Restore column widths from settings."""
        for i in range(self.table_widget.columnCount()):
            width = self.get_setting(f"{self.settings_prefix}/column_{i}_width")
            if width is not None:
                self.table_widget.setColumnWidth(i, width)
                self.column_widths[i] = width

    def save_column_widths(self) -> None:
        """Save current column widths to settings."""
        for i, width in self.column_widths.items():
            self.settings.setValue(f"{self.settings_prefix}/column_{i}_width", width)

    @Slot(int, int, int)
    def on_section_resized(self, logical_index: int, _: int, new_size: int) -> None:
        """
        Slot to handle column resize events.

        Args:
            logical_index (int): The index of the resized column.
            _ (int): The old size (unused).
            new_size (int): The new size of the column.
        """
        self.column_widths[logical_index] = new_size
        self.save_column_widths()

    def get_setting(self, key: str) -> Optional[int]:
        """
        Retrieve a setting value and convert it to an integer.

        Args:
            key (str): The settings key to retrieve.

        Returns:
            Optional[int]: The setting value as an integer, or None if not found or invalid.
        """
        value = self.settings.value(key)
        if value is None:
            return None
        try:
            return int(value)  # type: ignore
        except (ValueError, TypeError):
            return None

    def apply_default_widths(self, default_widths: Dict[int, int]) -> None:
        """
        Apply default widths to columns that haven't been resized by the user.

        Args:
            default_widths (Dict[int, int]): A dictionary mapping column indices to their default widths.
        """
        for col, width in default_widths.items():
            if col not in self.column_widths:
                self.table_widget.setColumnWidth(col, width)
                self.column_widths[col] = width
        self.save_column_widths()

    def reset_to_default(self, default_widths: Dict[int, int]) -> None:
        """
        Reset all column widths to the provided default values.

        Args:
            default_widths (Dict[int, int]): A dictionary mapping column indices to their default widths.
        """
        self.column_widths.clear()
        for col, width in default_widths.items():
            self.table_widget.setColumnWidth(col, width)
            self.column_widths[col] = width
        self.save_column_widths()

    def adjust_to_contents(self, padding: int = 20) -> None:
        """
        Adjust all column widths to fit their contents.

        Args:
            padding (int): Additional padding to add to each column width.
        """
        self.table_widget.resizeColumnsToContents()
        for i in range(self.table_widget.columnCount()):
            width = self.table_widget.columnWidth(i) + padding
            self.table_widget.setColumnWidth(i, width)
            self.column_widths[i] = width
        self.save_column_widths()
