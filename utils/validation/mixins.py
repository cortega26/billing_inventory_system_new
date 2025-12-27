"""Validation mixins for common validation patterns."""

from utils.exceptions import ValidationException


class ValidationMixin:
    """Mixin for common validation patterns."""

    @staticmethod
    def validate_chilean_phone(phone: str) -> str:
        """Validate Chilean phone number (9 digits starting with 9)."""
        if not phone or len(phone) != 9:
            raise ValidationException("Phone must be 9 digits")
        if not phone.startswith("9"):
            raise ValidationException("Phone must start with 9")
        if not phone.isdigit():
            raise ValidationException("Phone must contain only digits")
        return phone

    @staticmethod
    def validate_department(dept: str) -> str:
        """Validate department number (3 or 4 digits)."""
        if not dept or not dept.isdigit():
            raise ValidationException("Department must be numeric")
        if len(dept) not in (3, 4):
            raise ValidationException("Department must be 3 or 4 digits")
        if dept.startswith("0"):
            raise ValidationException("Department cannot start with 0")
        return dept

    @staticmethod
    def validate_money_clp(amount: int) -> int:
        """Validate Chilean Peso amount."""
        if not isinstance(amount, int):
            raise ValidationException("Amount must be integer")
        if amount < 0:
            raise ValidationException("Amount cannot be negative")
        if amount > 1_000_000:
            raise ValidationException("Amount exceeds maximum (1.000.000 CLP)")
        return amount
