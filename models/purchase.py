from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime
from utils.exceptions import ValidationException
#from utils.decorators import validate_input


@dataclass
class PurchaseItem:
    id: int
    purchase_id: int
    product_id: int
    quantity: int
    price: float

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "PurchaseItem":
        return cls(
            id=row["id"],
            purchase_id=row["purchase_id"],
            product_id=row["product_id"],
            quantity=row["quantity"],
            price=float(row["price"]),
        )

    def total_price(self) -> float:
        return round(self.quantity * self.price, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "purchase_id": self.purchase_id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "price": self.price,
            "total_price": self.total_price(),
        }


@dataclass
class Purchase:
    id: int
    supplier: str
    date: datetime
    items: List[PurchaseItem] = field(default_factory=list)
    _total_amount: float = field(init=False, default=0)

    def __post_init__(self):
        self.recalculate_total()

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Purchase":
        return cls(
            id=row["id"],
            supplier=row["supplier"],
            date=datetime.fromisoformat(row["date"]),
        )

    #@validate_input(show_dialog=True)
    def add_item(self, item: PurchaseItem) -> None:
        self.items.append(item)
        self._total_amount += item.total_price()

    #@validate_input(show_dialog=True)
    def remove_item(self, item_id: int) -> None:
        item = next((item for item in self.items if item.id == item_id), None)
        if item:
            self.items.remove(item)
            self._total_amount -= item.total_price()
        else:
            raise ValidationException(
                f"Item with id {item_id} not found in the purchase"
            )

    def recalculate_total(self) -> None:
        self._total_amount = sum(item.total_price() for item in self.items)

    @property
    def total_amount(self) -> float:
        return round(self._total_amount, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "supplier": self.supplier,
            "date": self.date.isoformat(),
            "total_amount": self.total_amount,
            "items": [item.to_dict() for item in self.items],
        }

    def __str__(self) -> str:
        return f"Purchase(id={self.id}, supplier='{self.supplier}', date='{self.date.isoformat()}', total_amount={self.total_amount:.2f})"

    @staticmethod
    #@validate_input(show_dialog=True)
    def validate_supplier(supplier: str) -> None:
        if not supplier or len(supplier.strip()) == 0:
            raise ValidationException("Supplier name cannot be empty")
        if len(supplier) > 100:
            raise ValidationException("Supplier name cannot exceed 100 characters")

    @staticmethod
    #@validate_input(show_dialog=True)
    def validate_date(date: datetime) -> None:
        if date > datetime.now():
            raise ValidationException("Purchase date cannot be in the future")
