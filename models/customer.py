import re
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from pydantic import PrivateAttr, model_validator
from sqlmodel import Field, SQLModel

from utils.exceptions import ValidationException


class Customer(SQLModel, table=True):
    """
    Represents a customer in the system.
    """

    __tablename__ = "customers"

    __table_args__ = (
        sa.CheckConstraint("is_active IN (0, 1)", name="check_customer_active"),
        sa.CheckConstraint(
            "LENGTH(identifier_9) = 9", name="check_identifier_9_length"
        ),
        sa.CheckConstraint(
            "SUBSTR(identifier_9, 1, 1) = '9'", name="check_identifier_9_starts_with_9"
        ),
        sa.CheckConstraint(
            "identifier_9 NOT GLOB '*[^0-9]*'", name="check_identifier_9_numeric"
        ),
        sa.CheckConstraint(
            "name IS NULL OR LENGTH(name) <= 50", name="check_customer_name_length"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    identifier_9: str = Field(unique=True, index=True)
    name: Optional[str] = Field(default=None)
    is_active: bool = Field(
        default=True,
        sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.text("1")),
    )
    deleted_at: Optional[str] = Field(default=None)

    # Not a database column in the 'customers' table (stored in customer_identifiers table)
    _identifier_3or4: Optional[str] = PrivateAttr(default=None)

    @property
    def identifier_3or4(self) -> Optional[str]:
        return self._identifier_3or4

    @identifier_3or4.setter
    def identifier_3or4(self, value: Optional[str]):
        self._identifier_3or4 = value

    def __init__(self, **data: Any):
        identifier_3or4 = data.pop("identifier_3or4", None)
        super().__init__(**data)
        if identifier_3or4 is not None:
            self.identifier_3or4 = identifier_3or4

    @model_validator(mode="after")
    def post_init_validation(self) -> "Customer":
        """
        Validate all fields after initialization.
        """
        self.validate_identifier_9(self.identifier_9)
        if self.identifier_3or4:
            self.validate_identifier_3or4(self.identifier_3or4)
        if self.name is not None:
            self.validate_name(self.name)
        return self

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Customer":
        """
        Create a Customer instance from a database row.
        """
        return cls(
            id=row["id"],
            identifier_9=row["identifier_9"],
            name=row.get("name"),
            identifier_3or4=row.get("identifier_3or4"),
            is_active=bool(row.get("is_active", 1)),
            deleted_at=row.get("deleted_at"),
        )

    @staticmethod
    def validate_identifier_9(identifier: str) -> None:
        """
        Validate 9-digit identifier.
        """
        if (
            not isinstance(identifier, str)
            or len(identifier) != 9
            or not identifier.isdigit()
            or not identifier.startswith("9")
        ):
            raise ValidationException("identifier_9 must be a string of 9 digits")

    @staticmethod
    def validate_identifier_3or4(identifier: Optional[str]) -> None:
        """
        Validate 3 or 4-digit identifier.
        """
        if identifier is not None:
            if (
                not isinstance(identifier, str)
                or len(identifier) not in (3, 4)
                or not identifier.isdigit()
                or identifier.startswith("0")
            ):
                raise ValidationException(
                    "identifier_3or4 must be a string of 3 or 4 digits"
                )

    @staticmethod
    def validate_name(name: str) -> None:
        """
        Validate customer name.
        """
        if not isinstance(name, str):
            raise ValidationException("Name must be a string")

        # Remove extra whitespace and normalize
        name_clean = " ".join(name.split())

        if len(name_clean) > 50:
            raise ValidationException("Name cannot exceed 50 characters")

        # Validate that name contains only letters, spaces, and Spanish characters
        if not re.match(r"^[A-Za-zÁÉÍÓÚÑáéíóúñ ]+$", name_clean):
            raise ValidationException(
                "Name can only contain letters, accented characters, and spaces"
            )

    def update_identifier_9(self, new_identifier_9: str) -> None:
        """
        Update the 9-digit identifier.
        """
        self.validate_identifier_9(new_identifier_9)
        self.identifier_9 = new_identifier_9

    def update_identifier_3or4(self, new_identifier_3or4: Optional[str]) -> None:
        """
        Update the 3 or 4-digit identifier.
        """
        self.validate_identifier_3or4(new_identifier_3or4)
        self.identifier_3or4 = new_identifier_3or4

    def update_name(self, new_name: Optional[str]) -> None:
        """
        Update the customer name.
        """
        if new_name is not None:
            self.validate_name(new_name)
            new_name = " ".join(new_name.split())  # Normalize whitespace
        self.name = new_name

    def get_all_identifiers(self) -> List[str]:
        """
        Get all identifiers associated with this customer.
        """
        identifiers = [self.identifier_9]
        if self.identifier_3or4:
            identifiers.append(self.identifier_3or4)
        return identifiers

    def get_display_name(self) -> str:
        """
        Get a formatted display name including identifiers and name.
        """
        base = f"{self.identifier_9} ({self.identifier_3or4 or 'N/A'})"
        if self.name:
            return f"{base} - {self.name}"
        return base

    def __str__(self) -> str:
        """String representation of the customer."""
        identifiers = ", ".join(self.get_all_identifiers())
        name_info = f", name: {self.name}" if self.name else ""
        return f"Customer(id={self.id}, identifiers=[{identifiers}]{name_info})"

    def __eq__(self, other: object) -> bool:
        """Check equality with another customer."""
        if not isinstance(other, Customer):
            return NotImplemented
        return (
            self.id == other.id
            and self.get_all_identifiers() == other.get_all_identifiers()
            and self.name == other.name
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert customer to dictionary.
        """
        return {
            "id": self.id,
            "identifier_9": self.identifier_9,
            "identifier_3or4": self.identifier_3or4,
            "name": self.name,
            "is_active": self.is_active,
            "deleted_at": self.deleted_at,
        }


class CustomerIdentifier(SQLModel, table=True):
    """
    Represents customer identifier 3 or 4 mapping to customer.
    """

    __tablename__ = "customer_identifiers"

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    identifier_3or4: str
