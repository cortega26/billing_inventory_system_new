from datetime import datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from pydantic import PrivateAttr, model_validator
from sqlmodel import Field, SQLModel

from models.enums import MAX_PRICE_CLP
from utils.exceptions import ValidationException


class Product(SQLModel, table=True):
    """Product entity with SQLModel implementation."""

    __tablename__ = "products"

    __table_args__ = (
        sa.CheckConstraint("cost_price >= 0", name="check_cost_price_positive"),
        sa.CheckConstraint("sell_price >= 0", name="check_sell_price_positive"),
        sa.CheckConstraint("is_active IN (0, 1)", name="check_product_active"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = Field(default=None)
    category_id: Optional[int] = Field(
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
    barcode: Optional[str] = Field(default=None, unique=True)
    is_active: bool = Field(
        default=True,
        sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.text("1")),
    )
    deleted_at: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.now,
        sa_column=sa.Column(sa.DateTime, nullable=True, server_default=sa.func.now()),
    )

    # Fields not in the database table (extra joined info)
    _category_name: Optional[str] = PrivateAttr(default=None)

    @property
    def category_name(self) -> Optional[str]:
        return self._category_name

    @category_name.setter
    def category_name(self, value: Optional[str]):
        self._category_name = value

    def __init__(self, **data: Any):
        category_name = data.pop("category_name", None)
        for field in ("cost_price", "sell_price"):
            if field in data:
                val = data[field]
                if not isinstance(val, int) or isinstance(val, bool):
                    raise ValidationException(
                        f"{field} must be an integer (CLP, no decimals)"
                    )
        super().__init__(**data)
        if category_name is not None:
            self.category_name = category_name
        self.validate()

    @model_validator(mode="after")
    def post_init_validation(self) -> "Product":
        """Validate data after initialization."""
        self.validate()
        return self

    def validate(self):
        """Validate product data."""
        if not self.name or len(self.name.strip()) == 0:
            raise ValidationException("Product name is required")

        if not isinstance(self.cost_price, int) or isinstance(self.cost_price, bool):
            raise ValidationException(
                "cost_price must be an integer (CLP, no decimals)"
            )
        if not isinstance(self.sell_price, int) or isinstance(self.sell_price, bool):
            raise ValidationException(
                "sell_price must be an integer (CLP, no decimals)"
            )

        if self.cost_price < 0:
            raise ValidationException("Cost price cannot be negative")

        if self.sell_price < 0:
            raise ValidationException("Sell price cannot be negative")

        if self.cost_price > MAX_PRICE_CLP:
            raise ValidationException(
                f"Cost price exceeds maximum ({MAX_PRICE_CLP:,.0f} CLP)"
            )

        if self.sell_price > MAX_PRICE_CLP:
            raise ValidationException(
                f"Sell price exceeds maximum ({MAX_PRICE_CLP:,.0f} CLP)"
            )

        if self.barcode:
            self.validate_barcode(self.barcode)

    @staticmethod
    def validate_barcode(barcode: str) -> None:
        """Validate barcode format."""
        if not barcode:
            return

        if not barcode.isdigit():
            raise ValidationException("Barcode must contain only digits")

        valid_lengths = {8, 12, 13, 14}
        if len(barcode) not in valid_lengths:
            raise ValidationException(f"Barcode must be one of: {valid_lengths} digits")

    def calculate_profit(self) -> int:
        """Calculate profit in Chilean Pesos."""
        return self.sell_price - self.cost_price

    def calculate_profit_margin(self) -> float:
        """Calculate profit margin as percentage."""
        if self.sell_price == 0:
            return 0.0
        return round((self.calculate_profit() / self.sell_price) * 100, 2)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "Product":
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

    def to_dict(self) -> Dict[str, Any]:
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
            "created_at": self.created_at.isoformat()
            if isinstance(self.created_at, datetime)
            else self.created_at,
            "updated_at": self.updated_at.isoformat()
            if isinstance(self.updated_at, datetime)
            else self.updated_at,
        }
