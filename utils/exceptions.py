class AppException(Exception):
    """Base exception class for the application."""

    def __init__(self, message, error_code=None, details=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def __str__(self):
        if self.error_code:
            return f"{self.error_code}: {self.message}"
        return self.message

    def __repr__(self):
        return f"{self.__class__.__name__}(message='{self.message}', error_code='{self.error_code}', details={self.details})"


class DatabaseException(AppException):
    """Exception raised for database-related errors."""

    pass


class ValidationException(AppException):
    """Exception raised for validation errors."""

    pass


class ConfigurationException(AppException):
    """Exception raised for configuration-related errors."""

    pass


class UIException(AppException):
    """Exception raised for UI-related errors."""

    pass


class NotFoundException(AppException):
    """Exception raised when a requested resource is not found."""

    pass
