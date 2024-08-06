from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime
from utils.exceptions import ValidationException
from utils.decorators import validate_input

@dataclass
class SaleItem:
    id: int
    sale_id: int
    product_id: int
    quantity: int
    unit_price: float

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'SaleItem':
        return cls(
            id=row['id'],
            sale_id=row['sale_id'],
            product_id=row['product_id'],
            quantity=row['quantity'],
            unit_price=float(row['price'])
        )

    def total_price(self) -> float:
        return round(self.quantity * self.unit_price, 2)

@dataclass
class Sale:
    id: int
    customer_id: int
    date: datetime
    total_amount: float
    items: List[SaleItem] = field(default_factory=list)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Sale':
        return cls(
            id=row['id'],
            customer_id=row['customer_id'],
            date=datetime.fromisoformat(row['date']),
            total_amount=float(row['total_amount'])
        )

    @validate_input(show_dialog=True)
    def add_item(self, item: SaleItem) -> None:
        self.items.append(item)
        self.recalculate_total()

    @validate_input(show_dialog=True)
    def remove_item(self, item_id: int) -> None:
        self.items = [item for item in self.items if item.id != item_id]
        self.recalculate_total()

    def recalculate_total(self) -> None:
        self.total_amount = sum(item.total_price() for item in self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'date': self.date.isoformat(),
            'total_amount': self.total_amount,
            'items': [item.__dict__ for item in self.items]
        }

    def __str__(self) -> str:
        return (f"Sale(id={self.id}, customer_id={self.customer_id}, "
                f"date='{self.date.isoformat()}', total_amount={self.total_amount:.2f})")

    @staticmethod
    @validate_input(show_dialog=True)
    def validate_customer_id(customer_id: int) -> None:
        if not isinstance(customer_id, int) or customer_id <= 0:
            raise ValidationException("Invalid customer ID")

    @staticmethod
    @validate_input(show_dialog=True)
    def validate_date(date: datetime) -> None:
        if date > datetime.now():
            raise ValidationException("Sale date cannot be in the future")

    @validate_input(show_dialog=True)
    def update_date(self, new_date: datetime) -> None:
        self.validate_date(new_date)
        self.date = new_date

    @validate_input(show_dialog=True)
    def update_customer(self, new_customer_id: int) -> None:
        self.validate_customer_id(new_customer_id)
        self.customer_id = new_customer_id
