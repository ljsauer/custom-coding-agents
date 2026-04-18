"""
FastAPI Application Factory

create_app() is the single entry point for building the FastAPI application.
It receives fully-constructed use-case objects from the composition root
(main.py) and configures dependency injection.

Nothing here knows about SQLAlchemy, cv2, or Google Images.
The presentation layer speaks only to use-case interfaces.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from collage_maker.application.use_cases.create_collage import CreateCollageUseCase
from collage_maker.application.use_cases.delete_collage import DeleteCollageUseCase
from collage_maker.application.use_cases.list_collages import ListCollagesUseCase
from collage_maker.application.use_cases.rename_collage import RenameCollageUseCase
from collage_maker.domain.exceptions import DomainError
from collage_maker.domain.ports.collage_storage import ICollageStorage
from collage_maker.presentation.dependencies import set_dependencies
from collage_maker.presentation.routes.collage_routes import router


def create_app(
    create_uc: CreateCollageUseCase,
    rename_uc: RenameCollageUseCase,
    delete_uc: DeleteCollageUseCase,
    list_uc: ListCollagesUseCase,
    storage: ICollageStorage,
    static_dir: str = "static",
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
        
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Collage Maker API",
        description="Create beautiful collages from text using computer vision and NLP",
        version="2.0.0",
    )
    
    # Configure CORS for web frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount static files for serving images
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    # Set up dependency injection
    set_dependencies(
        create_uc=create_uc,
        rename_uc=rename_uc,
        delete_uc=delete_uc,
        list_uc=list_uc,
        storage=storage,
    )
    
    # Register routes
    app.include_router(router)
    
    # Global exception handler for domain errors
    @app.exception_handler(DomainError)
    async def domain_error_handler(request, exc: DomainError):
        return JSONResponse(
            status_code=400,
            content={"message": str(exc), "success": False}
        )
    
    return app
