from dataclasses import dataclass
from typing import Dict, Any, Optional
from utils.exceptions import ValidationException

@dataclass
class Inventory:
    id: int
    product_id: int
    quantity: float
    min_stock_level: float = 0
    max_stock_level: Optional[float] = None

    def __post_init__(self):
        self.validate_quantity(self.quantity)
        self.validate_stock_levels(self.min_stock_level, self.max_stock_level)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Inventory":
        return cls(
            id=row["id"],
            product_id=row["product_id"],
            quantity=float(row["quantity"]),
            min_stock_level=float(row.get("min_stock_level", 0)),
            max_stock_level=float(row["max_stock_level"]) if row.get("max_stock_level") is not None else None,
        )

    @staticmethod
    def validate_quantity(quantity: float) -> None:
        if quantity < 0:
            raise ValidationException("Quantity cannot be negative")

    @staticmethod
    def validate_stock_levels(min_level: float, max_level: Optional[float]) -> None:
        if min_level < 0:
            raise ValidationException("Minimum stock level cannot be negative")
        if max_level is not None:
            if max_level <= min_level:
                raise ValidationException("Maximum stock level must be greater than minimum stock level")

    def update_quantity(self, change: float) -> None:
        new_quantity = self.quantity + change
        if new_quantity < 0:
            raise ValidationException(
                f"Cannot decrease quantity by {abs(change)}. Current quantity: {self.quantity}"
            )
        if self.max_stock_level is not None and new_quantity > self.max_stock_level:
            raise ValidationException(
                f"Cannot increase quantity above max stock level of {self.max_stock_level}"
            )
        self.quantity = new_quantity

    def set_quantity(self, new_quantity: float) -> None:
        self.validate_quantity(new_quantity)
        if self.max_stock_level is not None and new_quantity > self.max_stock_level:
            raise ValidationException(
                f"Cannot set quantity above max stock level of {self.max_stock_level}"
            )
        self.quantity = new_quantity

    def set_stock_levels(self, min_level: float, max_level: Optional[float] = None) -> None:
        self.validate_stock_levels(min_level, max_level)
        self.min_stock_level = min_level
        self.max_stock_level = max_level

    def is_low_stock(self) -> bool:
        return self.quantity <= self.min_stock_level

    def is_out_of_stock(self) -> bool:
        return self.quantity == 0

    def available_quantity(self) -> float:
        return max(0, self.quantity)

    def __str__(self) -> str:
        return (
            f"Inventory(id={self.id}, product_id={self.product_id}, "
            f"quantity={self.quantity}, min_stock_level={self.min_stock_level}, "
            f"max_stock_level={self.max_stock_level})"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "min_stock_level": self.min_stock_level,
            "max_stock_level": self.max_stock_level,
        }
