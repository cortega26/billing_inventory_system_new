from dataclasses import dataclass
from typing import Dict, Any
from utils.exceptions import ValidationException
from utils.decorators import validate_input


@dataclass
class Category:
    id: int
    name: str

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Category":
        return cls(id=row["id"], name=row["name"])

    def __str__(self) -> str:
        return f"Category(id={self.id}, name='{self.name}')"

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name}

    @staticmethod
    @validate_input(show_dialog=True)
    def validate_name(name: str) -> None:
        if not name or len(name.strip()) == 0:
            raise ValidationException("Category name cannot be empty")
        if len(name) > 50:
            raise ValidationException("Category name cannot exceed 50 characters")
