from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict, Optional

import sqlalchemy as sa
from pydantic import model_validator
from sqlmodel import Field, SQLModel

from utils.exceptions import ValidationException


class StockStatus(Enum):
    """Enumeration of possible stock statuses."""

    OUT_OF_STOCK = "out_of_stock"
    LOW_STOCK = "low_stock"
    OPTIMAL = "optimal"
    OVERSTOCKED = "overstocked"


class Inventory(SQLModel, table=True):
    """
    Represents inventory for a product in the system.
    """

    __tablename__ = "inventory"

    __table_args__ = (
        sa.CheckConstraint("quantity >= 0", name="check_quantity_positive"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            unique=True,
            index=True,
            nullable=False,
        )
    )
    quantity: float = Field(default=0.000)
    created_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )

    # Class constants
    QUANTITY_PRECISION: ClassVar[int] = 3
    MAX_QUANTITY: ClassVar[float] = 9999999.999

    @model_validator(mode="after")
    def post_init_validation(self) -> "Inventory":
        """
        Validate inventory data after initialization.
        """
        if self.id is not None:
            if not isinstance(self.id, int) or self.id < 0:
                raise ValidationException("Invalid inventory ID")

        if not isinstance(self.product_id, int) or self.product_id < 0:
            raise ValidationException("Invalid product ID")

        self._validate_float_field(self.quantity, "Quantity")

        # Round quantity to specified precision
        self.quantity = self._round_quantity(self.quantity)
        return self

    @classmethod
    def _round_quantity(cls, value: float) -> float:
        """Round float to specified precision."""
        return round(float(value), cls.QUANTITY_PRECISION)

    @staticmethod
    def _validate_float_field(value: float, field_name: str) -> None:
        """
        Validate a float field.
        """
        if not isinstance(value, (int, float)):
            raise ValidationException(f"{field_name} must be a numeric value")

        float_value = float(value)
        if float_value < 0:
            raise ValidationException(f"{field_name} cannot be negative")

        if float_value > Inventory.MAX_QUANTITY:
            raise ValidationException(f"{field_name} exceeds maximum allowed value")

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Inventory":
        """
        Create an Inventory instance from a database row.
        """
        try:
            return cls(
                id=int(row["id"]),
                product_id=int(row["product_id"]),
                quantity=float(str(row["quantity"])),
                created_at=(
                    datetime.fromisoformat(row["created_at"])
                    if "created_at" in row and row["created_at"]
                    else datetime.now()
                ),
                updated_at=(
                    datetime.fromisoformat(row["updated_at"])
                    if "updated_at" in row and row["updated_at"]
                    else datetime.now()
                ),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise ValidationException(f"Invalid inventory data: {str(e)}")

    def update_quantity(self, change: float) -> "Inventory":
        """
        Create new inventory instance with updated quantity.
        """
        new_quantity = self.quantity + float(change)
        if new_quantity < 0:
            raise ValidationException(
                f"Cannot decrease quantity by {abs(change)}. Current quantity: {self.quantity}"
            )

        return self.clone(quantity=new_quantity, updated_at=datetime.now())

    def set_quantity(self, new_quantity: float) -> "Inventory":
        """
        Create new inventory instance with set quantity.
        """
        self._validate_float_field(new_quantity, "New quantity")
        return self.clone(quantity=new_quantity, updated_at=datetime.now())

    def get_stock_status(self) -> StockStatus:
        """
        Get current stock status.
        """
        if self.quantity == 0:
            return StockStatus.OUT_OF_STOCK
        return StockStatus.OPTIMAL

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert inventory to dictionary representation.
        """
        return {
            "id": self.id,
            "product_id": self.product_id,
            "quantity": str(self.quantity),
            "stock_status": self.get_stock_status().value,
            "created_at": self.created_at.isoformat()
            if isinstance(self.created_at, datetime)
            else self.created_at,
            "updated_at": self.updated_at.isoformat()
            if isinstance(self.updated_at, datetime)
            else self.updated_at,
        }

    def clone(self, **changes: Any) -> "Inventory":
        """
        Create a copy of this inventory with optional changes.
        """
        data = {
            "id": self.id,
            "product_id": self.product_id,
            "quantity": self.quantity,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        data.update(changes)
        return Inventory(**data)

    def __str__(self) -> str:
        """String representation of inventory."""
        return (
            f"Inventory(id={self.id}, product_id={self.product_id}, "
            f"quantity={self.quantity}, status={self.get_stock_status().value})"
        )

    @classmethod
    def create_empty(cls, product_id: int, id: int = 0) -> "Inventory":
        """
        Create an empty inventory instance.
        """
        return cls(id=id, product_id=product_id, quantity=0.0)


class InventoryAdjustment(SQLModel, table=True):
    """
    Represents an inventory adjustment in the system.
    """

    __tablename__ = "inventory_adjustments"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id")
    quantity_change: float
    reason: str
    date: str
