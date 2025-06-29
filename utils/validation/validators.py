import re
from typing import Union, Optional, TypeVar, Any, Type, Tuple, List, Callable
from datetime import datetime
from utils.exceptions import ValidationException
from utils.sanitizers import sanitize_html

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

def validate_string(value: str, min_length: int = 0, max_length: Optional[int] = 100) -> str:
    """Validate a string value."""
    if not isinstance(value, str):
        raise ValidationException("Value must be a string")
    
    # Normalize whitespace
    value = " ".join(value.split())
    
    if len(value) < min_length:
        raise ValidationException(f"Value must be at least {min_length} characters long")
    
    if max_length is not None and len(value) > max_length:
        raise ValidationException(f"Value cannot exceed {max_length} characters")
    
    # Use Python string methods instead of REGEXP
    if not all(c.isalnum() or c.isspace() or c in '-.' for c in value):
        raise ValidationException("Value contains invalid characters")
    
    return value

def validate_integer(value: Any, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    """
    Validate and convert a value to integer.
    Specifically for money values in Chilean Pesos.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)

    Returns:
        int: Validated integer value

    Raises:
        ValidationException: If validation fails
    """
    try:
        int_value = int(value)
        if not isinstance(int_value, int):
            raise ValidationException("Value must be an integer")
        if min_value is not None and int_value < min_value:
            raise ValidationException(f"Value must be greater than or equal to {min_value}")
        if max_value is not None and int_value > max_value:
            raise ValidationException(f"Value must be less than or equal to {max_value}")
        return int_value
    except (ValueError, TypeError):
        raise ValidationException(f"Invalid integer value: {value}")

def validate_float(value: Any, min_value: Optional[float] = None, max_value: Optional[float] = None,
                  max_decimals: int = 3) -> float:
    """
    Validate and convert a value to float.
    Used primarily for quantities with up to 3 decimal places.

    Args:
        value: Value to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        max_decimals: Maximum allowed decimal places

    Returns:
        float: Validated float value

    Raises:
        ValidationException: If validation fails
    """
    try:
        float_value = float(value)
        
        # Check decimal places
        str_value = str(float_value)
        if '.' in str_value:
            decimals = len(str_value.split('.')[1])
            if decimals > max_decimals:
                raise ValidationException(f"Value cannot have more than {max_decimals} decimal places")
        
        if min_value is not None and float_value < min_value:
            raise ValidationException(f"Value must be greater than or equal to {min_value}")
        if max_value is not None and float_value > max_value:
            raise ValidationException(f"Value must be less than or equal to {max_value}")
        
        # Round to specified decimal places
        return round(float_value, max_decimals)
    except (ValueError, TypeError):
        raise ValidationException("Invalid float value")

def validate_float_non_negative(value: float) -> float:
    """Validate a non-negative float value with 3 decimal places max."""
    return validate_float(value, min_value=0, max_decimals=3)

def validate_int_non_negative(value: int) -> int:
    """Validate a non-negative integer value."""
    return validate_integer(value, min_value=0)

def validate_money(value: Any, field_name: str = "Amount") -> int:
    """
    Validate a money value (Chilean Pesos).
    Must be a positive integer not exceeding 1.000.000 CLP.

    Args:
        value: Value to validate
        field_name: Name of field for error messages

    Returns:
        int: Validated money value

    Raises:
        ValidationException: If value is invalid
    """
    try:
        money_value = int(round(float(value)))
        if not isinstance(money_value, int):
            raise ValidationException(f"{field_name} must be an integer")
        if money_value < 0:
            raise ValidationException(f"{field_name} cannot be negative")
        if money_value > 1_000_000:
            raise ValidationException(f"{field_name} cannot exceed 1.000.000 CLP")
        return money_value
    except (ValueError, TypeError):
        raise ValidationException(f"Invalid {field_name.lower()} value")

def validate_money_multiplication(amount: int, quantity: float, field_name: str = "Total") -> int:
    """
    Validate multiplication of money value by quantity.
    Result must not exceed 1.000.000 CLP.

    Args:
        amount: Base amount in CLP
        quantity: Quantity multiplier
        field_name: Name of field for error messages

    Returns:
        int: Validated result

    Raises:
        ValidationException: If result is invalid
    """
    try:
        result = int(round(float(amount) * quantity))
        return validate_money(result, field_name)
    except (ValueError, TypeError):
        raise ValidationException(f"Invalid {field_name.lower()} calculation")

def validate_quantity(value: Any) -> float:
    """
    Validate a quantity value.
    Must be a positive float with up to 3 decimal places.

    Args:
        value: Value to validate

    Returns:
        float: Validated quantity value

    Raises:
        ValidationException: If validation fails
    """
    return validate_float(value, min_value=0.001, max_decimals=3)

def validate_price_pair(cost_price: int, sell_price: int) -> None:
    """
    Validate a pair of cost and sell prices.
    Sell price must be greater than or equal to cost price.

    Args:
        cost_price: Cost price to validate
        sell_price: Sell price to validate

    Raises:
        ValidationException: If validation fails
    """
    validated_cost = validate_money(cost_price)
    validated_sell = validate_money(sell_price)
    
    if validated_sell < validated_cost:
        raise ValidationException("Sell price cannot be less than cost price")

def validate_date(date_str: str, format: str = "%Y-%m-%d") -> str:
    try:
        datetime_obj = datetime.strptime(date_str, format)
        
        current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        check_date = datetime_obj.replace(hour=0, minute=0, second=0, microsecond=0)
        if check_date > current_date:
            raise ValidationException("Date cannot be in the future")
        
        return datetime_obj.strftime(format)
    except ValueError:
        raise ValidationException(f"Invalid date format. Expected format: {format}")

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

def validate_with_pattern(value: str, pattern: str, error_message: str = "Invalid format") -> str:
    """Validate string with regex pattern."""
    if not re.match(pattern, value):
        raise ValidationException(error_message)
    return value

def validate_email(value: str) -> str:
    value = validate_string(value)
    return validate_with_pattern(value, r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', "Invalid email format")

def validate_phone(value: str) -> str:
    value = validate_string(value)
    return validate_with_pattern(value, r'^\+?1?\d{9,15}$', "Invalid phone format")

def validate_url(value: str) -> str:
    value = validate_string(value)
    return validate_with_pattern(value, r'^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$', "Invalid URL format")

def validate_identifier(value: str, length: Union[int, Tuple[int, ...]]) -> str:
    """Validate numeric identifier with specific length(s)."""
    value = validate_string(value)
    
    if isinstance(length, int):
        pattern = fr"^\d{{{length}}}$"
        error_message = f"Identifier must be exactly {length} digits"
    else:
        pattern = fr"^\d{{{','.join(map(str, length))}}}$"
        error_message = f"Identifier must be {' or '.join(map(str, length))} digits"
    
    return validate_with_pattern(value, pattern, error_message)

def validate_9digit_identifier(value: str) -> str:
    """Validate a 9-digit identifier."""
    return validate_identifier(value, length=9)

def validate_3or4digit_identifier(value: str) -> str:
    """Validate a 3 or 4-digit identifier."""
    return validate_identifier(value, length=(3, 4))

def validate_list(value: Any, item_validator: Callable[[Any], Any], 
                 min_length: int = 0, max_length: Optional[int] = None) -> List[Any]:
    if not isinstance(value, list):
        raise ValidationException("Value must be a list")
    if len(value) < min_length:
        raise ValidationException(f"List must have at least {min_length} items")
    if max_length is not None and len(value) > max_length:
        raise ValidationException(f"List can have at most {max_length} items")
    return [item_validator(item) for item in value]

def validate_dict(value: Any, key_validator: Callable[[Any], Any], 
                 value_validator: Callable[[Any], Any]) -> dict:
    if not isinstance(value, dict):
        raise ValidationException("Value must be a dictionary")
    return {key_validator(k): value_validator(v) for k, v in value.items()}
