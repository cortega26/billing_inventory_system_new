import re
from datetime import datetime
from typing import Any, ClassVar, Dict, Optional

import sqlalchemy as sa
from pydantic import model_validator
from sqlmodel import Field, SQLModel

from utils.exceptions import ValidationException
from utils.system.logger import logger


class Category(SQLModel, table=True):
    """
    Represents a product category in the system.
    """

    __tablename__ = "categories"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    created_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )

    # Class constants
    NAME_MAX_LENGTH: ClassVar[int] = 50
    NAME_MIN_LENGTH: ClassVar[int] = 1
    NAME_PATTERN: ClassVar[str] = r"^[\w\s\-]+$"

    @model_validator(mode="after")
    def post_init_validation(self) -> "Category":
        """Validate category data after initialization."""
        self.validate_name(self.name)
        if self.id is not None:
            if not isinstance(self.id, int):
                logger.error(
                    "Invalid category ID type",
                    extra={"id": self.id, "type": type(self.id)},
                )
                raise ValidationException("Category ID must be an integer")
            if self.id < 0:
                logger.error("Negative category ID", extra={"id": self.id})
                raise ValidationException("Category ID cannot be negative")
        return self

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Category":
        """
        Create a Category instance from a database row.
        """
        try:
            return cls(
                id=int(row["id"]),
                name=str(row["name"]),
                created_at=(
                    datetime.fromisoformat(row["created_at"])
                    if "created_at" in row and row["created_at"]
                    else datetime.now()
                ),
                updated_at=(
                    datetime.fromisoformat(row["updated_at"])
                    if "updated_at" in row and row["updated_at"]
                    else datetime.now()
                ),
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                "Failed to create category from DB row",
                extra={"error": str(e), "row": row},
            )
            raise ValidationException(f"Invalid category data: {str(e)}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert category to dictionary representation.
        """
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat()
            if isinstance(self.created_at, datetime)
            else self.created_at,
            "updated_at": self.updated_at.isoformat()
            if isinstance(self.updated_at, datetime)
            else self.updated_at,
        }

    @staticmethod
    def validate_name(name: str) -> str:
        """
        Validate and normalize category name.
        """
        if not name:
            logger.warning("Empty category name provided")
            raise ValidationException("Category name cannot be empty")

        # Normalize whitespace first
        normalized_name = " ".join(name.split())

        if len(normalized_name) < Category.NAME_MIN_LENGTH:
            raise ValidationException("Category name cannot be empty")

        if len(normalized_name) > Category.NAME_MAX_LENGTH:
            logger.warning(
                "Category name exceeds maximum length",
                extra={
                    "name": normalized_name,
                    "length": len(normalized_name),
                    "max_length": Category.NAME_MAX_LENGTH,
                },
            )
            raise ValidationException(
                f"Category name cannot exceed {Category.NAME_MAX_LENGTH} characters"
            )

        if not re.match(Category.NAME_PATTERN, normalized_name):
            logger.warning(
                "Invalid category name format", extra={"name": normalized_name}
            )
            raise ValidationException(
                "Category name can only contain letters, numbers, spaces, and hyphens"
            )

        return normalized_name

    def clone(self, **changes: Any) -> "Category":
        """
        Create a copy of this category with optional changes.
        """
        data = {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        data.update(changes)
        return Category(**data)

    def update(self, name: str) -> "Category":
        """
        Create new category instance with updated name.
        """
        self.validate_name(name)
        return self.clone(name=name, updated_at=datetime.now())

    def __str__(self) -> str:
        """String representation of category."""
        return f"Category(id={self.id}, name='{self.name}')"

    def __eq__(self, other: object) -> bool:
        """Check if categories are equal."""
        if not isinstance(other, Category):
            return NotImplemented
        return self.id == other.id and self.name == other.name

    def __hash__(self) -> int:
        """Hash based on id and name."""
        return hash((self.id, self.name))

    def __lt__(self, other: "Category") -> bool:
        """Compare categories by name."""
        if not isinstance(other, Category):
            return NotImplemented
        return self.name.lower() < other.name.lower()

    @classmethod
    def create_empty(cls, id: int = 0) -> "Category":
        """
        Create an empty category instance.
        """
        return cls(id=id, name="")
