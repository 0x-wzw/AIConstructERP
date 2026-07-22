"""Raw landing zone (bronze tier) API — unstructured data, before ETL.

Endpoints
  POST /raw/land            proxy-upload a file straight into the landing zone
  POST /raw/presign         issue a pre-signed URL AND pre-register the manifest
  POST /raw/{id}/confirm    confirm a pre-signed upload actually landed
  POST /raw/{id}/etl        promote a landed doc into structured domain data
  GET  /raw                 list the landing zone (optionally by etl_status)
  GET  /raw/{id}            inspect one raw document
  GET  /raw/{id}/download   download the original, untouched bytes

ETL reuses the existing `ingestion.ingest_file` parser so there is a single
source of truth for turning documents into structured fields.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from . import models
from .audit import log_action
from .config import settings
from .database import get_db
from .ingestion import ingest_file
from .models import User
from .raw_store import land_bytes, raw_storage_path, verify_landed
from .schemas import (
    RawDocumentRead,
    RawEtlResult,
    RawPresignRequest,
    RawPresignResponse,
)
from .security import get_current_active_user
from .storage import get_storage_backend, guess_file_category, validate_file

router = APIRouter(prefix="/raw", tags=["raw"])

storage = get_storage_backend()


def _to_read(r: models.RawDocument) -> dict:
    return {
        "id": r.id,
        "tenant_id": r.tenant_id,
        "source": r.source,
        "original_filename": r.original_filename,
        "content_type": r.content_type,
        "size_bytes": r.size_bytes,
        "storage_backend": r.storage_backend,
        "storage_bucket": r.storage_bucket or "",
        "storage_path": r.storage_path,
        "checksum_sha256": r.checksum_sha256 or "",
        "category": r.category or "",
        "etl_status": r.etl_status,
        "etl_error": r.etl_error or "",
        "file_upload_id": r.file_upload_id,
        "received_at": r.received_at.isoformat() if r.received_at else None,
        "processed_at": r.processed_at.isoformat() if r.processed_at else None,
    }


def _scoped(db: Session, user: User):
    q = db.query(models.RawDocument).filter(models.RawDocument.is_archived == False)  # noqa: E712
    if user.tenant_id is not None:
        q = q.filter(models.RawDocument.tenant_id == user.tenant_id)
    return q


def _get_or_404(db: Session, raw_id: int, user: User) -> models.RawDocument:
    r = db.get(models.RawDocument, raw_id)
    if r is None or r.is_archived:
        raise HTTPException(status_code=404, detail="Raw document not found")
    if user.tenant_id is not None and r.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Raw document not found")
    return r


@router.post("/land", response_model=RawDocumentRead, status_code=201,
             summary="Land an unstructured file in the raw zone (proxied)")
async def land(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """Upload a file through the API into the immutable landing zone. No ETL is
    run — the document sits as `landed` until `/raw/{id}/etl` promotes it."""
    content = await file.read()
    error = validate_file(file.filename or "", file.content_type or "", len(content))
    if error:
        raise HTTPException(status_code=400, detail=error)

    path = raw_storage_path(user.tenant_id, file.filename or "unnamed")
    landed = await land_bytes(content, path, file.content_type or "", storage)

    raw = models.RawDocument(
        tenant_id=user.tenant_id,
        source="upload",
        original_filename=file.filename or "unnamed",
        content_type=file.content_type or "",
        size_bytes=landed.size_bytes,
        storage_backend=landed.storage_backend,
        storage_bucket=landed.storage_bucket,
        storage_path=landed.storage_path,
        checksum_sha256=landed.checksum_sha256,
        category=category or guess_file_category(file.filename or "", file.content_type or ""),
        etl_status="landed",
    )
    db.add(raw)
    db.flush()
    log_action(db, user=user, action="create", entity_type="raw_documents",
               entity_id=raw.id, summary=f"Landed raw doc: {raw.original_filename}")
    db.commit()
    db.refresh(raw)
    return _to_read(raw)


@router.post("/presign", response_model=RawPresignResponse,
             summary="Pre-sign a direct-to-cloud landing and pre-register it")
async def presign(req: RawPresignRequest, db: Session = Depends(get_db),
                  user: User = Depends(get_current_active_user)):
    """Issue a pre-signed PUT URL so a large document uploads straight to cloud
    storage, and create the manifest row up front so the object is tracked from
    the moment the URL is issued — closing the orphaned-object gap. The client
    must call `/raw/{id}/confirm` after the PUT completes."""
    error = validate_file(req.filename, req.content_type, 0)
    if error:
        raise HTTPException(status_code=400, detail=error)

    path = raw_storage_path(user.tenant_id, req.filename)
    url = await storage.generate_presigned_upload_url(path, req.content_type)
    if not url:
        raise HTTPException(
            status_code=400,
            detail="Pre-signed uploads require the S3 storage backend.",
        )

    raw = models.RawDocument(
        tenant_id=user.tenant_id,
        source="presign",
        original_filename=req.filename,
        content_type=req.content_type,
        size_bytes=0,
        storage_backend=settings.storage_backend.lower(),
        storage_bucket=getattr(storage, "bucket", "") or "",
        storage_path=path,
        category=req.category or guess_file_category(req.filename, req.content_type),
        etl_status="pending_upload",
    )
    db.add(raw)
    db.flush()
    log_action(db, user=user, action="create", entity_type="raw_documents",
               entity_id=raw.id, summary=f"Issued presign for raw doc: {raw.original_filename}")
    db.commit()
    db.refresh(raw)
    return RawPresignResponse(
        raw_document_id=raw.id,
        storage_path=path,
        url=url,
        expires_in=settings.s3_presigned_expiry_seconds,
    )


@router.post("/{raw_id}/confirm", response_model=RawDocumentRead,
             summary="Confirm a pre-signed upload landed")
async def confirm(raw_id: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_active_user)):
    """Verify the object exists in the landing zone after a direct-to-cloud PUT
    and record its true size/checksum. Marks the document `landed` (ETL-ready)."""
    raw = _get_or_404(db, raw_id, user)
    if raw.etl_status not in ("pending_upload", "landed"):
        raise HTTPException(status_code=409,
                            detail=f"Cannot confirm a document in state '{raw.etl_status}'")

    if settings.raw_verify_checksum_on_confirm:
        landed = await verify_landed(raw.storage_path, storage)
        if landed is None:
            raise HTTPException(status_code=404,
                                detail="Object not found in landing zone — upload not completed")
        raw.size_bytes = landed.size_bytes
        raw.checksum_sha256 = landed.checksum_sha256
    elif not await storage.exists(raw.storage_path):
        raise HTTPException(status_code=404,
                            detail="Object not found in landing zone — upload not completed")

    raw.etl_status = "landed"
    log_action(db, user=user, action="update", entity_type="raw_documents",
               entity_id=raw.id, summary=f"Confirmed landing: {raw.original_filename}")
    db.commit()
    db.refresh(raw)
    return _to_read(raw)


@router.post("/{raw_id}/etl", response_model=RawEtlResult,
             summary="Promote a landed raw doc into structured data (ETL)")
def etl(raw_id: int, db: Session = Depends(get_db),
        user: User = Depends(get_current_active_user)):
    """Run ETL: create a curated FileUpload referencing the immutable raw object,
    then extract structured fields (reusing the ingestion pipeline). The raw
    object itself is never modified, so ETL is safe to re-run."""
    raw = _get_or_404(db, raw_id, user)
    if raw.etl_status == "pending_upload":
        raise HTTPException(status_code=409,
                            detail="Upload not confirmed yet — call /confirm first")

    raw.etl_status = "extracting"
    db.flush()

    # Curated (silver) record — references the raw object read-only. If ETL has
    # already produced one, reuse it so re-runs stay idempotent.
    curated = db.get(models.FileUpload, raw.file_upload_id) if raw.file_upload_id else None
    if curated is None:
        curated = models.FileUpload(
            tenant_id=raw.tenant_id,
            filename=raw.storage_path.rsplit("/", 1)[-1],
            original_filename=raw.original_filename,
            content_type=raw.content_type,
            size_bytes=raw.size_bytes,
            storage_backend=raw.storage_backend,
            storage_bucket=raw.storage_bucket,
            storage_path=raw.storage_path,
            checksum_sha256=raw.checksum_sha256,
            category=raw.category,
            ocr_text=raw.raw_text or "",
            ocr_processed=bool(raw.raw_text),
        )
        db.add(curated)
        db.flush()
        raw.file_upload_id = curated.id

    result = ingest_file(db, curated, user)

    # Mirror the outcome onto the raw manifest and cache any freshly OCR'd text.
    raw = db.get(models.RawDocument, raw_id)
    if result.get("status") == "ingested":
        raw.etl_status = "extracted"
    else:
        raw.etl_status = "failed"
        raw.etl_error = result.get("error", "")[:2000]
    if curated.ocr_text and not raw.raw_text:
        raw.raw_text = curated.ocr_text
    raw.category = curated.category
    raw.processed_at = datetime.utcnow()
    db.commit()

    return RawEtlResult(
        raw_document_id=raw_id,
        etl_status=raw.etl_status,
        file_upload_id=raw.file_upload_id,
        category=raw.category,
        extracted_data=result.get("extracted_data", {}) or {},
        linked_entity_type=result.get("linked_entity_type"),
        linked_entity_id=result.get("linked_entity_id"),
        error=result.get("error"),
    )


@router.get("", response_model=List[RawDocumentRead], summary="List the raw landing zone")
def list_raw(
    etl_status: Optional[str] = Query(None, description="Filter by ETL state"),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    q = _scoped(db, user)
    if etl_status:
        q = q.filter(models.RawDocument.etl_status == etl_status)
    if source:
        q = q.filter(models.RawDocument.source == source)
    return [_to_read(r) for r in q.order_by(models.RawDocument.id.desc()).all()]


@router.get("/{raw_id}", response_model=RawDocumentRead, summary="Inspect a raw document")
def get_raw(raw_id: int, db: Session = Depends(get_db),
            user: User = Depends(get_current_active_user)):
    return _to_read(_get_or_404(db, raw_id, user))


@router.get("/{raw_id}/download", summary="Download the original untouched bytes")
async def download_raw(raw_id: int, db: Session = Depends(get_db),
                       user: User = Depends(get_current_active_user)):
    from fastapi.responses import Response

    raw = _get_or_404(db, raw_id, user)
    if raw.etl_status == "pending_upload":
        raise HTTPException(status_code=409, detail="Upload not confirmed yet")
    content = await storage.read(raw.storage_path)
    return Response(
        content=content,
        media_type=raw.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{raw.original_filename}"'},
    )
