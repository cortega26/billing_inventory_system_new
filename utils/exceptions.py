from typing import Optional

class AppException(Exception):
    """Base exception for the application."""
    def __init__(self, message: str, error_code: str = "APP_ERROR", details: Optional[dict] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        return f"{self.error_code}: {self.message}"

class DatabaseException(AppException):
    """Exception raised for database-related errors."""
    def __init__(self, message: str, error_code: str = "DB_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, details)

class ValidationException(AppException):
    """Exception raised for data validation errors."""
    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, details)

class NotFoundException(AppException):
    """Exception raised when a requested resource is not found."""
    def __init__(self, message: str, error_code: str = "NOT_FOUND", details: Optional[dict] = None):
        super().__init__(message, error_code, details)

class AuthorizationException(AppException):
    """Exception raised for authorization-related errors."""
    def __init__(self, message: str, error_code: str = "AUTH_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, details)

class ConfigurationException(AppException):
    """Exception raised for configuration-related errors."""
    def __init__(self, message: str, error_code: str = "CONFIG_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, details)

class ExternalServiceException(AppException):
    """Exception raised for errors related to external service interactions."""
    def __init__(self, message: str, error_code: str = "EXT_SERVICE_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, details)

class ConcurrencyException(AppException):
    """Exception raised for concurrency-related errors."""
    def __init__(self, message: str, error_code: str = "CONCURRENCY_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, details)

class BusinessLogicException(AppException):
    """Exception raised for violations of business logic rules."""
    def __init__(self, message: str, error_code: str = "BUSINESS_LOGIC_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, details)

class UIException(AppException):
    """Exception raised for UI-related errors."""
    def __init__(self, message: str, error_code: str = "UI_ERROR", details: Optional[dict] = None):
        super().__init__(message, error_code, details)
