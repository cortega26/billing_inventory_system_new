from typing import Any

import sqlalchemy as sa
from pydantic import PrivateAttr, model_validator
from sqlmodel import Field, SQLModel

from utils.validation.validators import (
    validate_3or4digit_identifier,
    validate_9digit_identifier,
    validate_string,
)


class Customer(SQLModel, table=True):
    """
    Represents a customer in the system.
    """

    __tablename__: str = "customers"

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
        sa.CheckConstraint("credit_limit >= 0", name="check_customer_credit_limit"),
    )

    id: int | None = Field(default=None, primary_key=True)
    identifier_9: str = Field(unique=True, index=True)
    name: str | None = Field(default=None)
    is_active: bool = Field(
        default=True,
        sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.text("1")),
    )
    deleted_at: str | None = Field(default=None)
    current_balance: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    credit_limit: int = Field(
        default=50000,
        sa_column=sa.Column(
            sa.Integer, nullable=False, server_default=sa.text("50000")
        ),
    )

    # Not a database column in the 'customers' table (stored in customer_identifiers table)
    _identifier_3or4: str | None = PrivateAttr(default=None)

    @property
    def identifier_3or4(self) -> str | None:
        return self._identifier_3or4

    @identifier_3or4.setter
    def identifier_3or4(self, value: str | None):
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
    def from_db_row(cls, row: dict[str, Any]) -> "Customer":
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
        validate_9digit_identifier(identifier)

    @staticmethod
    def validate_identifier_3or4(identifier: str | None) -> None:
        """
        Validate 3 or 4-digit identifier.
        """
        if identifier is not None:
            validate_3or4digit_identifier(identifier)

    @staticmethod
    def validate_name(name: str) -> None:
        """
        Validate customer name.
        """
        validate_string(name, min_length=1, max_length=50)

    def update_identifier_3or4(self, new_identifier_3or4: str | None) -> None:
        """
        Update the 3 or 4-digit identifier.
        """
        self.validate_identifier_3or4(new_identifier_3or4)
        self.identifier_3or4 = new_identifier_3or4

    def get_all_identifiers(self) -> list[str]:
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

    def to_dict(self) -> dict[str, Any]:
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

    __tablename__: str = "customer_identifiers"

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    identifier_3or4: str
