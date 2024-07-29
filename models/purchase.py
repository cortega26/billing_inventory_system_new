from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime

@dataclass
class PurchaseItem:
    id: int
    purchase_id: int
    product_id: int
    quantity: int
    price: float

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'PurchaseItem':
        return cls(
            id=row['id'],
            purchase_id=row['purchase_id'],
            product_id=row['product_id'],
            quantity=row['quantity'],
            price=float(row['price'])
        )

    def total_price(self) -> float:
        return self.quantity * self.price

@dataclass
class Purchase:
    id: int
    supplier: str
    date: datetime
    total_amount: float
    items: List[PurchaseItem] = field(default_factory=list)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Purchase':
        return cls(
            id=row['id'],
            supplier=row['supplier'],
            date=datetime.fromisoformat(row['date']),
            total_amount=float(row['total_amount'])
        )

    def add_item(self, item: PurchaseItem) -> None:
        self.items.append(item)
        self.recalculate_total()

    def remove_item(self, item_id: int) -> None:
        self.items = [item for item in self.items if item.id != item_id]
        self.recalculate_total()

    def recalculate_total(self) -> None:
        self.total_amount = sum(item.total_price() for item in self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'supplier': self.supplier,
            'date': self.date.isoformat(),
            'total_amount': self.total_amount,
            'items': [item.__dict__ for item in self.items]
        }

    def __str__(self) -> str:
        return (f"Purchase(id={self.id}, supplier='{self.supplier}', "
                f"date='{self.date.isoformat()}', total_amount={self.total_amount:.2f})")

    @staticmethod
    def validate_supplier(supplier: str) -> None:
        if not supplier or len(supplier.strip()) == 0:
            raise ValueError("Supplier name cannot be empty")
        if len(supplier) > 100:
            raise ValueError("Supplier name cannot exceed 100 characters")

    @staticmethod
    def validate_date(date: datetime) -> None:
        if date > datetime.now():
            raise ValueError("Purchase date cannot be in the future")