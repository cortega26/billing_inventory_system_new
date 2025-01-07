from typing import Dict, Any, Optional
from utils.exceptions import ValidationException
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Product:
    def __init__(
        self,
        id: int,
        name: str,
        description: str,
        category_id: int,
        cost_price: float,
        sell_price: float,
        barcode: Optional[str] = None,
        category_name: Optional[str] = None
    ):
        self.id = id
        self.name = name
        self.description = description
        self.category_id = category_id
        self.category_name = category_name
        self._cost_price = int(cost_price) if cost_price is not None else 0
        self._sell_price = int(sell_price) if sell_price is not None else 0
        self.barcode = barcode

    @property
    def cost_price(self) -> int:
        return self._cost_price

    @cost_price.setter
    def cost_price(self, value: Any):
        if value is None:
            self._cost_price = 0
            return
        try:
            price = int(value)
            if price < 0:
                raise ValidationException("Cost price cannot be negative")
            self._cost_price = price
        except (TypeError, ValueError):
            raise ValidationException("Invalid cost price format")

    @property
    def sell_price(self) -> int:
        return self._sell_price

    @sell_price.setter
    def sell_price(self, value: Any):
        if value is None:
            self._sell_price = 0
            return
        try:
            price = int(value)
            if price < 0:
                raise ValidationException("Sell price cannot be negative")
            self._sell_price = price
        except (TypeError, ValueError):
            raise ValidationException("Invalid sell price format")

    def calculate_profit(self) -> int:
        """Calculate the profit for this product."""
        return self.sell_price - self.cost_price

    def calculate_profit_margin(self) -> float:
        """Calculate the profit margin as a percentage."""
        if self.cost_price == 0:
            return 0
        return round((self.calculate_profit() / self.cost_price * 100), 2)

    def to_dict(self) -> Dict[str, Any]:
        """Convert product to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category_id": self.category_id,
            "category_name": self.category_name or 'Uncategorized',
            "cost_price": int(self.cost_price),
            "sell_price": int(self.sell_price),
            "barcode": self.barcode
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Product':
        """Create a Product instance from a dictionary."""
        return cls(
            id=data.get('id', 0),
            name=data.get('name', ''),
            description=data.get('description', ''),
            category_id=data.get('category_id', 0),
            cost_price=data.get('cost_price', 0),
            sell_price=data.get('sell_price', 0),
            barcode=data.get('barcode', '')
        )

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Product':
        """Create a Product instance from a database row."""
        logger.debug(f"Creating Product from row: {row}")
        product = cls(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            category_id=row['category_id'],
            cost_price=row['cost_price'],
            sell_price=row['sell_price'],
            barcode=row['barcode'],
            category_name=row.get('category_name', 'Uncategorized')
        )
        logger.debug(f"Created Product: {vars(product)}")
        return product

    def validate(self):
        """Validate the product data."""
        if not self.name:
            raise ValidationException("Product name is required")
        if not self.category_id:
            raise ValidationException("Category ID is required")
        if not self.barcode:
            raise ValidationException("Barcode is required")
        if len(self.barcode) != 8:
            raise ValidationException("Barcode must be 8 digits")
        if not self.barcode.isdigit():
            raise ValidationException("Barcode must contain only digits")
        if self.sell_price is not None and self.cost_price is not None and self.sell_price < self.cost_price:
            raise ValidationException("Sell price cannot be less than cost price")

    def __str__(self) -> str:
        return f"Product(id={self.id}, name={self.name}, barcode={self.barcode})"

    def __repr__(self) -> str:
        return self.__str__()

    @staticmethod
    def validate_barcode(barcode: str) -> None:
        """Validate barcode format."""
        if not barcode:
            return  # Allow empty barcode
        
        if not barcode.isdigit():
            raise ValidationException("Barcode must contain only digits")
        
        valid_lengths = [8, 12, 13, 14]
        if len(barcode) not in valid_lengths:
            raise ValidationException(f"Barcode must be one of these lengths: {valid_lengths}")
