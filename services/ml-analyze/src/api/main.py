"""
FastAPI Application Entry Point
===============================

Main FastAPI application with health check, middleware,
and lifecycle management.
"""

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from uuid import uuid4

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src import __version__
from src.config.settings import get_settings
from src.db.connection import close_database, init_database
from src.db.connection import health_check as db_health_check
from src.utils.errors import MLAnalyzeError
from src.utils.logger import configure_logging, get_logger

# Configure logging at module load
configure_logging()
logger = get_logger(__name__)

# Global Redis connection for health checks
# Note: Redis type parameter not supported in all versions
_redis_client: aioredis.Redis | None = None  # type: ignore[type-arg]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown events for:
    - Database connection pools
    - Redis connections
    - Resource cleanup
    """
    global _redis_client

    settings = get_settings()
    logger.info(
        "ml-analyze service starting",
        version=__version__,
        environment=settings.environment,
        port=settings.fastapi_port,
    )

    # Initialize database connection pool
    try:
        await init_database(settings)
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        # Continue startup - service can work in degraded mode

    # Initialize Redis connection for health checks and arq
    try:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await _redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error("Failed to connect to Redis", error=str(e))
        _redis_client = None
        # Continue startup - service can work in degraded mode

    yield

    # Shutdown: cleanup resources
    logger.info("ml-analyze service shutting down")

    # Close database connections
    try:
        await close_database()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error("Error closing database connections", error=str(e))

    # Close Redis connection
    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error("Error closing Redis connection", error=str(e))


def create_app() -> FastAPI:
    """
    FastAPI application factory.

    Returns:
        Configured FastAPI application instance
    """
    settings = get_settings()

    app = FastAPI(
        title="ML-Analyze API",
        description=(
            "AI-powered product analysis and matching service for Marketbel. "
            "Handles complex file parsing (PDF tables, Excel merged cells), "
            "vector embeddings, and LLM-based product matching."
        ),
        version=__version__,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # -------------------------------------------------------------------------
    # CORS Middleware
    # -------------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -------------------------------------------------------------------------
    # Request Logging Middleware
    # -------------------------------------------------------------------------
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Any) -> Any:
        """
        Log all incoming requests with timing and correlation ID.

        Adds X-Request-ID header for tracing and X-Process-Time header
        with request duration in seconds.
        """
        # Generate unique request ID for correlation
        request_id = str(uuid4())

        # Start timing
        start_time = time.perf_counter()

        # Log request details
        logger.info(
            "Request received",
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            query=str(request.query_params) if request.query_params else None,
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        process_time = time.perf_counter() - start_time

        # Add correlation headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        # Log response details
        logger.info(
            "Request completed",
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration_ms=round(process_time * 1000, 2),
        )

        return response

    # -------------------------------------------------------------------------
    # Exception Handlers
    # -------------------------------------------------------------------------
    @app.exception_handler(MLAnalyzeError)
    async def ml_analyze_error_handler(
        request: Request, exc: MLAnalyzeError
    ) -> JSONResponse:
        """Handle application-specific errors."""
        logger.error(
            "Application error",
            error_type=type(exc).__name__,
            message=exc.message,
            details=exc.details,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": type(exc).__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unexpected errors."""
        logger.exception(
            "Unexpected error",
            error_type=type(exc).__name__,
            message=str(exc),
            path=str(request.url),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
            },
        )

    # -------------------------------------------------------------------------
    # Health Check Endpoint
    # -------------------------------------------------------------------------
    @app.get(
        "/health",
        tags=["Health"],
        summary="Health check endpoint",
        response_model=dict[str, Any],
    )
    async def health_check() -> dict[str, Any]:
        """
        Check service health status.

        Returns health status of the service and its dependencies:
        - Database connectivity
        - Ollama API availability
        - Redis connectivity
        """
        health_status: dict[str, Any] = {
            "status": "healthy",
            "version": __version__,
            "service": "ml-analyze",
            "checks": {},
        }

        # Check Ollama API
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.ollama_base_url}/api/tags")
                health_status["checks"]["ollama"] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "url": settings.ollama_base_url,
                }
        except Exception as e:
            health_status["checks"]["ollama"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health_status["status"] = "degraded"

        # Check database connection
        db_status = await db_health_check()
        health_status["checks"]["database"] = db_status
        if db_status.get("status") != "healthy":
            health_status["status"] = "degraded"

        # Check Redis connection
        if _redis_client:
            try:
                import time

                start = time.perf_counter()
                await _redis_client.ping()
                latency = (time.perf_counter() - start) * 1000
                health_status["checks"]["redis"] = {
                    "status": "healthy",
                    "latency_ms": round(latency, 2),
                }
            except Exception as e:
                health_status["checks"]["redis"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                health_status["status"] = "degraded"
        else:
            health_status["checks"]["redis"] = {
                "status": "not_initialized",
                "error": "Redis client not available",
            }
            health_status["status"] = "degraded"

        return health_status

    # -------------------------------------------------------------------------
    # API Info Endpoint
    # -------------------------------------------------------------------------
    @app.get(
        "/",
        tags=["Info"],
        summary="API information",
    )
    async def api_info() -> dict[str, str]:
        """Return basic API information."""
        return {
            "service": "ml-analyze",
            "version": __version__,
            "description": "AI-powered product analysis and matching service",
            "docs": "/docs",
        }

    # -------------------------------------------------------------------------
    # Register Routers
    # -------------------------------------------------------------------------
    from src.api.routes import analyze_router, status_router

    app.include_router(analyze_router, prefix="/analyze", tags=["Analysis"])
    app.include_router(status_router, prefix="/analyze/status", tags=["Status"])

    return app


# Create application instance
app = create_app()

