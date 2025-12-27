import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, ClassVar, Dict

from utils.exceptions import ValidationException
from utils.system.logger import logger


@dataclass(frozen=True)
class Category:
    """
    Represents a product category in the system.

    Attributes:
        id (int): Unique identifier for the category
        name (str): Name of the category
        created_at (datetime): Timestamp when category was created
        updated_at (datetime): Timestamp when category was last updated
    """

    id: int
    name: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Class constants
    NAME_MAX_LENGTH: ClassVar[int] = 50
    NAME_MIN_LENGTH: ClassVar[int] = 1
    NAME_PATTERN: ClassVar[str] = r"^[\w\s\-]+$"

    def __post_init__(self) -> None:
        """Validate category data after initialization."""
        self.validate_name(self.name)
        if not isinstance(self.id, int):
            logger.error(
                "Invalid category ID type", extra={"id": self.id, "type": type(self.id)}
            )
            raise ValidationException("Category ID must be an integer")
        if self.id < 0:
            logger.error("Negative category ID", extra={"id": self.id})
            raise ValidationException("Category ID cannot be negative")

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Category":
        """
        Create a Category instance from a database row.

        Args:
            row: Dictionary containing category data from database

        Returns:
            Category: New Category instance

        Raises:
            ValidationException: If required fields are missing or invalid
        """
        try:
            return cls(
                id=int(row["id"]),
                name=str(row["name"]),
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
        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                "Failed to create category from DB row",
                extra={"error": str(e), "row": row},
            )
            raise ValidationException(f"Invalid category data: {str(e)}")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert category to dictionary representation.

        Returns:
            Dict[str, Any]: Dictionary containing category data
        """
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @staticmethod
    def validate_name(name: str) -> str:
        """
        Validate and normalize category name.

        Args:
            name: Category name to validate

        Returns:
            str: Normalized category name

        Raises:
            ValidationException: If name is invalid
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

        Args:
            **changes: Attribute changes to apply to the clone

        Returns:
            Category: New Category instance with changes applied
        """
        return replace(self, **changes)

    def update(self, name: str) -> "Category":
        """
        Create new category instance with updated name.

        Args:
            name: New category name

        Returns:
            Category: New Category instance with updated name

        Raises:
            ValidationException: If name is invalid
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
    def create_empty(cls, id: int = -1) -> "Category":
        """
        Create an empty category instance.

        Args:
            id: Category ID (defaults to -1)

        Returns:
            Category: New empty Category instance
        """
        return cls(id=id, name="")
