from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from pydantic import model_validator
from sqlmodel import Field, Relationship, SQLModel

from utils.exceptions import ValidationException
from utils.system.logger import logger
from utils.validation.validators import validate_money, validate_money_multiplication


class PurchaseItem(SQLModel, table=True):
    """Purchase item entity with SQLModel implementation."""

    __tablename__ = "purchase_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    purchase_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("purchases.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    product_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    quantity: float  # Allows up to 3 decimal places
    price: int  # Chilean Pesos - always integer

    # Relationship to parent Purchase
    purchase: Optional["Purchase"] = Relationship(back_populates="items")

    @model_validator(mode="after")
    def post_init_validation(self) -> "PurchaseItem":
        self.validate_quantity(self.quantity)
        self.validate_price(self.price)
        return self

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "PurchaseItem":
        return cls(
            id=int(row["id"]),
            purchase_id=int(row["purchase_id"]),
            product_id=int(row["product_id"]),
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
        decimal_str = str(quantity).split(".")
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
        """Calculate total price ensuring proper CLP rounding."""
        return validate_money_multiplication(self.price, self.quantity, "Total price")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "purchase_id": self.purchase_id,
            "product_id": self.product_id,
            "quantity": round(self.quantity, 3),  # Always round to 3 decimal places
            "price": self.price,
            "total_price": self.total_price(),
        }


class Purchase(SQLModel, table=True):
    """Purchase entity with SQLModel implementation."""

    __tablename__ = "purchases"

    id: Optional[int] = Field(default=None, primary_key=True)
    supplier: str
    date: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
    total_amount: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    created_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )

    # Relationship to PurchaseItems
    items: List[PurchaseItem] = Relationship(back_populates="purchase")

    @model_validator(mode="after")
    def post_init_validation(self) -> "Purchase":
        self.validate_supplier(self.supplier)
        self.validate_date(self.date)
        self.recalculate_total()
        return self

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Purchase":
        try:
            # Parse date string
            try:
                date_val = datetime.strptime(row["date"], "%Y-%m-%d")
            except ValueError:
                date_val = datetime.fromisoformat(row["date"])

            return cls(
                id=int(row["id"]),
                supplier=str(row["supplier"]),
                date=date_val,
                total_amount=int(row.get("total_amount", 0)),
                created_at=(
                    datetime.fromisoformat(row["created_at"])
                    if "created_at" in row and row["created_at"]
                    else datetime.now()
                ),
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Error creating Purchase from row: {row}")
            logger.error(f"Error details: {str(e)}")
            raise

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
        self.total_amount += item.total_price()

    def remove_item(self, item_id: int) -> None:
        """
        Remove a purchase item and update total.
        """
        item = next((item for item in self.items if item.id == item_id), None)
        if item:
            self.items.remove(item)
            self.total_amount -= item.total_price()
        else:
            raise ValidationException(
                f"Item with id {item_id} not found in the purchase"
            )

    def recalculate_total(self) -> None:
        """Recalculate total amount ensuring proper CLP handling."""
        try:
            total = sum(item.total_price() for item in self.items)
            # No upper cap — purchase totals can exceed any single unit price
            self.total_amount = validate_money(total, "Total amount", max_value=None)
        except Exception as e:
            logger.error(f"Error calculating total: {str(e)}")
            raise ValidationException("Error calculating total amount")

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
            "date": self.date.strftime("%Y-%m-%d"),
            "total_amount": self.total_amount,
            "items": [item.to_dict() for item in self.items],
        }

    def __str__(self) -> str:
        """
        String representation of the purchase.
        """
        return (
            f"Purchase(id={self.id}, supplier='{self.supplier}', "
            f"date='{self.date.strftime('%Y-%m-%d')}', "
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
        return self.total_amount == expected_total

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
