from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.exceptions import ValidationException
from utils.system.logger import logger

@dataclass
class SaleItem:
    id: int
    sale_id: int
    product_id: int
    quantity: float  # Allow up to 3 decimals for weight-based products
    unit_price: int  # Chilean Pesos - always integer
    profit: int      # Chilean Pesos - always integer
    product_name: Optional[str] = None

    def __post_init__(self):
        self.quantity = self.normalize_quantity(self.quantity)
        self.validate_price(self.unit_price)
        self.validate_profit(self.profit)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "SaleItem":
        try:
            return cls(
                id=int(row["id"]),
                sale_id=int(row["sale_id"]),
                product_id=int(row["product_id"]),
                quantity=float(row["quantity"]),
                unit_price=int(row["price"]),
                profit=int(row["profit"]),
                product_name=row.get("product_name")
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Error creating SaleItem from row: {row}")
            logger.error(f"Error details: {str(e)}")
            raise

    @staticmethod
    def normalize_quantity(quantity: float) -> float:
        """Normalize and validate quantity value."""
        try:
            # Convert to float if not already
            if not isinstance(quantity, (int, float)):
                quantity = float(str(quantity))
            
            if quantity <= 0:
                raise ValidationException("Quantity must be positive")
            
            # Round to 3 decimal places for weight-based products
            return round(quantity, 3)
            
        except (ValueError, TypeError):
            raise ValidationException("Invalid quantity format")

    @staticmethod
    def validate_price(price: int) -> None:
        """Validate price value."""
        if not isinstance(price, int):
            raise ValidationException("Price must be an integer")
        if price < 0:
            raise ValidationException("Price cannot be negative")

    @staticmethod
    def validate_profit(profit: int) -> None:
        """Validate profit value."""
        if not isinstance(profit, int):
            raise ValidationException("Profit must be an integer")

    def total_price(self) -> int:
        """Calculate total price and ensure integer result."""
        # Convert quantity to float and multiply by integer price
        total = float(self.quantity) * self.unit_price
        # Round to nearest integer for Chilean Pesos
        return int(round(total))

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
    total_amount: int     # Chilean Pesos - always integer
    total_profit: int     # Chilean Pesos - always integer
    receipt_id: Optional[str] = None
    items: List[SaleItem] = field(default_factory=list)

    def __post_init__(self):
        self.validate_customer_id(self.customer_id)
        self.validate_date(self.date)
        self.validate_total_amount(self.total_amount)
        self.validate_total_profit(self.total_profit)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Sale":
        try:
            return cls(
                id=int(row["id"]),
                customer_id=int(row["customer_id"]),
                date=datetime.fromisoformat(row["date"]),
                total_amount=int(row["total_amount"]),
                total_profit=int(row["total_profit"]),
                receipt_id=row.get("receipt_id")
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Error creating Sale from row: {row}")
            logger.error(f"Error details: {str(e)}")
            raise

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
        if not isinstance(total_amount, int):
            raise ValidationException("Total amount must be an integer")
        if total_amount < 0:
            raise ValidationException("Total amount cannot be negative")

    @staticmethod
    def validate_total_profit(total_profit: int) -> None:
        if not isinstance(total_profit, int):
            raise ValidationException("Total profit must be an integer")

    def add_item(self, item: SaleItem) -> None:
        self.items.append(item)
        self.recalculate_total()

    def remove_item(self, item_id: int) -> None:
        self.items = [item for item in self.items if item.id != item_id]
        self.recalculate_total()

    def recalculate_total(self) -> None:
        """Recalculate totals ensuring integer results."""
        self.total_amount = sum(item.total_price() for item in self.items)  # Already rounded to int
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
