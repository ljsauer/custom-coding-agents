"""
Collage Routes — FastAPI Router

Each route does exactly three things:
  1. Extract and validate input using Pydantic models.
  2. Call a use case via dependency injection.
  3. Return a typed response.

Business logic validation is handled by the domain and surfaces here as
exceptions that are caught and converted into proper HTTP error responses.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, BackgroundTasks
from fastapi.responses import HTMLResponse

from collage_maker.application.use_cases.create_collage import CreateCollageUseCase
from collage_maker.application.use_cases.delete_collage import DeleteCollageUseCase
from collage_maker.application.use_cases.list_collages import ListCollagesUseCase
from collage_maker.application.use_cases.rename_collage import RenameCollageUseCase
from collage_maker.domain.exceptions import (
    CollageCreationError,
    CollageNotFoundError,
    InvalidCollageNameError,
)
from collage_maker.domain.ports.collage_storage import ICollageStorage
from collage_maker.presentation.dependencies import (
    get_create_use_case,
    get_delete_use_case,
    get_list_use_case,
    get_rename_use_case,
    get_storage,
    get_thumbnail_size,
)
from collage_maker.presentation.models.requests import RenameCollageRequest
from collage_maker.presentation.models.responses import (
    CollageListResponse,
    CollageResponse,
    MessageResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def index(
    list_uc: ListCollagesUseCase = Depends(get_list_use_case),
    storage: ICollageStorage = Depends(get_storage),
    img_size: int = Depends(get_thumbnail_size),
) -> str:
    """Render the main collage gallery page."""
    collages = list_uc.execute()
    
    # For now, return a basic HTML response
    # In a full migration, you'd use a template engine like Jinja2
    html_items = []
    for collage in collages:
        image_path = storage.public_path(collage.id)
        html_items.append(
            f'<div class="collage-item">'
            f'<img src="/static/{image_path}" width="{img_size}" height="{img_size * 3//4}" '
            f'alt="Collage: {collage.name}" loading="lazy">'
            f'<h3>{collage.name}</h3>'
            f'<p>Keywords: {", ".join(collage.keyword_texts())}</p>'
            f'<form method="post" action="/api/collage/{collage.id}/rename">'
            f'<input type="text" name="name" value="{collage.name}" required>'
            f'<button type="submit">Rename</button>'
            f'</form>'
            f'<form method="post" action="/api/collage/{collage.id}/delete" '
            f'onsubmit="return confirm(\'Delete this collage?\')">'
            f'<button type="submit">Delete</button>'
            f'</form>'
            f'</div>'
        )
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Collage Gallery</title>
        <style>
            .gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
            .collage-item {{ border: 1px solid #ddd; padding: 15px; border-radius: 8px; }}
            .collage-item img {{ width: 100%; height: auto; }}
            form {{ margin-top: 10px; }}
            input, button {{ margin: 5px; padding: 8px; }}
        </style>
    </head>
    <body>
        <h1>Collage Gallery</h1>
        <form method="post" action="/api/collage" enctype="multipart/form-data">
            <input type="file" name="file" accept=".txt,.md,.rtf" required>
            <button type="submit">Create Collage</button>
        </form>
        <div class="gallery">
            {''.join(html_items)}
        </div>
    </body>
    </html>
    """


@router.get("/api/collages", response_model=CollageListResponse)
async def list_collages(
    list_uc: ListCollagesUseCase = Depends(get_list_use_case),
    storage: ICollageStorage = Depends(get_storage),
) -> CollageListResponse:
    """Get all collages as JSON."""
    collages = list_uc.execute()
    
    collage_responses = [
        CollageResponse(
            id=collage.id,
            name=collage.name,
            keywords=collage.keyword_texts(),
            image_url=f"/static/{storage.public_path(collage.id)}",
            created_at=collage.created_at,
            updated_at=collage.updated_at,
        )
        for collage in collages
    ]
    
    return CollageListResponse(
        collages=collage_responses,
        total=len(collage_responses)
    )


@router.post("/api/collage", response_model=MessageResponse)
async def create_collage(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    create_uc: CreateCollageUseCase = Depends(get_create_use_case),
) -> MessageResponse:
    """Create a new collage from uploaded text file (async background processing)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please upload a text file.")
    
    # Validate file type
    allowed_extensions = {'.txt', '.md', '.rtf'}
    file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
    if f'.{file_ext}' not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"File type not supported. Please use: {', '.join(allowed_extensions)}"
        )
    
    try:
        content = await file.read()
        text = content.decode("utf-8", errors="ignore")
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="The uploaded file appears to be empty.")
        
        if len(text) < 100:
            raise HTTPException(
                status_code=400, 
                detail="Text is too short. Please provide at least 100 characters for meaningful keyword extraction."
            )
        
        # Process collage creation in background for better UX
        background_tasks.add_task(create_uc.execute, text)
        
        return MessageResponse(
            message="Your collage is being created in the background. Please refresh the page in a few moments to see the result."
        )
        
    except CollageCreationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400, 
            detail="Could not decode file as text. Please ensure the file is in UTF-8 encoding."
        )
    except Exception as exc:
        # Log the full exception in production
        raise HTTPException(status_code=500, detail=f"Could not create collage: {exc}")


@router.post("/api/collage/{collage_id}/rename", response_model=MessageResponse)
async def rename_collage_form(
    collage_id: str,
    name: str = Form(..., min_length=1, max_length=100),
    rename_uc: RenameCollageUseCase = Depends(get_rename_use_case),
) -> MessageResponse:
    """Rename a collage (form submission)."""
    return await _rename_collage_impl(collage_id, name, rename_uc)


@router.put("/api/collage/{collage_id}/rename", response_model=MessageResponse)
async def rename_collage_json(
    collage_id: str,
    request: RenameCollageRequest,
    rename_uc: RenameCollageUseCase = Depends(get_rename_use_case),
) -> MessageResponse:
    """Rename a collage (JSON API)."""
    return await _rename_collage_impl(collage_id, request.name, rename_uc)


async def _rename_collage_impl(
    collage_id: str,
    new_name: str,
    rename_uc: RenameCollageUseCase,
) -> MessageResponse:
    """Shared implementation for rename operations."""
    try:
        rename_uc.execute(collage_id, new_name.strip())
        return MessageResponse(message="Collage renamed successfully.")
    except CollageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidCollageNameError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/collage/{collage_id}/delete", response_model=MessageResponse)
@router.delete("/api/collage/{collage_id}", response_model=MessageResponse)
async def delete_collage(
    collage_id: str,
    delete_uc: DeleteCollageUseCase = Depends(get_delete_use_case),
) -> MessageResponse:
    """Delete a collage and its image."""
    try:
        delete_uc.execute(collage_id)
        return MessageResponse(message="Collage deleted successfully.")
    except CollageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
