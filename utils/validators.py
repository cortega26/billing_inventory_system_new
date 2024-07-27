import re

def validate_9digit_identifier(identifier):
    if not re.match(r'^\d{9}$', identifier):
        raise ValueError("9-digit identifier must be exactly 9 digits")

def validate_4digit_identifier(identifier):
    if identifier and not re.match(r'^\d{4}$', identifier):
        raise ValueError("4-digit identifier must be exactly 4 digits or empty")

def validate_positive_integer(value, field_name):
    try:
        int_value = int(value)
        if int_value <= 0:
            raise ValueError
    except ValueError:
        raise ValueError(f"{field_name} must be a positive integer")

def validate_positive_float(value, field_name):
    try:
        float_value = float(value)
        if float_value <= 0:
            raise ValueError
    except ValueError:
        raise ValueError(f"{field_name} must be a positive number")

def validate_string(value, field_name, max_length=None):
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty")
    if max_length and len(value) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or less")