"""
FastAPI Application Factory

create_app() is the single entry point for building the FastAPI application.
It receives fully-constructed use-case objects from the composition root
(main.py) and configures dependency injection.

Nothing here knows about SQLAlchemy, cv2, or Google Images.
The presentation layer speaks only to use-case interfaces.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from collage_maker.application.use_cases.create_collage import CreateCollageUseCase
from collage_maker.application.use_cases.delete_collage import DeleteCollageUseCase
from collage_maker.application.use_cases.list_collages import ListCollagesUseCase
from collage_maker.application.use_cases.rename_collage import RenameCollageUseCase
from collage_maker.domain.exceptions import DomainError
from collage_maker.domain.ports.collage_storage import ICollageStorage
from collage_maker.presentation.dependencies import set_dependencies
from collage_maker.presentation.routes.collage_routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    logger.info("Starting Collage Maker API v%s", app.version)
    yield
    logger.info("Shutting down Collage Maker API")


def create_app(
    create_uc: CreateCollageUseCase,
    rename_uc: RenameCollageUseCase,
    delete_uc: DeleteCollageUseCase,
    list_uc: ListCollagesUseCase,
    storage: ICollageStorage,
    static_dir: str = "static",
    *,
    debug: bool = False,
    allowed_hosts: list[str] | None = None,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        create_uc: Use case for creating collages
        rename_uc: Use case for renaming collages  
        delete_uc: Use case for deleting collages
        list_uc: Use case for listing collages
        storage: Storage adapter for collage images
        static_dir: Directory for serving static files
        debug: Enable debug mode
        allowed_hosts: List of allowed hosts for TrustedHostMiddleware
        cors_origins: List of allowed CORS origins
        
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Collage Maker API",
        description="Create beautiful collages from text using computer vision and NLP",
        version="2.0.0",
        debug=debug,
        lifespan=lifespan,
        docs_url="/docs" if debug else None,
        redoc_url="/redoc" if debug else None,
    )
    
    # Security middleware - restrict allowed hosts in production
    if allowed_hosts is not None:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=allowed_hosts,
        )
    
    # Configure CORS
    cors_config = {
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["*"],
        "expose_headers": ["X-Request-ID"],
    }
    
    if cors_origins is not None:
        cors_config["allow_origins"] = cors_origins
    elif debug:
        cors_config["allow_origins"] = ["*"]  # Only in debug mode
    else:
        cors_config["allow_origins"] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    app.add_middleware(CORSMiddleware, **cors_config)
    
    # Mount static files for serving images
    try:
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
        logger.info("Mounted static files from %s", static_dir)
    except RuntimeError as e:
        logger.error("Failed to mount static files: %s", e)
        raise
    
    # Set up dependency injection
    set_dependencies(
        create_uc=create_uc,
        rename_uc=rename_uc,
        delete_uc=delete_uc,
        list_uc=list_uc,
        storage=storage,
    )
    
    # Register routes - Fixed: Remove /api/v1 prefix since routes define their own paths
    app.include_router(router)
    
    # Health check endpoint
    @app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
    async def health_check() -> dict[str, str]:
        """Health check endpoint for monitoring."""
        return {"status": "healthy", "service": "collage-maker"}
    
    # Exception handlers
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        """Handle domain-specific errors with structured responses."""
        logger.warning("Domain error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "domain_error",
                "message": str(exc),
                "success": False,
            }
        )
    
    @app.exception_handler(ValueError)
    async def validation_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Handle validation errors."""
        logger.warning("Validation error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error", 
                "message": str(exc),
                "success": False,
            }
        )
    
    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected internal errors."""
        logger.error("Internal server error: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred" if not debug else str(exc),
                "success": False,
            }
        )
    
    return app
