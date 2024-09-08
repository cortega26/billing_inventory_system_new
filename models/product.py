from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from models.category import Category
from utils.exceptions import ValidationException

@dataclass
class Product:
    id: int
    name: str
    description: Optional[str] = field(default=None)
    category: Optional[Category] = field(default=None)
    cost_price: Optional[int] = field(default=None)
    sell_price: Optional[int] = field(default=None)

    def __post_init__(self):
        self.validate_name(self.name)
        if self.description is not None:
            self.validate_description(self.description)
        if self.cost_price is not None:
            self.validate_price(self.cost_price, "Cost price")
        if self.sell_price is not None:
            self.validate_price(self.sell_price, "Sell price")

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Product":
        category = (
            Category(id=row["category_id"], name=row["category_name"])
            if row.get("category_id")
            else None
        )
        return cls(
            id=int(row["id"]),
            name=str(row["name"]),
            description=str(row["description"]) if row.get("description") else None,
            category=category,
            cost_price=(
                int(row["cost_price"]) if row.get("cost_price") is not None else None
            ),
            sell_price=(
                int(row["sell_price"]) if row.get("sell_price") is not None else None
            ),
        )

    @staticmethod
    def validate_name(name: str) -> None:
        if not name or len(name.strip()) == 0:
            raise ValidationException("Product name cannot be empty")
        if len(name) > 100:
            raise ValidationException("Product name cannot exceed 100 characters")

    @staticmethod
    def validate_description(description: str) -> None:
        if len(description) > 500:
            raise ValidationException("Product description cannot exceed 500 characters")

    @staticmethod
    def validate_price(price: int, price_type: str) -> None:
        if price < 0:
            raise ValidationException(f"{price_type} cannot be negative")

    def update_name(self, new_name: str) -> None:
        self.validate_name(new_name)
        self.name = new_name

    def update_description(self, new_description: Optional[str]) -> None:
        if new_description is not None:
            self.validate_description(new_description)
        self.description = new_description

    def update_category(self, new_category: Optional[Category]) -> None:
        self.category = new_category

    def update_cost_price(self, new_cost_price: Optional[int]) -> None:
        if new_cost_price is not None:
            self.validate_price(new_cost_price, "Cost price")
        self.cost_price = new_cost_price

    def update_sell_price(self, new_sell_price: Optional[int]) -> None:
        if new_sell_price is not None:
            self.validate_price(new_sell_price, "Sell price")
        self.sell_price = new_sell_price

    def calculate_profit_margin(self) -> Optional[float]:
        if self.cost_price is not None and self.sell_price is not None and self.cost_price > 0:
            return (self.sell_price - self.cost_price) / self.sell_price * 100
        return None

    def __str__(self) -> str:
        category_info = f", category: {self.category}" if self.category else ""
        cost_info = f", cost: {self.cost_price}" if self.cost_price is not None else ""
        sell_info = f", sell: {self.sell_price}" if self.sell_price is not None else ""
        return f"Product(id={self.id}, name='{self.name}', description='{self.description}'{category_info}{cost_info}{sell_info})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category_id": self.category.id if self.category else None,
            "category_name": self.category.name if self.category else None,
            "cost_price": self.cost_price,
            "sell_price": self.sell_price,
        }
