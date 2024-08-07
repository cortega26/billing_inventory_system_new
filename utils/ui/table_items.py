from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt
from typing import Union, Callable, Any


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, value: Union[int, float]):
        super().__init__(str(value))
        self.value = value
        self.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    def __lt__(self, other: "NumericTableWidgetItem") -> bool:
        if isinstance(other, NumericTableWidgetItem):
            return self.value < other.value
        return super().__lt__(other)


class PercentageTableWidgetItem(QTableWidgetItem):
    def __init__(self, value: Union[int, float, None]):
        display_value = (
            f"{value:.2f}%".replace(".", ",") if value is not None else "N/A"
        )
        super().__init__(display_value)
        self.value = (
            value if value is not None else float("-inf")
        )  # Use -inf for N/A to sort it at the bottom
        self.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    def __lt__(self, other: "PercentageTableWidgetItem") -> bool:
        if isinstance(other, PercentageTableWidgetItem):
            return self.value < other.value
        return super().__lt__(other)


class PriceTableWidgetItem(QTableWidgetItem):
    def __init__(
        self,
        value: Union[int, float, None],
        format_func: Callable[[Union[int, float]], str],
    ):
        display_value = format_func(value) if value is not None else "N/A"
        super().__init__(display_value)
        self.value = (
            value if value is not None else float("-inf")
        )  # Use -inf for N/A to sort it at the bottom
        self.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    def __lt__(self, other: "PriceTableWidgetItem") -> bool:
        if isinstance(other, PriceTableWidgetItem):
            return self.value < other.value
        return super().__lt__(other)


class DateTableWidgetItem(QTableWidgetItem):
    def __init__(self, date: Any, format_str: str = "%Y-%m-%d"):
        super().__init__(date.strftime(format_str) if date else "")
        self.date = date
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def __lt__(self, other: "DateTableWidgetItem") -> bool:
        if isinstance(other, DateTableWidgetItem):
            if self.date and other.date:
                return self.date < other.date
            return bool(self.date) < bool(other.date)  # None dates sort last
        return super().__lt__(other)


class CheckboxTableWidgetItem(QTableWidgetItem):
    def __init__(self, checked: bool = False):
        super().__init__()
        self.setFlags(self.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        self.setCheckState(
            Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        )
