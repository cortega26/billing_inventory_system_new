from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Dict

from utils.exceptions import ValidationException


class StockStatus(Enum):
    """Enumeration of possible stock statuses."""

    OUT_OF_STOCK = "out_of_stock"
    LOW_STOCK = "low_stock"
    OPTIMAL = "optimal"
    OVERSTOCKED = "overstocked"


@dataclass(frozen=True)
class Inventory:
    """
    Represents inventory for a product in the system.

    Attributes:
        id (int): Unique identifier
        product_id (int): Associated product ID
        quantity (float): Current quantity in stock (up to 3 decimals)
        created_at (datetime): Creation timestamp
        updated_at (datetime): Last update timestamp
    """

    id: int
    product_id: int
    quantity: float
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Class constants
    QUANTITY_PRECISION: ClassVar[int] = 3
    MAX_QUANTITY: ClassVar[float] = 9999999.999

    def __post_init__(self) -> None:
        """
        Validate inventory data after initialization.

        Raises:
            ValidationException: If validation fails
        """
        if not isinstance(self.id, int) or self.id < 0:
            raise ValidationException("Invalid inventory ID")

        if not isinstance(self.product_id, int) or self.product_id < 0:
            raise ValidationException("Invalid product ID")

        self._validate_float_field(self.quantity, "Quantity")

        # Round quantity to specified precision
        object.__setattr__(self, "quantity", self._round_quantity(self.quantity))

    @classmethod
    def _round_quantity(cls, value: float) -> float:
        """Round float to specified precision."""
        return round(float(value), cls.QUANTITY_PRECISION)

    @staticmethod
    def _validate_float_field(value: float, field_name: str) -> None:
        """
        Validate a float field.

        Args:
            value: Value to validate
            field_name: Name of field for error messages

        Raises:
            ValidationException: If validation fails
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

        Args:
            row: Dictionary containing inventory data from database

        Returns:
            Inventory: New Inventory instance

        Raises:
            ValidationException: If required fields are missing or invalid
        """
        try:
            return cls(
                id=int(row["id"]),
                product_id=int(row["product_id"]),
                quantity=float(str(row["quantity"])),
                created_at=(
                    datetime.fromisoformat(row["created_at"])
                    if "created_at" in row
                    else datetime.now()
                ),
                updated_at=(
                    datetime.fromisoformat(row["updated_at"])
                    if "updated_at" in row
                    else datetime.now()
                ),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise ValidationException(f"Invalid inventory data: {str(e)}")

    def update_quantity(self, change: float) -> "Inventory":
        """
        Create new inventory instance with updated quantity.

        Args:
            change: Amount to change quantity by (positive or negative)

        Returns:
            Inventory: New Inventory instance with updated quantity

        Raises:
            ValidationException: If new quantity would be invalid
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

        Args:
            new_quantity: New quantity value

        Returns:
            Inventory: New Inventory instance with set quantity

        Raises:
            ValidationException: If new quantity is invalid
        """
        self._validate_float_field(new_quantity, "New quantity")
        return self.clone(quantity=new_quantity, updated_at=datetime.now())

    def get_stock_status(self) -> StockStatus:
        """
        Get current stock status.

        Returns:
            StockStatus: OUT_OF_STOCK when quantity is zero, OPTIMAL otherwise.
        """
        if self.quantity == 0:
            return StockStatus.OUT_OF_STOCK
        return StockStatus.OPTIMAL

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert inventory to dictionary representation.

        Returns:
            Dict[str, Any]: Dictionary containing inventory data
        """
        return {
            "id": self.id,
            "product_id": self.product_id,
            "quantity": str(self.quantity),
            "stock_status": self.get_stock_status().value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def clone(self, **changes: Any) -> "Inventory":
        """
        Create a copy of this inventory with optional changes.

        Args:
            **changes: Attribute changes to apply to the clone

        Returns:
            Inventory: New Inventory instance with changes applied
        """
        return replace(self, **changes)

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

        Args:
            product_id: Associated product ID
            id: Inventory ID (defaults to 0, meaning not yet persisted)

        Returns:
            Inventory: New empty Inventory instance
        """
        return cls(id=id, product_id=product_id, quantity=0.0)
