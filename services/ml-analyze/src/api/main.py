"""
FastAPI Application Entry Point
===============================

Main FastAPI application with health check, middleware,
and lifecycle management.
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import httpx
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src import __version__
from src.config.settings import get_settings
from src.utils.errors import MLAnalyzeError
from src.utils.logger import configure_logging, get_logger

# Configure logging at module load
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown events for:
    - Database connection pools
    - Redis connections
    - Resource cleanup
    """
    settings = get_settings()
    logger.info(
        "ml-analyze service starting",
        version=__version__,
        environment=settings.environment,
        port=settings.fastapi_port,
    )

    # TODO: Initialize database connection pool
    # TODO: Initialize Redis connection for arq

    yield

    # Shutdown: cleanup resources
    logger.info("ml-analyze service shutting down")
    # TODO: Close database connections
    # TODO: Close Redis connections


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

        # TODO: Add database health check
        health_status["checks"]["database"] = {"status": "pending"}

        # TODO: Add Redis health check
        health_status["checks"]["redis"] = {"status": "pending"}

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
    # TODO: Include routers when implemented
    # from src.api.routes import analyze, status
    # app.include_router(analyze.router, prefix="/analyze", tags=["Analysis"])
    # app.include_router(status.router, prefix="/status", tags=["Status"])

    return app


# Create application instance
app = create_app()

