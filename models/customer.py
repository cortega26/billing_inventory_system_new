from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from utils.exceptions import ValidationException
import re

@dataclass
class Customer:
    id: int
    identifier_9: str
    name: Optional[str] = None
    identifier_3or4: Optional[str] = None
    _identifiers: List[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        """
        Validate all fields after initialization and set up identifiers list.
        """
        self.validate_identifier_9(self.identifier_9)
        if self.identifier_3or4:
            self.validate_identifier_3or4(self.identifier_3or4)
        if self.name is not None:
            self.validate_name(self.name)
        
        # Initialize identifiers list
        self._identifiers = [self.identifier_9]
        if self.identifier_3or4:
            self._identifiers.append(self.identifier_3or4)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Customer":
        """
        Create a Customer instance from a database row.

        Args:
            row (Dict[str, Any]): Database row containing customer data.

        Returns:
            Customer: A new Customer instance.
        """
        return cls(
            id=row["id"],
            identifier_9=row["identifier_9"],
            name=row.get("name"),
            identifier_3or4=row.get("identifier_3or4"),
        )

    @staticmethod
    def validate_identifier_9(identifier: str) -> None:
        """
        Validate 9-digit identifier.

        Args:
            identifier (str): The identifier to validate.

        Raises:
            ValidationException: If identifier is invalid.
        """
        if not isinstance(identifier, str) or len(identifier) != 9 or not identifier.isdigit():
            raise ValidationException("identifier_9 must be a string of 9 digits")

    @staticmethod
    def validate_identifier_3or4(identifier: Optional[str]) -> None:
        """
        Validate 3 or 4-digit identifier.

        Args:
            identifier (Optional[str]): The identifier to validate.

        Raises:
            ValidationException: If identifier is invalid.
        """
        if identifier is not None:
            if not isinstance(identifier, str) or len(identifier) not in (3, 4) or not identifier.isdigit():
                raise ValidationException("identifier_3or4 must be a string of 3 or 4 digits")

    @staticmethod
    def validate_name(name: str) -> None:
        """
        Validate customer name.

        Args:
            name (str): The name to validate.

        Raises:
            ValidationException: If name is invalid.
        """
        if not isinstance(name, str):
            raise ValidationException("Name must be a string")

        # Remove extra whitespace and normalize
        name = " ".join(name.split())

        if len(name) > 50:
            raise ValidationException("Name cannot exceed 50 characters")

        # Validate that name contains only letters, spaces, and Spanish characters
        if not re.match(r'^[A-Za-zÁÉÍÓÚÑáéíóúñ ]+$', name):
            raise ValidationException("Name can only contain letters, accented characters, and spaces")

    def update_identifier_9(self, new_identifier_9: str) -> None:
        """
        Update the 9-digit identifier.

        Args:
            new_identifier_9 (str): The new identifier.
        """
        self.validate_identifier_9(new_identifier_9)
        self.identifier_9 = new_identifier_9
        self._identifiers[0] = new_identifier_9

    def update_identifier_3or4(self, new_identifier_3or4: Optional[str]) -> None:
        """
        Update the 3 or 4-digit identifier.

        Args:
            new_identifier_3or4 (Optional[str]): The new identifier.
        """
        self.validate_identifier_3or4(new_identifier_3or4)
        self.identifier_3or4 = new_identifier_3or4
        if new_identifier_3or4:
            if len(self._identifiers) > 1:
                self._identifiers[1] = new_identifier_3or4
            else:
                self._identifiers.append(new_identifier_3or4)
        elif len(self._identifiers) > 1:
            self._identifiers.pop()

    def update_name(self, new_name: Optional[str]) -> None:
        """
        Update the customer name.

        Args:
            new_name (Optional[str]): The new name.
        """
        if new_name is not None:
            self.validate_name(new_name)
            new_name = " ".join(new_name.split())  # Normalize whitespace
        self.name = new_name

    def get_all_identifiers(self) -> List[str]:
        """
        Get all identifiers associated with this customer.

        Returns:
            List[str]: List of identifiers.
        """
        return self._identifiers.copy()

    def get_display_name(self) -> str:
        """
        Get a formatted display name including identifiers and name.

        Returns:
            str: Formatted display name.
        """
        base = f"{self.identifier_9} ({self.identifier_3or4 or 'N/A'})"
        if self.name:
            return f"{base} - {self.name}"
        return base

    def __str__(self) -> str:
        """String representation of the customer."""
        identifiers = ", ".join(self._identifiers)
        name_info = f", name: {self.name}" if self.name else ""
        return f"Customer(id={self.id}, identifiers=[{identifiers}]{name_info})"

    def __eq__(self, other: object) -> bool:
        """Check equality with another customer."""
        if not isinstance(other, Customer):
            return NotImplemented
        return (
            self.id == other.id and 
            self._identifiers == other._identifiers and 
            self.name == other.name
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert customer to dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of the customer.
        """
        return {
            "id": self.id,
            "identifier_9": self.identifier_9,
            "identifier_3or4": self.identifier_3or4,
            "name": self.name
        }
