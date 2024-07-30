from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class Product:
    id: int
    name: str
    description: Optional[str] = field(default=None)
    category_id: Optional[int] = field(default=None)
    category_name: Optional[str] = field(default=None)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Product':
        return cls(
            id=row['id'],
            name=row['name'],
            description=row.get('description'),
            category_id=row.get('category_id'),
            category_name=row.get('category_name')
        )

    def update(self, name: Optional[str] = None, description: Optional[str] = None, category_id: Optional[int] = None) -> None:
        if name is not None:
            self.name = name.strip()
        if description is not None:
            self.description = description.strip() if description else None
        if category_id is not None:
            self.category_id = category_id

    def __str__(self) -> str:
        category_info = f", category: {self.category_name}" if self.category_name else ""
        return f"Product(id={self.id}, name='{self.name}', description='{self.description}'{category_info})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category_id': self.category_id,
            'category_name': self.category_name
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