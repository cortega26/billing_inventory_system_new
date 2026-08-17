"""Models are data containers; business validation is enforced by services.
Product.validate() runs at construction for load-path safety.
"""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from pydantic import PrivateAttr, model_validator
from sqlmodel import Field, SQLModel

from utils.dates import parse_datetime_cell
from utils.exceptions import ValidationException
from utils.validation.validators import validate_barcode, validate_money


class Product(SQLModel, table=True):
    """Product entity with SQLModel implementation."""

    __tablename__: str = "products"

    __table_args__ = (
        sa.CheckConstraint("cost_price >= 0", name="check_cost_price_positive"),
        sa.CheckConstraint("sell_price >= 0", name="check_sell_price_positive"),
        sa.CheckConstraint("is_active IN (0, 1)", name="check_product_active"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = Field(default=None)
    category_id: int | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    cost_price: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    sell_price: int = Field(
        default=0,
        sa_column=sa.Column(sa.Integer, nullable=False, server_default=sa.text("0")),
    )
    barcode: str | None = Field(default=None, unique=True)
    is_active: bool = Field(
        default=True,
        sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.text("1")),
    )
    deleted_at: str | None = Field(default=None)
    created_at: datetime | None = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
    updated_at: datetime | None = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )

    # Fields not in the database table (extra joined info)
    _category_name: str | None = PrivateAttr(default=None)

    @property
    def category_name(self) -> str | None:
        return self._category_name

    @category_name.setter
    def category_name(self, value: str | None):
        self._category_name = value

    def __init__(self, **data: Any):
        category_name = data.pop("category_name", None)
        super().__init__(**data)
        if category_name is not None:
            self.category_name = category_name

    @model_validator(mode="after")
    def post_init_validation(self) -> "Product":
        """Validate data after initialization."""
        self.validate()
        return self

    def validate(self):
        """Validate product data."""
        if not self.name or len(self.name.strip()) == 0:
            raise ValidationException("Product name is required")

        validate_money(self.cost_price, "Cost price")
        validate_money(self.sell_price, "Sell price")

        if self.barcode:
            self.validate_barcode(self.barcode)

    @staticmethod
    def validate_barcode(barcode: str) -> None:
        """Validate barcode format."""
        validate_barcode(barcode)

    def calculate_profit(self) -> int:
        """Calculate profit in Chilean Pesos."""
        return self.sell_price - self.cost_price

    def calculate_profit_margin(self) -> float:
        """Calculate profit margin as percentage."""
        if self.sell_price == 0:
            return 0.0
        return round((self.calculate_profit() / self.sell_price) * 100, 2)

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "Product":
        """Create Product from database row."""
        return cls(
            id=int(row["id"]),
            name=str(row["name"]),
            description=str(row["description"] or ""),
            category_id=(
                int(row["category_id"]) if row.get("category_id") is not None else None
            ),
            cost_price=int(row["cost_price"] or 0),
            sell_price=int(row["sell_price"] or 0),
            barcode=row.get("barcode"),
            category_name=row.get("category_name") or "Uncategorized",
            is_active=bool(row.get("is_active", 1)),
            deleted_at=row.get("deleted_at"),
            created_at=parse_datetime_cell(row, "created_at"),
            updated_at=parse_datetime_cell(row, "updated_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "cost_price": self.cost_price,
            "sell_price": self.sell_price,
            "barcode": self.barcode,
            "is_active": self.is_active,
            "deleted_at": self.deleted_at,
            "created_at": (
                self.created_at.isoformat()
                if isinstance(self.created_at, datetime)
                else self.created_at
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if isinstance(self.updated_at, datetime)
                else self.updated_at
            ),
        }
