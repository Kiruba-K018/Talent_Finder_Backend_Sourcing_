import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.start_time = time.time()

        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": str(dict(request.query_params))
                if request.query_params
                else None,
                "client_ip": request.client.host if request.client else None,
            },
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed_time = time.time() - request.state.start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=True,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "elapsed_time_ms": round(elapsed_time * 1000, 2),
                    "exception_type": type(exc).__name__,
                },
            )
            raise

        elapsed_time = time.time() - request.state.start_time

        logger.info(
            f"Response completed: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "elapsed_time_ms": round(elapsed_time * 1000, 2),
                "client_ip": request.client.host if request.client else None,
            },
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(round(elapsed_time * 1000, 2))

        return response
