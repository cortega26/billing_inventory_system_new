class AppException(Exception):
    """Base exception for the application."""


class DatabaseException(AppException):
    """Exception raised for database-related errors."""


class ValidationException(AppException):
    """Exception raised for data validation errors."""


class NotFoundException(AppException):
    """Exception raised when a requested resource is not found."""


class AuthorizationException(AppException):
    """Exception raised for authorization-related errors."""


class ConfigurationException(AppException):
    """Exception raised for configuration-related errors."""


class ExternalServiceException(AppException):
    """Exception raised for errors related to external service interactions."""


class ConcurrencyException(AppException):
    """Exception raised for concurrency-related errors."""


class BusinessLogicException(AppException):
    """Exception raised for violations of business logic rules."""


class UIException(AppException):
    """Exception raised for UI-related errors."""
