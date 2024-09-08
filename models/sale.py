from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.exceptions import ValidationException


@dataclass
class SaleItem:
    id: int
    sale_id: int
    product_id: int
    quantity: float
    unit_price: int
    profit: int
    product_name: Optional[str] = None

    def __post_init__(self):
        self.validate_quantity(self.quantity)
        self.validate_price(self.unit_price)
        self.validate_profit(self.profit)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "SaleItem":
        return cls(
            id=row["id"],
            sale_id=row["sale_id"],
            product_id=row["product_id"],
            quantity=float(row["quantity"]),
            unit_price=int(row["price"]),
            profit=int(row["profit"]),
            product_name=row.get("product_name")
        )

    @staticmethod
    def validate_quantity(quantity: float) -> None:
        if quantity <= 0:
            raise ValidationException("Quantity must be positive")

    @staticmethod
    def validate_price(price: int) -> None:
        if price < 0:
            raise ValidationException("Price cannot be negative")

    @staticmethod
    def validate_profit(profit: int) -> None:
        if profit < 0:
            raise ValidationException("Profit cannot be negative")

    def total_price(self) -> int:
        return round(self.quantity * self.unit_price)

    def calculate_profit(self, cost_price: int) -> None:
        self.profit = int((self.unit_price - cost_price) * self.quantity)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sale_id": self.sale_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "product_name": self.product_name,
            "total_price": self.total_price(),
            "profit": self.profit,
        }

@dataclass
class Sale:
    id: int
    customer_id: int
    date: datetime
    total_amount: int
    total_profit: int
    receipt_id: Optional[str] = None
    items: List[SaleItem] = field(default_factory=list)

    def __post_init__(self):
        self.validate_customer_id(self.customer_id)
        self.validate_date(self.date)
        self.validate_total_amount(self.total_amount)
        self.validate_total_profit(self.total_profit)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Sale":
        return cls(
            id=row["id"],
            customer_id=row["customer_id"],
            date=datetime.fromisoformat(row["date"]),
            total_amount=int(row["total_amount"] or 0),
            total_profit=int(row["total_profit"] or 0),
            receipt_id=row.get("receipt_id")
        )

    @staticmethod
    def validate_customer_id(customer_id: int) -> None:
        if not isinstance(customer_id, int) or customer_id <= 0:
            raise ValidationException("Invalid customer ID")

    @staticmethod
    def validate_date(date: datetime) -> None:
        if date > datetime.now():
            raise ValidationException("Sale date cannot be in the future")

    @staticmethod
    def validate_total_amount(total_amount: int) -> None:
        if total_amount < 0:
            raise ValidationException("Total amount cannot be negative")

    @staticmethod
    def validate_total_profit(total_profit: int) -> None:
        if total_profit < 0:
            raise ValidationException("Total profit cannot be negative")

    def add_item(self, item: SaleItem) -> None:
        self.items.append(item)
        self.recalculate_total()

    def remove_item(self, item_id: int) -> None:
        self.items = [item for item in self.items if item.id != item_id]
        self.recalculate_total()

    def recalculate_total(self) -> None:
        self.total_amount = sum(item.total_price() for item in self.items)
        self.total_profit = sum(item.profit for item in self.items)

    def update_date(self, new_date: datetime) -> None:
        self.validate_date(new_date)
        self.date = new_date

    def update_customer(self, new_customer_id: int) -> None:
        self.validate_customer_id(new_customer_id)
        self.customer_id = new_customer_id

    def update_receipt_id(self, new_receipt_id: Optional[str]) -> None:
        self.receipt_id = new_receipt_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "date": self.date.isoformat(),
            "total_amount": self.total_amount,
            "total_profit": self.total_profit,
            "receipt_id": self.receipt_id,
            "items": [item.to_dict() for item in self.items],
        }

    def __str__(self) -> str:
        return (
            f"Sale(id={self.id}, customer_id={self.customer_id}, "
            f"date='{self.date.isoformat()}', total_amount={self.total_amount}, "
            f"total_profit={self.total_profit}, receipt_id='{self.receipt_id}')"
        )
