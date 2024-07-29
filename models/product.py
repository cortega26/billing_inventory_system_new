from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class Product:
    id: int
    name: str
    description: Optional[str] = field(default=None)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Product':
        return cls(
            id=row['id'],
            name=row['name'],
            description=row.get('description')
        )

    def update(self, name: Optional[str] = None, description: Optional[str] = None) -> None:
        """
        Update the product's name and/or description.

        Args:
            name (Optional[str]): New name for the product. If None, name is not updated.
            description (Optional[str]): New description for the product. If None, description is not updated.

        Raises:
            ValueError: If both name and description are None.
        """
        if name is None and description is None:
            raise ValueError("At least one of name or description must be provided")

        if name is not None:
            self.name = name.strip()
        if description is not None:
            self.description = description.strip() if description else None

    def __str__(self) -> str:
        return f"Product(id={self.id}, name='{self.name}', description='{self.description}')"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Product object to a dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the Product.
        """
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }

    @staticmethod
    def validate_name(name: str) -> None:
        """
        Validate the product name.

        Args:
            name (str): The name to validate.

        Raises:
            ValueError: If the name is empty or too long.
        """
        if not name or len(name.strip()) == 0:
            raise ValueError("Product name cannot be empty")
        if len(name) > 100:
            raise ValueError("Product name cannot exceed 100 characters")

    @staticmethod
    def validate_description(description: Optional[str]) -> None:
        """
        Validate the product description.

        Args:
            description (Optional[str]): The description to validate.

        Raises:
            ValueError: If the description is too long.
        """
        if description and len(description) > 500:
            raise ValueError("Product description cannot exceed 500 characters")