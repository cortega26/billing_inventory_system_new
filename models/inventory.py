from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Inventory:
    id: int
    product_id: int
    quantity: int

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Inventory':
        return cls(
            id=row['id'],
            product_id=row['product_id'],
            quantity=row['quantity']
        )

    def update_quantity(self, change: int) -> None:
        """
        Update the quantity of the inventory item.
        
        Args:
            change (int): The amount to change the quantity by. 
                          Positive for increase, negative for decrease.
        
        Raises:
            ValueError: If the resulting quantity would be negative.
        """
        new_quantity = self.quantity + change
        if new_quantity < 0:
            raise ValueError(f"Cannot decrease quantity by {abs(change)}. Current quantity: {self.quantity}")
        self.quantity = new_quantity

    def set_quantity(self, new_quantity: int) -> None:
        """
        Set the quantity of the inventory item to a specific value.
        
        Args:
            new_quantity (int): The new quantity to set.
        
        Raises:
            ValueError: If the new quantity is negative.
        """
        if new_quantity < 0:
            raise ValueError("Inventory quantity cannot be negative")
        self.quantity = new_quantity

    def __str__(self) -> str:
        return f"Inventory(id={self.id}, product_id={self.product_id}, quantity={self.quantity})"