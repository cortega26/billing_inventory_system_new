from typing import Any

from models.enums import QUANTITY_PRECISION
from utils.exceptions import ValidationException
from utils.validation.validators import validate_float, validate_integer


def validate_item_count(items: list, max_items: int, entity_label: str) -> None:
    if not items:
        raise ValidationException(f"{entity_label} must have at least one item")
    if len(items) > max_items:
        raise ValidationException(
            f"Too many items in single {entity_label} (max {max_items})"
        )


def validate_line_item(
    item: dict[str, Any],
    *,
    quantity_min: float,
    quantity_max: float | None,
    price_min: int,
    price_max: int | None,
    price_key: str,
) -> None:
    """Validate one sale/purchase line item.

    Intentional per-domain limits (do NOT unify without a product decision):
    - Sales: quantity_min=0.001, no quantity_max, price_min=1, no price_max
      (discounted sales may exceed the 1_000_000 unit-price cap).
    - Purchases: quantity_max=9999999.999, price_max=MAX_PRICE_CLP.
    """
    try:
        product_id = int(item.get("product_id", 0))
        if product_id <= 0:
            raise ValidationException(f"Invalid product ID: {product_id}")
        quantity = validate_float(
            item.get("quantity"), min_value=quantity_min, max_value=quantity_max
        )
        if round(quantity, QUANTITY_PRECISION) != quantity:
            raise ValidationException(
                f"Quantity cannot have more than {QUANTITY_PRECISION} decimal places"
            )
        price = validate_integer(
            item.get(price_key), min_value=price_min, max_value=price_max
        )
        item[price_key] = price
        item["quantity"] = quantity
    except (ValueError, TypeError) as e:
        raise ValidationException(f"Invalid item data: {str(e)}") from e
