from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt

class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, value):
        super().__init__(str(value))
        self.value = value

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.value < other.value
        return self.text() < other.text()

class PercentageTableWidgetItem(QTableWidgetItem):
    def __init__(self, value):
        super().__init__(f"{value:.2f}%".replace('.', ',') if value is not None else "N/A")
        self.value = value if value is not None else -1  # Use -1 for N/A to sort it at the bottom

    def __lt__(self, other):
        if isinstance(other, PercentageTableWidgetItem):
            return self.value < other.value
        return self.text() < other.text()

class PriceTableWidgetItem(NumericTableWidgetItem):
    def __init__(self, value, format_func):
        super().__init__(value if value is not None else -1)
        self.setData(Qt.ItemDataRole.DisplayRole, format_func(value) if value is not None else "N/A")
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)