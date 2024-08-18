import re
from typing import Union, Optional, TypeVar, Any, Type, Tuple, List, Callable
from datetime import datetime
from utils.exceptions import ValidationException
from utils.sanitizers import sanitize_html, sanitize_sql

T = TypeVar("T")

def validate(value: Any, validators: List[Callable[[Any], bool]], error_message: str):
    for validator in validators:
        if not validator(value):
            raise ValidationException(error_message)

def validate_and_sanitize(value: Any, validators: List[Callable[[Any], bool]], sanitizer: Callable[[Any], Any], error_message: str) -> Any:
    if not all(validator(value) for validator in validators):
        raise ValidationException(error_message)
    return sanitizer(value)

def is_instance_of(class_or_tuple: Union[Type, Tuple[Type, ...]]) -> Callable[[Any], bool]:
    return lambda value: isinstance(value, class_or_tuple)

def is_non_empty_string(value: Any) -> bool:
    return is_instance_of(str)(value) and len(value.strip()) > 0

def is_numeric(value: Any) -> bool:
    return is_instance_of((int, float))(value)

def is_positive(value: Any) -> bool:
    return is_numeric(value) and value > 0

def is_non_negative(value: Any) -> bool:
    return is_numeric(value) and value >= 0

def is_string(value: str, min_length: int = 1, max_length: int = 100) -> bool:
    return isinstance(value, str) and min_length <= len(value) <= max_length

def is_in_range(min_value: float, max_value: float) -> Callable[[Any], bool]:
    return lambda value: is_numeric(value) and min_value <= value <= max_value

def matches_pattern(pattern: str) -> Callable[[str], bool]:
    compiled_pattern = re.compile(pattern)
    return lambda value: is_instance_of(str)(value) and compiled_pattern.match(value) is not None

def has_length(min_length: int, max_length: int) -> Callable[[Any], bool]:
    return lambda value: min_length <= len(value) <= max_length

def validate_string(value: str, min_length: int = 1, max_length: int = 100, pattern: Optional[str] = None) -> str:
    validators = [is_non_empty_string, has_length(min_length, max_length)]
    if pattern:
        validators.append(matches_pattern(pattern))
    error_message = f"Invalid string. Length should be between {min_length} and {max_length} characters."
    return validate_and_sanitize(
        value,
        validators,
        sanitize_html,
        error_message
    )

def validate_numeric(value: Any, min_value: Optional[float] = None, max_value: Optional[float] = None, is_integer: bool = False) -> Union[int, float]:
    validators: List[Callable[[Any], bool]] = [is_numeric]
    if min_value is not None:
        validators.append(lambda x: x >= min_value)
    if max_value is not None:
        validators.append(lambda x: x <= max_value)
    if is_integer:
        validators.append(is_instance_of(int))
    
    error_message = f"Invalid {'integer' if is_integer else 'numeric'} value. "
    if min_value is not None or max_value is not None:
        error_message += f"Value should be between {min_value} and {max_value}."
    
    result = validate_and_sanitize(
        value,
        validators,
        int if is_integer else float,
        error_message
    )
    return int(result) if is_integer else result

def validate_integer(value: Any, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    result = validate_numeric(value, min_value, max_value, is_integer=True)
    return int(result)

def validate_float(value: Any, min_value: Optional[float] = None, max_value: Optional[float] = None) -> float:
    try:
        float_value = float(value)
        if min_value is not None and float_value < min_value:
            raise ValidationException(f"Value must be greater than or equal to {min_value}")
        if max_value is not None and float_value > max_value:
            raise ValidationException(f"Value must be less than or equal to {max_value}")
        return float_value
    except ValueError:
        raise ValidationException("Invalid float value")

def validate_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
    raise ValidationException(f"Invalid boolean value: {value}")

def validate_date(date_str: str, format: str = "%Y-%m-%d") -> str:
    try:
        # Parse the string to a datetime object to validate it
        datetime_obj = datetime.strptime(date_str, format)
        # Format the datetime object back to a string
        return datetime_obj.strftime(format)
    except ValueError:
        raise ValidationException(f"Invalid date format. Expected format: {format}")

def validate_email(value: str) -> str:
    return validate_string(value, pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def validate_phone(value: str) -> str:
    return validate_string(value, pattern=r'^\+?1?\d{9,15}$')

def validate_url(value: str) -> str:
    return validate_string(value, pattern=r'^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$')

def validate_identifier(value: str, length: Union[int, Tuple[int, ...]]) -> str:
    if isinstance(length, int):
        pattern = r"^\d{{{length}}}$"
        error_message = f"Identifier must be exactly {length} digits"
    else:
        pattern = r"^\d{{{','.join(map(str, length))}}}$"
        error_message = f"Identifier must be {' or '.join(map(str, length))} digits"
    
    return validate_string(value, pattern=pattern, min_length=min(length) if isinstance(length, tuple) else length, max_length=max(length) if isinstance(length, tuple) else length)

def validate_9digit_identifier(value: str) -> str:
    return validate_string(value, min_length=9, max_length=9, pattern=r'^\d{9}$')

def validate_3or4digit_identifier(value: str) -> str:
    return validate_string(value, min_length=3, max_length=4, pattern=r'^\d{3,4}$')

def validate_int_non_negative(value: int) -> int:
    if value < 0:
        raise ValueError("The value must be non-negative.")
    return value

def validate_float_non_negative(value: float) -> float:
    return validate_float(value, min_value=0)

def validate_list(value: Any, item_validator: Callable[[Any], Any], min_length: int = 0, max_length: Optional[int] = None) -> List[Any]:
    if not isinstance(value, list):
        raise ValidationException("Value must be a list")
    if len(value) < min_length:
        raise ValidationException(f"List must have at least {min_length} items")
    if max_length is not None and len(value) > max_length:
        raise ValidationException(f"List can have at most {max_length} items")
    return [item_validator(item) for item in value]

def validate_dict(value: Any, key_validator: Callable[[Any], Any], value_validator: Callable[[Any], Any]) -> dict:
    if not isinstance(value, dict):
        raise ValidationException("Value must be a dictionary")
    return {key_validator(k): value_validator(v) for k, v in value.items()}

def sanitize_sql_input(value: str) -> str:
    return sanitize_sql(value)
