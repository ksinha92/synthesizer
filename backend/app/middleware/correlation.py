"""Request correlation ID middleware."""

from __future__ import annotations

import re
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Adds X-Request-ID to every request/response and injects into structlog context."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Accept client-provided ID only if valid UUID format (prevents log injection)
        client_id = request.headers.get("X-Request-ID", "")
        if client_id and UUID_PATTERN.match(client_id):
            request_id = client_id
        else:
            request_id = str(uuid.uuid4())

        # Inject into structlog context for all logs during this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
