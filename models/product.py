from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from models.enums import MAX_PRICE_CLP
from utils.exceptions import ValidationException


@dataclass
class Product:
    """Product entity with proper dataclass implementation."""

    id: int
    name: str
    description: str
    category_id: int
    cost_price: int  # Chilean Pesos - always integer
    sell_price: int  # Chilean Pesos - always integer
    barcode: Optional[str] = None
    category_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate data after initialization."""
        self.validate()

    def validate(self):
        """Validate product data."""
        if not self.name or len(self.name.strip()) == 0:
            raise ValidationException("Product name is required")

        if self.cost_price < 0:
            raise ValidationException("Cost price cannot be negative")

        if self.sell_price < 0:
            raise ValidationException("Sell price cannot be negative")

        if self.cost_price > MAX_PRICE_CLP:
            raise ValidationException(f"Cost price exceeds maximum ({MAX_PRICE_CLP:,.0f} CLP)")

        if self.sell_price > MAX_PRICE_CLP:
            raise ValidationException(f"Sell price exceeds maximum ({MAX_PRICE_CLP:,.0f} CLP)")

        if self.barcode:
            self.validate_barcode(self.barcode)

    @staticmethod
    def validate_barcode(barcode: str) -> None:
        """Validate barcode format."""
        if not barcode:
            return

        if not barcode.isdigit():
            raise ValidationException("Barcode must contain only digits")

        valid_lengths = {8, 12, 13, 14}
        if len(barcode) not in valid_lengths:
            raise ValidationException(f"Barcode must be one of: {valid_lengths} digits")

    def calculate_profit(self) -> int:
        """Calculate profit in Chilean Pesos."""
        return self.sell_price - self.cost_price

    def calculate_profit_margin(self) -> float:
        """Calculate profit margin as percentage."""
        if self.sell_price == 0:
            return 0.0
        return round((self.calculate_profit() / self.sell_price) * 100, 2)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Product":
        """Create Product from database row."""
        return cls(
            id=int(row["id"]),
            name=str(row["name"]),
            description=str(row["description"] or ""),
            category_id=int(row["category_id"]),
            cost_price=int(row["cost_price"] or 0),
            sell_price=int(row["sell_price"] or 0),
            barcode=row.get("barcode"),
            category_name=row.get("category_name", "Uncategorized"),
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "cost_price": self.cost_price,
            "sell_price": self.sell_price,
            "barcode": self.barcode,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
