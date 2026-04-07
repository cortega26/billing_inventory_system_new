from typing import Any, Callable, Dict, List

from utils.validation.validators import (
    validate_integer,
    validate_money,
    validate_string,
)


def normalize_create_product_data(validated_data: Dict[str, Any]) -> Dict[str, Any]:
    normalized_data = dict(validated_data)
    normalized_data.setdefault("barcode", None)
    normalized_data.setdefault("category_id", None)
    normalized_data.setdefault("description", None)
    return normalized_data


def build_product_update_statement(
    product_id: int, validated_data: Dict[str, Any]
) -> tuple[str, Dict[str, Any], List[str]]:
    updated_fields = list(validated_data.keys())
    params = dict(validated_data)
    params["product_id"] = product_id
    set_clause = ", ".join(f"{key} = :{key}" for key in updated_fields)
    query = f"UPDATE products SET {set_clause} WHERE id = :product_id"
    return query, params, updated_fields


def validate_name_field(
    data: Dict[str, Any], validated: Dict[str, Any], is_create: bool
) -> None:
    if "name" not in data and not is_create:
        return
    validated["name"] = validate_string(
        data.get("name", ""), min_length=1, max_length=100
    )


def validate_description_field(
    data: Dict[str, Any], validated: Dict[str, Any]
) -> None:
    if "description" not in data:
        return
    validated["description"] = validate_string(
        data.get("description", ""), min_length=0, max_length=500
    )


def validate_category_field(
    data: Dict[str, Any], validated: Dict[str, Any]
) -> None:
    if "category_id" not in data:
        return
    category_id = data.get("category_id")
    validated["category_id"] = (
        validate_integer(category_id, min_value=1)
        if category_id is not None
        else None
    )


def validate_money_field(
    data: Dict[str, Any], validated: Dict[str, Any], field: str, label: str
) -> None:
    if field not in data:
        return
    value = data.get(field)
    if value is not None:
        validated[field] = validate_money(value, label)


def validate_barcode_field(
    data: Dict[str, Any],
    validated: Dict[str, Any],
    barcode_validator: Callable[[str], None],
) -> None:
    if "barcode" not in data:
        return
    barcode = data.get("barcode")
    if barcode is not None:
        barcode_validator(barcode)
        validated["barcode"] = barcode