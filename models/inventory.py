from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class Inventory:
    id: int
    product_id: int
    quantity: int
    min_stock_level: int = 0
    max_stock_level: Optional[int] = None

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Inventory':
        return cls(
            id=row['id'],
            product_id=row['product_id'],
            quantity=row['quantity'],
            min_stock_level=row.get('min_stock_level', 0),
            max_stock_level=row.get('max_stock_level')
        )

    def update_quantity(self, change: int) -> None:
        new_quantity = self.quantity + change
        if new_quantity < 0:
            raise ValueError(f"Cannot decrease quantity by {abs(change)}. Current quantity: {self.quantity}")
        if self.max_stock_level is not None and new_quantity > self.max_stock_level:
            raise ValueError(f"Cannot increase quantity above max stock level of {self.max_stock_level}")
        self.quantity = new_quantity

    def set_quantity(self, new_quantity: int) -> None:
        if new_quantity < 0:
            raise ValueError("Inventory quantity cannot be negative")
        if self.max_stock_level is not None and new_quantity > self.max_stock_level:
            raise ValueError(f"Cannot set quantity above max stock level of {self.max_stock_level}")
        self.quantity = new_quantity

    def is_low_stock(self) -> bool:
        return self.quantity <= self.min_stock_level

    def is_out_of_stock(self) -> bool:
        return self.quantity == 0

    def available_quantity(self) -> int:
        return max(0, self.quantity)

    def __str__(self) -> str:
        return f"Inventory(id={self.id}, product_id={self.product_id}, quantity={self.quantity}, min_stock_level={self.min_stock_level}, max_stock_level={self.max_stock_level})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'product_id': self.product_id,
            'quantity': self.quantity,
            'min_stock_level': self.min_stock_level,
            'max_stock_level': self.max_stock_level
        }
