from typing import Dict

class Inventory:
    def __init__(self, id: int, product_id: int, quantity: int):
        self.id = id
        self.product_id = product_id
        self.quantity = quantity

    @classmethod
    def from_row(cls, row: Dict[str, int]) -> 'Inventory':
        return cls(
            id=row['id'],
            product_id=row['product_id'],
            quantity=row['quantity']
        )

    def __repr__(self) -> str:
        return f"Inventory(id={self.id}, product_id={self.product_id}, quantity={self.quantity})"

    def update_quantity(self, change: int) -> None:
        self.quantity += change
        if self.quantity < 0:
            raise ValueError("Inventory quantity cannot be negative")
