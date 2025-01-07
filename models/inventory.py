from dataclasses import dataclass, field, replace
from typing import Dict, Any, Optional, ClassVar
from datetime import datetime
from utils.exceptions import ValidationException
from enum import Enum

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
        min_stock_level (float): Minimum stock level before reorder
        max_stock_level (Optional[float]): Maximum stock level capacity
        reorder_point (float): Point at which to reorder stock
        reorder_quantity (float): Quantity to reorder when reordering
        created_at (datetime): Creation timestamp
        updated_at (datetime): Last update timestamp
    """
    id: int
    product_id: int
    quantity: float
    min_stock_level: float = field(default=0.0)
    max_stock_level: Optional[float] = None
    reorder_point: float = field(default=0.0)
    reorder_quantity: float = field(default=0.0)
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
        self._validate_float_field(self.min_stock_level, "Minimum stock level")
        
        if self.max_stock_level is not None:
            self._validate_float_field(self.max_stock_level, "Maximum stock level")
            if self.max_stock_level <= self.min_stock_level:
                raise ValidationException(
                    "Maximum stock level must be greater than minimum stock level"
                )

        self._validate_float_field(self.reorder_point, "Reorder point")
        self._validate_float_field(self.reorder_quantity, "Reorder quantity")

        # Round all float values to specified precision
        object.__setattr__(self, 'quantity', 
            self._round_quantity(self.quantity))
        object.__setattr__(self, 'min_stock_level', 
            self._round_quantity(self.min_stock_level))
        if self.max_stock_level is not None:
            object.__setattr__(self, 'max_stock_level', 
                self._round_quantity(self.max_stock_level))
        object.__setattr__(self, 'reorder_point', 
            self._round_quantity(self.reorder_point))
        object.__setattr__(self, 'reorder_quantity', 
            self._round_quantity(self.reorder_quantity))

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
                min_stock_level=float(str(row.get("min_stock_level", 0))),
                max_stock_level=float(str(row["max_stock_level"])) if row.get("max_stock_level") is not None else None,
                reorder_point=float(str(row.get("reorder_point", 0))),
                reorder_quantity=float(str(row.get("reorder_quantity", 0))),
                created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
                updated_at=datetime.fromisoformat(row["updated_at"]) if "updated_at" in row else datetime.now()
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
        
        if self.max_stock_level is not None and new_quantity > self.max_stock_level:
            raise ValidationException(
                f"Cannot increase quantity above max stock level of {self.max_stock_level}"
            )
            
        return self.clone(
            quantity=new_quantity,
            updated_at=datetime.now()
        )

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
        if self.max_stock_level is not None and new_quantity > self.max_stock_level:
            raise ValidationException(
                f"Cannot set quantity above max stock level of {self.max_stock_level}"
            )
            
        return self.clone(
            quantity=new_quantity,
            updated_at=datetime.now()
        )

    def set_stock_levels(
        self,
        min_level: float,
        max_level: Optional[float] = None,
        reorder_point: Optional[float] = None,
        reorder_quantity: Optional[float] = None
    ) -> "Inventory":
        """
        Create new inventory instance with updated stock levels.

        Args:
            min_level: New minimum stock level
            max_level: New maximum stock level
            reorder_point: New reorder point
            reorder_quantity: New reorder quantity

        Returns:
            Inventory: New Inventory instance with updated stock levels
            
        Raises:
            ValidationException: If new levels are invalid
        """
        self._validate_float_field(min_level, "Minimum stock level")
        if max_level is not None:
            self._validate_float_field(max_level, "Maximum stock level")
            if max_level <= min_level:
                raise ValidationException(
                    "Maximum stock level must be greater than minimum stock level"
                )

        updates = {
            "min_stock_level": min_level,
            "max_stock_level": max_level,
            "updated_at": datetime.now()
        }
        
        if reorder_point is not None:
            self._validate_float_field(reorder_point, "Reorder point")
            updates["reorder_point"] = reorder_point
            
        if reorder_quantity is not None:
            self._validate_float_field(reorder_quantity, "Reorder quantity")
            updates["reorder_quantity"] = reorder_quantity

        return self.clone(**updates)

    def get_stock_status(self) -> StockStatus:
        """
        Get current stock status.

        Returns:
            StockStatus: Current stock status
        """
        if self.quantity == 0:
            return StockStatus.OUT_OF_STOCK
        if self.quantity <= self.min_stock_level:
            return StockStatus.LOW_STOCK
        if self.max_stock_level is not None and self.quantity >= self.max_stock_level:
            return StockStatus.OVERSTOCKED
        return StockStatus.OPTIMAL

    def needs_reorder(self) -> bool:
        """
        Check if stock needs reordering.

        Returns:
            bool: True if stock needs reordering
        """
        return self.quantity <= self.reorder_point and self.reorder_quantity > 0

    def get_suggested_order_quantity(self) -> Optional[float]:
        """
        Get suggested order quantity if reorder is needed.

        Returns:
            Optional[float]: Suggested order quantity or None if no reorder needed
        """
        if not self.needs_reorder():
            return None
            
        if self.max_stock_level is not None:
            return min(
                self.reorder_quantity,
                self.max_stock_level - self.quantity
            )
        return self.reorder_quantity

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
            "min_stock_level": str(self.min_stock_level),
            "max_stock_level": str(self.max_stock_level) if self.max_stock_level is not None else None,
            "reorder_point": str(self.reorder_point),
            "reorder_quantity": str(self.reorder_quantity),
            "stock_status": self.get_stock_status().value,
            "needs_reorder": self.needs_reorder(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
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
    def create_empty(cls, product_id: int, id: int = -1) -> "Inventory":
        """
        Create an empty inventory instance.

        Args:
            product_id: Associated product ID
            id: Inventory ID (defaults to -1)

        Returns:
            Inventory: New empty Inventory instance
        """
        return cls(
            id=id,
            product_id=product_id,
            quantity=0.0
        )
