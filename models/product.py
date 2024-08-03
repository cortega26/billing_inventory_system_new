from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from models.category import Category

@dataclass
class Product:
    id: int
    name: str
    description: Optional[str] = field(default=None)
    category: Optional[Category] = field(default=None)
    price: Optional[float] = field(default=None)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Product':
        category = Category(id=row['category_id'], name=row['category_name']) if row.get('category_id') else None
        return cls(
            id=row['id'],
            name=row['name'],
            description=row.get('description'),
            category=category,
            price=row.get('price')
        )

    def __str__(self) -> str:
        category_info = f", category: {self.category}" if self.category else ""
        price_info = f", price: {self.price}" if self.price is not None else ""
        return f"Product(id={self.id}, name='{self.name}', description='{self.description}'{category_info}{price_info})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category_id': self.category.id if self.category else None,
            'category_name': self.category.name if self.category else None,
            'price': self.price
        }

    @staticmethod
    def validate_name(name: str) -> None:
        if not name or len(name.strip()) == 0:
            raise ValueError("Product name cannot be empty")
        if len(name) > 100:
            raise ValueError("Product name cannot exceed 100 characters")

    @staticmethod
    def validate_description(description: Optional[str]) -> None:
        if description and len(description) > 500:
            raise ValueError("Product description cannot exceed 500 characters")

    @staticmethod
    def validate_price(price: Optional[float]) -> None:
        if price is not None and price < 0:
            raise ValueError("Price cannot be negative")