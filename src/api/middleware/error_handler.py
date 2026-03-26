import logging
from collections.abc import Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.core.exception.exceptions import ApplicationException

logger = logging.getLogger(__name__)


async def error_handler_middleware(
    request: Request, call_next: Callable
) -> JSONResponse:
    """Error handling middleware for centralized exception handling."""
    try:
        response = await call_next(request)
        return response
    except ApplicationException as exc:
        logger.warning(
            f"Application exception: {exc.error_code}",
            extra={
                "status_code": exc.status_code,
                "error_code": exc.error_code,
                "message": exc.message,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "status_code": exc.status_code,
            },
        )
    except ValidationError as exc:
        logger.warning(
            f"Validation error on {request.url.path}",
            extra={
                "errors": exc.errors(),
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Validation failed",
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "details": exc.errors(),
            },
        )
    except Exception as exc:
        logger.error(
            f"Unhandled exception on {request.url.path}: {str(exc)}",
            exc_info=True,
            extra={
                "path": request.url.path,
                "method": request.method,
                "exception_type": type(exc).__name__,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )


def setup_error_handlers(app: FastAPI) -> None:
    """Register error handlers for the application."""

    @app.exception_handler(ApplicationException)
    async def application_exception_handler(
        request: Request, exc: ApplicationException
    ) -> JSONResponse:
        logger.warning(
            f"Application exception: {exc.error_code}",
            extra={
                "status_code": exc.status_code,
                "error_code": exc.error_code,
                "message": exc.message,
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        logger.warning(
            f"Validation error on {request.url.path}",
            extra={
                "errors": exc.errors(),
                "path": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Validation failed",
                "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            f"Unhandled exception on {request.url.path}: {str(exc)}",
            exc_info=True,
            extra={
                "path": request.url.path,
                "method": request.method,
                "exception_type": type(exc).__name__,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
