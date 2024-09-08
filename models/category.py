from dataclasses import dataclass
from typing import Dict, Any, ClassVar
from utils.exceptions import ValidationException

@dataclass
class Category:
    id: int
    name: str

    NAME_MAX_LENGTH: ClassVar[int] = 50

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Category":
        return cls(id=row["id"], name=row["name"])

    def __str__(self) -> str:
        return f"Category(id={self.id}, name='{self.name}')"

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name}

    @staticmethod
    def validate_name(name: str) -> None:
        if not name or len(name.strip()) == 0:
            raise ValidationException("Category name cannot be empty")
        if len(name) > Category.NAME_MAX_LENGTH:
            raise ValidationException(f"Category name cannot exceed {Category.NAME_MAX_LENGTH} characters")

    def update(self, name: str) -> None:
        self.validate_name(name)
        self.name = name
