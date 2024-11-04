from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime
from utils.exceptions import ValidationException
from utils.system.logger import logger

@dataclass
class PurchaseItem:
    id: int
    purchase_id: int
    product_id: int
    quantity: float  # Allows up to 3 decimal places
    price: int      # Chilean Pesos - always integer

    def __post_init__(self):
        self.validate_quantity(self.quantity)
        self.validate_price(self.price)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "PurchaseItem":
        return cls(
            id=row["id"],
            purchase_id=row["purchase_id"],
            product_id=row["product_id"],
            quantity=float(row["quantity"]),
            price=int(row["price"]),
        )

    @staticmethod
    def validate_quantity(quantity: float) -> None:
        """
        Validate that the quantity is positive and has max 3 decimal places.
        """
        if quantity <= 0:
            raise ValidationException("Quantity must be positive")
        
        # Check decimal places (convert to string to check actual decimal places)
        decimal_str = str(quantity).split('.')
        if len(decimal_str) > 1 and len(decimal_str[1]) > 3:
            raise ValidationException("Quantity cannot have more than 3 decimal places")

    @staticmethod
    def validate_price(price: int) -> None:
        """
        Validate that the price is a positive integer.
        """
        if not isinstance(price, int):
            raise ValidationException("Price must be an integer")
        if price < 0:
            raise ValidationException("Price cannot be negative")

    def total_price(self) -> int:
        """
        Calculate total price ensuring integer result for Chilean Pesos.
        """
        return int(round(self.quantity * self.price))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "purchase_id": self.purchase_id,
            "product_id": self.product_id,
            "quantity": round(self.quantity, 3),  # Always round to 3 decimal places
            "price": self.price,
            "total_price": self.total_price(),
        }

@dataclass
class Purchase:
    id: int
    supplier: str
    date: datetime
    items: List[PurchaseItem] = field(default_factory=list)
    _total_amount: int = field(init=False, default=0)  # Chilean Pesos - always integer

    def __post_init__(self):
        self.validate_supplier(self.supplier)
        self.validate_date(self.date)
        self.recalculate_total()

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Purchase":
        return cls(
            id=row["id"],
            supplier=row["supplier"],
            date=datetime.fromisoformat(row["date"]),
        )

    @staticmethod
    def validate_supplier(supplier: str) -> None:
        """
        Validate supplier name.
        """
        if not supplier or len(supplier.strip()) == 0:
            raise ValidationException("Supplier name cannot be empty")
        if len(supplier) > 100:
            raise ValidationException("Supplier name cannot exceed 100 characters")

    @staticmethod
    def validate_date(date: datetime) -> None:
        """
        Validate purchase date is not in the future.
        """
        if date > datetime.now():
            raise ValidationException("Purchase date cannot be in the future")

    def add_item(self, item: PurchaseItem) -> None:
        """
        Add a purchase item and update total.
        """
        self.items.append(item)
        self._total_amount += item.total_price()

    def remove_item(self, item_id: int) -> None:
        """
        Remove a purchase item and update total.
        """
        item = next((item for item in self.items if item.id == item_id), None)
        if item:
            self.items.remove(item)
            self._total_amount -= item.total_price()
        else:
            raise ValidationException(f"Item with id {item_id} not found in the purchase")

    def recalculate_total(self) -> None:
        """
        Recalculate total amount ensuring integer result.
        """
        try:
            self._total_amount = sum(item.total_price() for item in self.items)
        except Exception as e:
            logger.error(f"Error recalculating total: {str(e)}")
            raise ValidationException("Error calculating total amount")

    @property
    def total_amount(self) -> int:
        """
        Get the total amount as integer (Chilean Pesos).
        """
        return self._total_amount

    def update_supplier(self, new_supplier: str) -> None:
        """
        Update supplier name with validation.
        """
        self.validate_supplier(new_supplier)
        self.supplier = new_supplier

    def update_date(self, new_date: datetime) -> None:
        """
        Update purchase date with validation.
        """
        self.validate_date(new_date)
        self.date = new_date

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert purchase to dictionary representation.
        """
        return {
            "id": self.id,
            "supplier": self.supplier,
            "date": self.date.isoformat(),
            "total_amount": self.total_amount,
            "items": [item.to_dict() for item in self.items],
        }

    def __str__(self) -> str:
        """
        String representation of the purchase.
        """
        return (
            f"Purchase(id={self.id}, supplier='{self.supplier}', "
            f"date='{self.date.isoformat()}', "
            f"total_amount={self.total_amount})"
        )

    @staticmethod
    def validate_items(items: List[PurchaseItem]) -> None:
        """
        Validate all items in a purchase.
        """
        if not items:
            raise ValidationException("Purchase must have at least one item")
        for item in items:
            if not isinstance(item, PurchaseItem):
                raise ValidationException("Invalid item type")
            item.validate_quantity(item.quantity)
            item.validate_price(item.price)

    def verify_totals(self) -> bool:
        """
        Verify that all totals are correctly calculated.
        """
        expected_total = sum(item.total_price() for item in self.items)
        return self._total_amount == expected_total

    def add_items(self, items: List[PurchaseItem]) -> None:
        """
        Add multiple items at once.
        """
        self.validate_items(items)
        for item in items:
            self.add_item(item)

    def get_item_count(self) -> int:
        """
        Get the total number of items.
        """
        return len(self.items)

    def get_total_quantity(self) -> float:
        """
        Get the total quantity of all items, rounded to 3 decimal places.
        """
        return round(sum(item.quantity for item in self.items), 3)
