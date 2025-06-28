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


class DepartmentIdentifierTableWidgetItem(QTableWidgetItem):
    """Custom table item for department identifiers (3 or 4 digits)"""
    def __init__(self, value: str):
        # Handle empty or N/A values
        if not value or value == "N/A":
            # Use a very high number for sorting "N/A" at the end
            self.sort_key = float('inf')
            display_value = "N/A"
        else:
            # For actual department numbers, use numeric value for sorting
            try:
                self.sort_key = int(value)
                display_value = value
            except ValueError:
                self.sort_key = float('inf')
                display_value = value

        super().__init__(display_value)
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def __lt__(self, other: "DepartmentIdentifierTableWidgetItem") -> bool:
        if not isinstance(other, DepartmentIdentifierTableWidgetItem):
            return super().__lt__(other)
        
        # Both are valid numbers - sort by length first, then by value
        if isinstance(self.sort_key, int) and isinstance(other.sort_key, int):
            self_str = str(self.sort_key)
            other_str = str(other.sort_key)
            
            # If lengths are different, shorter numbers come first
            if len(self_str) != len(other_str):
                return len(self_str) < len(other_str)
            
            # If lengths are the same, sort by numeric value
            return self.sort_key < other.sort_key
            
        # Handle "N/A" and invalid values
        return self.sort_key < other.sort_key
