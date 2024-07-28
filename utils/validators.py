import re
from typing import Union

def validate_9digit_identifier(identifier: str) -> None:
    if not re.match(r'^\d{9}$', identifier):
        raise ValueError("9-digit identifier must be exactly 9 digits")

def validate_3or4digit_identifier(identifier: str) -> None:
    if not re.match(r'^\d{3,4}$', identifier):
        raise ValueError("3 or 4-digit identifier must be either 3 or 4 digits")

def validate_positive_integer(value: Union[int, str], field_name: str) -> int:
    try:
        int_value = int(value)
        if int_value <= 0:
            raise ValueError
        return int_value
    except ValueError:
        raise ValueError(f"{field_name} must be a positive integer")

def validate_positive_float(value: Union[float, str], field_name: str) -> float:
    try:
        float_value = float(value)
        if float_value <= 0:
            raise ValueError
        return float_value
    except ValueError:
        raise ValueError(f"{field_name} must be a positive number")

def validate_string(value: str, field_name: str, max_length: Union[int, None] = None) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if max_length and len(value) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or less")
    return value.strip()