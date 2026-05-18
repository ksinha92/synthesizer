"""Global error handler — standardized error responses, no stack trace leaks."""

from __future__ import annotations

import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = structlog.get_logger()


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with standardized format."""
    request_id = request.headers.get("X-Request-ID", "")

    body = exc.detail if isinstance(exc.detail, dict) else {"error": "http_error", "detail": str(exc.detail)}
    body["request_id"] = request_id

    return JSONResponse(status_code=exc.status_code, content=body)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors."""
    request_id = request.headers.get("X-Request-ID", "")
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "detail": str(exc.errors()[:3]),  # Limit error detail length
            "request_id": request_id,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors — log full traceback, return generic message."""
    request_id = request.headers.get("X-Request-ID", "")

    await logger.aerror(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=str(request.url),
        method=request.method,
        request_id=request_id,
        exc_info=True,
    )

    # NEVER expose stack trace to client
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "An unexpected error occurred. Please try again or contact support.",
            "request_id": request_id,
        },
    )
