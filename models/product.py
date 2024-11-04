from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from models.category import Category
from utils.exceptions import ValidationException

@dataclass
class Product:
    """
    Product model with integer prices (Chilean Pesos)
    """
    id: int
    name: str
    description: Optional[str] = field(default=None)
    category: Optional[Category] = field(default=None)
    cost_price: Optional[int] = field(default=None)    # Chilean Pesos - always integer
    sell_price: Optional[int] = field(default=None)    # Chilean Pesos - always integer
    barcode: Optional[str] = field(default=None)

    def __post_init__(self):
        """Validate all fields after initialization."""
        self.validate_name(self.name)
        if self.description is not None:
            self.validate_description(self.description)
        if self.cost_price is not None:
            self.validate_price(self.cost_price, "Cost price")
        if self.sell_price is not None:
            self.validate_price(self.sell_price, "Sell price")
        if self.barcode is not None:
            self.validate_barcode(self.barcode)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Product":
        """
        Create a Product instance from a database row.

        Args:
            row (Dict[str, Any]): Database row containing product data.

        Returns:
            Product: A new Product instance.
        """
        category = (
            Category(id=row["category_id"], name=row["category_name"])
            if row.get("category_id")
            else None
        )

        barcode = row.get("barcode")
        if barcode == "":
            barcode = None

        return cls(
            id=int(row["id"]),
            name=str(row["name"]),
            description=str(row["description"]) if row.get("description") else None,
            category=category,
            cost_price=int(row["cost_price"]) if row.get("cost_price") is not None else None,
            sell_price=int(row["sell_price"]) if row.get("sell_price") is not None else None,
            barcode=barcode
        )

    @staticmethod
    def validate_name(name: str) -> None:
        """
        Validate product name.

        Args:
            name (str): Product name to validate.

        Raises:
            ValidationException: If name is invalid.
        """
        if not name or len(name.strip()) == 0:
            raise ValidationException("Product name cannot be empty")
        if len(name) > 100:
            raise ValidationException("Product name cannot exceed 100 characters")

    @staticmethod
    def validate_description(description: str) -> None:
        """
        Validate product description.

        Args:
            description (str): Product description to validate.

        Raises:
            ValidationException: If description is too long.
        """
        if len(description) > 500:
            raise ValidationException("Product description cannot exceed 500 characters")

    @staticmethod
    def validate_price(price: int, price_type: str) -> None:
        """
        Validate a price value. Must be a positive integer for Chilean Pesos.

        Args:
            price (int): Price to validate.
            price_type (str): Type of price (for error messages).

        Raises:
            ValidationException: If price is invalid.
        """
        if not isinstance(price, int):
            raise ValidationException(f"{price_type} must be an integer")
        if price < 0:
            raise ValidationException(f"{price_type} cannot be negative")

    @staticmethod
    def validate_barcode(barcode: str) -> None:
        """
        Validate product barcode.

        Args:
            barcode (str): Barcode to validate.

        Raises:
            ValidationException: If barcode is invalid.
        """
        if not barcode:
            return
        
        if not isinstance(barcode, str):
            raise ValidationException("Barcode must be a string")
        
        # Remove any whitespace
        barcode = barcode.strip()
        
        if len(barcode) == 0:
            return
            
        # Check if barcode contains only digits
        if not barcode.isdigit():
            raise ValidationException("Barcode must contain only digits")
        
        # Validate length - accept common barcode lengths
        valid_lengths = {8, 12, 13, 14}  # EAN-8, UPC-A, EAN-13, EAN-14
        if len(barcode) not in valid_lengths:
            raise ValidationException(f"Invalid barcode length. Must be one of: {valid_lengths}")

    def update_name(self, new_name: str) -> None:
        """Update product name."""
        self.validate_name(new_name)
        self.name = new_name

    def update_description(self, new_description: Optional[str]) -> None:
        """Update product description."""
        if new_description is not None:
            self.validate_description(new_description)
        self.description = new_description

    def update_category(self, new_category: Optional[Category]) -> None:
        """Update product category."""
        self.category = new_category

    def update_cost_price(self, new_cost_price: Optional[int]) -> None:
        """Update product cost price."""
        if new_cost_price is not None:
            self.validate_price(new_cost_price, "Cost price")
        self.cost_price = new_cost_price

    def update_sell_price(self, new_sell_price: Optional[int]) -> None:
        """Update product sell price."""
        if new_sell_price is not None:
            self.validate_price(new_sell_price, "Sell price")
        self.sell_price = new_sell_price

    def update_barcode(self, new_barcode: Optional[str]) -> None:
        """Update product barcode."""
        if new_barcode is not None:
            self.validate_barcode(new_barcode)
        self.barcode = new_barcode

    def calculate_profit_margin(self) -> Optional[float]:
        """
        Calculate the profit margin percentage.

        Returns:
            Optional[float]: Profit margin as a percentage, or None if prices are not set.
        """
        if self.cost_price is not None and self.sell_price is not None and self.cost_price > 0:
            return round((self.sell_price - self.cost_price) / self.sell_price * 100, 2)
        return None

    def calculate_profit(self) -> Optional[int]:
        """
        Calculate the profit in Chilean Pesos.

        Returns:
            Optional[int]: Profit amount, or None if prices are not set.
        """
        if self.cost_price is not None and self.sell_price is not None:
            return self.sell_price - self.cost_price
        return None

    def has_valid_prices(self) -> bool:
        """
        Check if the product has valid price configuration.

        Returns:
            bool: True if both prices are set and valid.
        """
        return (
            self.cost_price is not None and 
            self.sell_price is not None and 
            self.cost_price >= 0 and 
            self.sell_price >= self.cost_price
        )

    def __str__(self) -> str:
        """String representation of the product."""
        category_info = f", category: {self.category.name}" if self.category else ""
        cost_info = f", cost: {self.cost_price}" if self.cost_price is not None else ""
        sell_info = f", sell: {self.sell_price}" if self.sell_price is not None else ""
        barcode_info = f", barcode: {self.barcode}" if self.barcode else ""
        return (
            f"Product(id={self.id}, name='{self.name}', "
            f"description='{self.description}'{category_info}"
            f"{cost_info}{sell_info}{barcode_info})"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert product to dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the product.
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category_id": self.category.id if self.category else None,
            "category_name": self.category.name if self.category else None,
            "cost_price": self.cost_price,
            "sell_price": self.sell_price,
            "barcode": self.barcode,
            "profit_margin": self.calculate_profit_margin(),
            "profit": self.calculate_profit()
        }
