"""FastAPI application factory."""

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException

from app.api.v1 import api_router
from app.api.v1.auth import limiter
from app.config import settings
from app.middleware.correlation import CorrelationIDMiddleware
from app.middleware.error_handler import generic_exception_handler, http_exception_handler, validation_exception_handler
from app.container import Container


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(settings.LOG_LEVEL),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def create_app() -> FastAPI:
    configure_logging()

    container = Container()
    container.wire(modules=[
        "app.api.v1.health",
        "app.api.v1.auth",
        "app.api.v1.projects",
        "app.api.v1.connections",
        "app.api.v1.discovery",
        "app.api.v1.synthetic",
        "app.infrastructure.auth.dependencies",
    ])

    app = FastAPI(
        title="DataWrangler",
        description="AI-Powered Test Data Management Platform",
        version="0.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.container = container  # type: ignore[attr-defined]

    # Middleware ordering note: Starlette wraps middleware in REVERSE add order,
    # so the LAST `add_middleware` call is the OUTERMOST layer that sees an
    # incoming request first. CORS must be outermost so it can answer the
    # preflight OPTIONS request before any other middleware (e.g. rate limiting)
    # has a chance to reject it. The previous order applied SlowAPI before CORS
    # and consequently returned 400 to every preflight, blocking the frontend.

    # Error handlers (standardized format, no stack trace leaks)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Rate limiting — innermost so it only runs for real (non-OPTIONS) requests
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Correlation ID — middle layer, after CORS strips OPTIONS preflights
    app.add_middleware(CorrelationIDMiddleware)

    # CORS — outermost. Handles preflight OPTIONS and adds Access-Control-* headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    app.include_router(api_router)

    return app


app = create_app()
