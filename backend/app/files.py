"""File upload, listing, download, and delete — with auth + tenant isolation."""
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from . import models
from .audit import log_action
from .config import settings
from .database import get_db
from .models import User
from .security import get_current_active_user, require_roles
from .storage import (
    FileInfo,
    generate_storage_path,
    get_storage_backend,
    guess_file_category,
    validate_file,
)

router = APIRouter(prefix="/files", tags=["files"])

ORM = ConfigDict(from_attributes=True)

storage = get_storage_backend()


class FileRead(BaseModel):
    model_config = ORM
    id: int
    tenant_id: Optional[int] = None
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    storage_backend: str
    category: str
    ocr_processed: bool
    uploaded_at: str


def _file_to_read(f: models.FileUpload) -> dict:
    return {
        "id": f.id,
        "tenant_id": f.tenant_id,
        "filename": f.filename,
        "original_filename": f.original_filename,
        "content_type": f.content_type,
        "size_bytes": f.size_bytes,
        "storage_backend": f.storage_backend,
        "category": f.category,
        "ocr_processed": f.ocr_processed,
        "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else "",
    }


def _scoped_query(db: Session, user: User, include_archived: bool = False):
    """Return a query for FileUpload filtered by the user's tenant."""
    q = db.query(models.FileUpload)
    if user.tenant_id is not None:
        q = q.filter(models.FileUpload.tenant_id == user.tenant_id)
    if not include_archived:
        q = q.filter(models.FileUpload.is_archived == False)  # noqa: E712
    return q


def _get_file_or_404(db: Session, file_id: int, user: User) -> models.FileUpload:
    f = db.get(models.FileUpload, file_id)
    if f is None:
        raise HTTPException(status_code=404, detail="File not found")
    if user.tenant_id is not None and f.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="File not found")
    if f.is_archived:
        raise HTTPException(status_code=404, detail="File not found")
    return f


@router.post("/upload", response_model=FileRead, status_code=201,
             summary="Upload a file")
async def upload_file(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    content = await file.read()
    size = len(content)

    error = validate_file(file.filename or "", file.content_type or "", size)
    if error:
        raise HTTPException(status_code=400, detail=error)

    path = generate_storage_path(user.tenant_id, file.filename or "unnamed")
    file_info = await storage.save(content, path)
    file_category = category or guess_file_category(file.filename or "", file.content_type or "")

    db_file = models.FileUpload(
        tenant_id=user.tenant_id,
        filename=file_info.filename,
        original_filename=file.filename or "unnamed",
        content_type=file.content_type or "",
        size_bytes=size,
        storage_backend=file_info.storage_backend,
        storage_path=path,
        category=file_category,
    )
    db.add(db_file)
    db.flush()
    log_action(db, user=user, action="create", entity_type="file_uploads",
               entity_id=db_file.id, summary=f"Uploaded file: {db_file.original_filename}")
    db.commit()
    db.refresh(db_file)
    return _file_to_read(db_file)


@router.get("", response_model=List[FileRead], summary="List files")
def list_files(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    q = _scoped_query(db, user)
    if category:
        q = q.filter(models.FileUpload.category == category)
    files = q.order_by(models.FileUpload.id.desc()).all()
    return [_file_to_read(f) for f in files]


@router.get("/{file_id}", response_model=FileRead, summary="Get file metadata")
def get_file(file_id: int, db: Session = Depends(get_db),
             user: User = Depends(get_current_active_user)):
    f = _get_file_or_404(db, file_id, user)
    return _file_to_read(f)


@router.get("/{file_id}/download", summary="Download file content")
async def download_file(file_id: int, db: Session = Depends(get_db),
                         user: User = Depends(get_current_active_user)):
    from fastapi.responses import Response

    f = _get_file_or_404(db, file_id, user)
    content = await storage.read(f.storage_path)
    return Response(
        content=content,
        media_type=f.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{f.original_filename}"'},
    )


@router.delete("/{file_id}", status_code=204, summary="Delete file")
async def delete_file(file_id: int, db: Session = Depends(get_db),
                       user: User = Depends(get_current_active_user)):
    f = _get_file_or_404(db, file_id, user)
    await storage.delete(f.storage_path)
    f.is_archived = True
    log_action(db, user=user, action="archive", entity_type="file_uploads",
               entity_id=file_id, summary=f"Archived file: {f.original_filename}")
    db.commit()