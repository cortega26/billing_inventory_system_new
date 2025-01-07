from typing import Optional

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

class DatabaseException(AppException):
    """Exception raised for database-related errors."""
    pass

class ValidationException(AppException):
    """Exception raised for validation errors."""
    pass

class ConfigurationException(AppException):
    """Exception raised for configuration-related errors."""
    pass

class BusinessLogicException(AppException):
    """Exception raised for business logic errors."""
    pass

class UIException(AppException):
    """Exception raised for UI-related errors."""
    pass

class NetworkException(AppException):
    """Exception raised for network-related errors."""
    pass

class SecurityException(AppException):
    """Exception raised for security-related errors."""
    pass

class NotFoundException(AppException):
    """Exception raised when a requested resource is not found."""
    pass

class ExternalServiceException(AppException):
    """Exception raised for external service-related errors."""
    pass

class FileOperationException(AppException):
    """Exception raised for file operation errors."""
    pass

class AuthenticationException(AppException):
    """Exception raised for authentication-related errors."""
    pass

class AuthorizationException(AppException):
    """Exception raised for authorization-related errors."""
    pass

class DataFormatException(AppException):
    """Exception raised for data format errors."""
    pass

class SystemConfigurationException(AppException):
    """Exception raised for system configuration errors."""
    pass

class ResourceException(AppException):
    """Exception raised for resource-related errors."""
    pass

class ConcurrencyException(AppException):
    """Exception raised for concurrency-related errors."""
    pass
