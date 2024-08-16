# utils/exceptions.py

class AppException(Exception):
    """Base exception for the application."""
    def __init__(self, message: str, error_code: str = "APP_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

class DatabaseException(AppException):
    """Exception raised for database-related errors."""
    def __init__(self, message: str, error_code: str = "DB_ERROR"):
        super().__init__(message, error_code)

class ValidationException(AppException):
    """Exception raised for data validation errors."""
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR"):
        super().__init__(message, error_code)

class NotFoundException(AppException):
    """Exception raised when a requested resource is not found."""
    def __init__(self, message: str, error_code: str = "NOT_FOUND"):
        super().__init__(message, error_code)

class AuthorizationException(AppException):
    """Exception raised for authorization-related errors."""
    def __init__(self, message: str, error_code: str = "AUTH_ERROR"):
        super().__init__(message, error_code)

class ConfigurationException(AppException):
    """Exception raised for configuration-related errors."""
    def __init__(self, message: str, error_code: str = "CONFIG_ERROR"):
        super().__init__(message, error_code)

class ExternalServiceException(AppException):
    """Exception raised for errors related to external service interactions."""
    def __init__(self, message: str, error_code: str = "EXT_SERVICE_ERROR"):
        super().__init__(message, error_code)

class ConcurrencyException(AppException):
    """Exception raised for concurrency-related errors."""
    def __init__(self, message: str, error_code: str = "CONCURRENCY_ERROR"):
        super().__init__(message, error_code)

class BusinessLogicException(AppException):
    """Exception raised for violations of business logic rules."""
    def __init__(self, message: str, error_code: str = "BUSINESS_LOGIC_ERROR"):
        super().__init__(message, error_code)

class UIException(AppException):
    """Exception raised for UI-related errors."""
    def __init__(self, message: str, error_code: str = "UI_ERROR"):
        super().__init__(message, error_code)