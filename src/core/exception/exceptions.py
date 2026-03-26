from fastapi import status


class ApplicationException(Exception):
    """Base exception for the application."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_SERVER_ERROR"
        super().__init__(self.message)


class ValidationException(ApplicationException):
    """Raised when validation fails."""

    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR") -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
        )


class ResourceNotFoundException(ApplicationException):
    """Raised when a resource is not found."""

    def __init__(self, resource: str, error_code: str = "RESOURCE_NOT_FOUND") -> None:
        message = f"{resource} not found"
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=error_code,
        )


class UnauthorizedException(ApplicationException):
    """Raised when user is not authorized."""

    def __init__(
        self, message: str = "Unauthorized", error_code: str = "UNAUTHORIZED"
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
        )


class ForbiddenException(ApplicationException):
    """Raised when user lacks permissions."""

    def __init__(
        self, message: str = "Forbidden", error_code: str = "FORBIDDEN"
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code=error_code,
        )


class ConflictException(ApplicationException):
    """Raised when resource already exists."""

    def __init__(self, message: str, error_code: str = "CONFLICT") -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code=error_code,
        )
