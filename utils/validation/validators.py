import re
from typing import Union, Optional, TypeVar, Any, Type, Tuple, List, Callable
from utils.exceptions import ValidationException
from datetime import datetime

T = TypeVar("T")

def validate(value: Any, validators: List[Callable[[Any], bool]], error_message: str) -> None:
    if not all(validator(value) for validator in validators):
        raise ValidationException(error_message)

def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and len(value.strip()) > 0

def is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float))

def is_positive(value: Any) -> bool:
    return is_numeric(value) and value > 0

def is_non_negative(value: Any) -> bool:
    return is_numeric(value) and value >= 0

def is_in_range(min_value: float, max_value: float) -> Callable[[Any], bool]:
    return lambda value: is_numeric(value) and min_value <= value <= max_value

def matches_pattern(pattern: str) -> Callable[[str], bool]:
    return lambda value: isinstance(value, str) and re.match(pattern, value) is not None

def is_valid_email(value: Any) -> bool:
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return matches_pattern(email_pattern)(value)

def is_valid_phone(value: Any) -> bool:
    phone_pattern = r'^\+?1?\d{9,15}$'
    return matches_pattern(phone_pattern)(value)

def has_length(min_length: int, max_length: int) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, (str, list, tuple, dict)) and min_length <= len(value) <= max_length

def is_instance_of(class_or_tuple: Union[Type, Tuple[Type, ...]]) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, class_or_tuple)

def is_valid_date(value: Any) -> bool:
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    return matches_pattern(date_pattern)(value)

def is_valid_url(value: Any) -> bool:
    url_pattern = r'^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$'
    return matches_pattern(url_pattern)(value)

def is_valid_9digit_identifier(identifier: Any) -> bool:
    return isinstance(identifier, str) and bool(re.match(r"^\d{9}$", identifier))

def is_valid_3or4digit_identifier(identifier: Any) -> bool:
    return isinstance(identifier, str) and bool(re.match(r"^\d{3,4}$", identifier))

def validate_9digit_identifier(identifier: str) -> str:
    if not is_valid_9digit_identifier(identifier):
        raise ValidationException("Identifier must be exactly 9 digits")
    return identifier

def validate_3or4digit_identifier(identifier: str) -> str:
    if not is_valid_3or4digit_identifier(identifier):
        raise ValidationException("Identifier must be either 3 or 4 digits")
    return identifier

def validate_numeric(
    value: Union[int, float, str],
    field_name: str,
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
) -> Union[int, float]:
    try:
        numeric_value = float(value)
        if isinstance(value, str) and value.isdigit():
            numeric_value = int(value)
        if min_value is not None and numeric_value < min_value:
            raise ValidationException(f"{field_name} must be at least {min_value}.")
        if max_value is not None and numeric_value > max_value:
            raise ValidationException(f"{field_name} must not exceed {max_value}.")
        return numeric_value
    except ValueError:
        raise ValidationException(f"{field_name} must be a valid number.")

def validate_string(
    value: str,
    field_name: str,
    max_length: Optional[int] = None,
    min_length: Optional[int] = None,
    pattern: Optional[str] = None,
) -> str:
    stripped_value = value.strip()
    if not stripped_value:
        raise ValidationException(f"{field_name} cannot be empty")
    if min_length and len(stripped_value) < min_length:
        raise ValidationException(f"{field_name} must be at least {min_length} characters long")
    if max_length and len(stripped_value) > max_length:
        raise ValidationException(f"{field_name} must be {max_length} characters or less")
    if pattern and not re.match(pattern, stripped_value):
        raise ValidationException(f"{field_name} does not match the required pattern")
    return stripped_value

def validate_date(date_str: str, format: str = "%Y-%m-%d") -> datetime:
    try:
        return datetime.strptime(date_str, format)
    except ValueError:
        raise ValidationException(f"Invalid date format. Expected format: {format}")

def validate_phone_number(phone: str) -> str:
    phone_regex = r"^\+?1?\d{9,15}$"
    if not re.match(phone_regex, phone):
        raise ValidationException("Invalid phone number")
    return phone

def validate_type(
    value: Any, expected_type: Union[Type[T], Tuple[Type[T], ...]], field_name: str
) -> T:
    if not isinstance(value, expected_type):
        type_names = (
            expected_type.__name__
            if isinstance(expected_type, type)
            else " or ".join(t.__name__ for t in expected_type)
        )
        raise ValidationException(f"{field_name} must be of type {type_names}")
    return value

def validate_non_empty_list(value: List[Any], field_name: str) -> List[Any]:
    if not value:
        raise ValidationException(f"{field_name} cannot be empty")
    return value

def validate_boolean(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
    raise ValidationException(f"{field_name} must be a valid boolean value")