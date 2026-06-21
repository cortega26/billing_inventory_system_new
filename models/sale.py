from datetime import datetime
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from pydantic import PrivateAttr, model_validator
from sqlmodel import Column, Field, Integer, Relationship, SQLModel

from utils.exceptions import ValidationException
from utils.system.logger import logger
from utils.validation.validators import validate_money, validate_money_multiplication


class SaleItem(SQLModel, table=True):
    """Sale item entity with SQLModel implementation."""

    __tablename__ = "sale_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    sale_id: int = Field(
        sa_column=sa.Column(
            sa.Integer, sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False
        )
    )
    product_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    quantity: float  # Allow up to 3 decimals for weight-based products
    unit_price: int = Field(sa_column=Column("price", Integer, nullable=False))
    profit: int  # Chilean Pesos - always integer
    created_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )

    # Relationship to parent Sale
    sale: Optional["Sale"] = Relationship(back_populates="items")

    # Field not in the database table (extra joined info)
    _product_name: Optional[str] = PrivateAttr(default=None)

    @property
    def product_name(self) -> Optional[str]:
        return self._product_name

    @product_name.setter
    def product_name(self, value: Optional[str]):
        self._product_name = value

    def __init__(self, **data: Any):
        product_name = data.pop("product_name", None)
        super().__init__(**data)
        if product_name is not None:
            self.product_name = product_name

    @model_validator(mode="after")
    def post_init_validation(self) -> "SaleItem":
        self.quantity = self.normalize_quantity(self.quantity)
        self.validate_price(self.unit_price)
        self.validate_profit(self.profit)
        return self

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
                product_name=row.get("product_name"),
                created_at=(
                    datetime.fromisoformat(row["created_at"])
                    if "created_at" in row and row["created_at"]
                    else datetime.now()
                ),
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
        """Calculate total price ensuring proper CLP rounding."""
        return validate_money_multiplication(
            self.unit_price, self.quantity, "Total price"
        )

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


VALID_STATUSES = frozenset({"confirmed", "cancelled"})


class Sale(SQLModel, table=True):
    """Sale entity with SQLModel implementation."""

    __tablename__ = "sales"

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('confirmed', 'cancelled')", name="check_sale_status"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: Optional[int] = Field(
        default=None,
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    date: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
    total_amount: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    total_profit: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    receipt_id: Optional[str] = Field(default=None, unique=True)
    status: str = Field(
        default="confirmed",
        sa_column=sa.Column(
            sa.String, nullable=False, server_default=sa.text("'confirmed'")
        ),
    )
    created_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )

    # Relationship to SaleItems
    items: List[SaleItem] = Relationship(back_populates="sale")

    @model_validator(mode="after")
    def post_init_validation(self) -> "Sale":
        self.validate_customer_id(self.customer_id)
        self.validate_date(self.date)
        self.validate_total_amount(self.total_amount)
        self.validate_total_profit(self.total_profit)
        self.validate_status(self.status)
        return self

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Sale":
        try:
            # Parse date string
            try:
                date_val = datetime.strptime(row["date"], "%Y-%m-%d")
            except ValueError:
                date_val = datetime.fromisoformat(row["date"])

            return cls(
                id=int(row["id"]),
                customer_id=(
                    int(row["customer_id"])
                    if row.get("customer_id") is not None
                    else None
                ),
                date=date_val,
                total_amount=int(row["total_amount"]),
                total_profit=int(row["total_profit"]),
                receipt_id=row.get("receipt_id"),
                status=row.get("status", "confirmed"),
                created_at=(
                    datetime.fromisoformat(row["created_at"])
                    if "created_at" in row and row["created_at"]
                    else datetime.now()
                ),
            )
        except (ValueError, TypeError) as e:
            logger.error(f"Error creating Sale from row: {row}")
            logger.error(f"Error details: {str(e)}")
            raise

    @staticmethod
    def validate_customer_id(customer_id: Optional[int]) -> None:
        if customer_id is None:
            return
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

    @staticmethod
    def validate_status(status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValidationException(
                f"Invalid sale status '{status}'. Must be one of: {sorted(VALID_STATUSES)}"
            )

    def add_item(self, item: SaleItem) -> None:
        self.items.append(item)
        self.recalculate_total()

    def remove_item(self, item_id: int) -> None:
        self.items = [item for item in self.items if item.id != item_id]
        self.recalculate_total()

    def recalculate_total(self) -> None:
        """Recalculate totals ensuring proper CLP handling."""
        self.total_amount = sum(item.total_price() for item in self.items)
        # Validate final total — no upper cap; totals can exceed any single unit price
        self.total_amount = validate_money(
            self.total_amount, "Total amount", max_value=None
        )

        # Profit can be negative (selling below cost) — only require integer type
        self.total_profit = sum(item.profit for item in self.items)
        if not isinstance(self.total_profit, int):
            raise ValidationException("Total profit must be an integer")

    def update_date(self, new_date: datetime) -> None:
        self.validate_date(new_date)
        self.date = new_date

    def update_customer(self, new_customer_id: Optional[int]) -> None:
        self.validate_customer_id(new_customer_id)
        self.customer_id = new_customer_id

    def update_receipt_id(self, new_receipt_id: Optional[str]) -> None:
        self.receipt_id = new_receipt_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "date": self.date.strftime("%Y-%m-%d"),
            "total_amount": self.total_amount,
            "total_profit": self.total_profit,
            "receipt_id": self.receipt_id,
            "status": self.status,
            "items": [item.to_dict() for item in self.items],
        }

    def __str__(self) -> str:
        return (
            f"Sale(id={self.id}, customer_id={self.customer_id}, "
            f"date='{self.date.strftime('%Y-%m-%d')}', total_amount={self.total_amount}, "
            f"total_profit={self.total_profit}, receipt_id='{self.receipt_id}')"
        )
