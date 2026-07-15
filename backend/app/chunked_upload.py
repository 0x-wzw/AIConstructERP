"""Chunked upload handler — for large tender documents (50-500MB).

Flow:
  1. Client POSTs /api/files/upload/init with filename + total_size
     → Server returns upload_id + chunk_size
  2. Client POSTs /api/files/upload/{upload_id}/chunk with chunk_index + data
     → Server stores chunk in temp dir
  3. Client POSTs /api/files/upload/{upload_id}/complete
     → Server assembles chunks, computes SHA-256, stores final file
     → Returns file_metadata_id for attaching to entities

Chunks are stored in a temp directory and cleaned up after TTL.
"""
from __future__ import annotations

import hashlib
import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from . import models, schemas
from .config import settings
from .database import get_db
from .filestore import get_file_store
from .security import get_current_active_user

router = APIRouter(prefix="/api/files/upload", tags=["chunked_upload"])

# In-memory session tracking
# upload_id -> {"filename": ..., "total_chunks": ..., "received_chunks": set, "chunk_size": ..., "total_size": ..., "created_at": ...}
_upload_sessions: dict = {}
_lock = threading.Lock()


def _get_chunk_dir(upload_id: str) -> Path:
    return Path(settings.chunk_temp_dir) / upload_id


def _cleanup_expired_sessions():
    """Remove sessions older than chunk_ttl_seconds."""
    now = time.time()
    expired = [
        uid for uid, session in _upload_sessions.items()
        if now - session["created_at"] > settings.chunk_ttl_seconds
    ]
    for uid in expired:
        _cleanup_session(uid)


def _cleanup_session(upload_id: str):
    _upload_sessions.pop(upload_id, None)
    chunk_dir = _get_chunk_dir(upload_id)
    if chunk_dir.exists():
        shutil.rmtree(chunk_dir, ignore_errors=True)


@router.post("/init", response_model=dict,
             summary="Initialize a chunked upload session")
def init_upload(
    filename: str = Form(...),
    total_size: int = Form(...),
    content_type: str = Form("application/octet-stream"),
    user: models.User = Depends(get_current_active_user),
):
    """Initialize a chunked upload for large files (e.g. tender documents).
    
    Returns an upload_id that the client uses for subsequent chunk uploads.
    """
    if total_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.max_upload_size_bytes // (1024*1024)} MB.",
        )

    upload_id = uuid.uuid4().hex
    chunk_size = settings.upload_chunk_size_bytes
    total_chunks = (total_size + chunk_size - 1) // chunk_size

    if total_chunks > settings.max_chunks_per_upload:
        raise HTTPException(
            status_code=413,
            detail=f"Too many chunks ({total_chunks}). Max {settings.max_chunks_per_upload}.",
        )

    # Create temp directory
    chunk_dir = _get_chunk_dir(upload_id)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    with _lock:
        _cleanup_expired_sessions()
        _upload_sessions[upload_id] = {
            "filename": filename,
            "content_type": content_type,
            "total_size": total_size,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks,
            "received_chunks": set(),
            "created_at": time.time(),
            "uploaded_by": user.id,
        }

    return {
        "upload_id": upload_id,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
        "filename": filename,
        "content_type": content_type,
    }


@router.post("/{upload_id}/chunk", response_model=dict,
             summary="Upload a single chunk")
async def upload_chunk(
    upload_id: str,
    chunk_index: int = Form(...),
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_active_user),
):
    """Upload a single chunk of a file.
    
    Chunks should be sent in order but the server handles out-of-order chunks.
    """
    session = _upload_sessions.get(upload_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Upload session not found or expired")

    if chunk_index < 0 or chunk_index >= session["total_chunks"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid chunk index {chunk_index}. Must be 0-{session['total_chunks'] - 1}.",
        )

    data = await file.read()
    if len(data) > session["chunk_size"]:
        raise HTTPException(
            status_code=413,
            detail=f"Chunk too large. Max {session['chunk_size']} bytes.",
        )

    # Store chunk
    chunk_dir = _get_chunk_dir(upload_id)
    chunk_path = chunk_dir / f"{chunk_index:06d}"
    chunk_path.write_bytes(data)

    with _lock:
        session["received_chunks"].add(chunk_index)

    return {
        "upload_id": upload_id,
        "chunk_index": chunk_index,
        "size_bytes": len(data),
        "received": len(session["received_chunks"]),
        "total": session["total_chunks"],
    }


@router.post("/{upload_id}/complete", response_model=schemas.UploadResponse,
             summary="Complete a chunked upload and assemble the file")
def complete_upload(
    upload_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_active_user),
):
    """Assemble all chunks into the final file, compute checksum, and store.
    
    Returns the file_metadata_id for attaching to entities via entity_files.
    """
    session = _upload_sessions.get(upload_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Upload session not found or expired")

    if len(session["received_chunks"]) != session["total_chunks"]:
        missing = sorted(set(range(session["total_chunks"])) - session["received_chunks"])
        raise HTTPException(
            status_code=400,
            detail=f"Missing chunks: {missing}. "
                   f"Received {len(session['received_chunks'])}/{session['total_chunks']}.",
        )

    # Assemble chunks in order
    chunk_dir = _get_chunk_dir(upload_id)
    sha256 = hashlib.sha256()
    assembled = bytearray()

    for i in range(session["total_chunks"]):
        chunk_path = chunk_dir / f"{i:06d}"
        if not chunk_path.exists():
            raise HTTPException(status_code=500, detail=f"Chunk {i} missing from disk")
        data = chunk_path.read_bytes()
        sha256.update(data)
        assembled.extend(data)

    # Save to file store
    store = get_file_store()
    storage_path, original_name, size_bytes, checksum = store.save(
        bytes(assembled), session["filename"], session["content_type"]
    )

    # Record metadata in DB
    fm = models.FileMetadata(
        original_name=original_name,
        storage_path=storage_path,
        content_type=session["content_type"],
        size_bytes=size_bytes,
        checksum_sha256=checksum,
        uploaded_by=user.id,
    )
    db.add(fm)
    db.commit()
    db.refresh(fm)

    # Cleanup temp files
    _cleanup_session(upload_id)

    return schemas.UploadResponse(
        file_id=fm.id,
        original_name=original_name,
        size_bytes=size_bytes,
        storage_path=storage_path,
        checksum_sha256=checksum,
        upload_url=store.get_url(storage_path),
    )


@router.get("/{upload_id}/status", response_model=dict,
            summary="Check upload progress")
def upload_status(
    upload_id: str,
    user: models.User = Depends(get_current_active_user),
):
    """Check the status of an in-progress chunked upload."""
    session = _upload_sessions.get(upload_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Upload session not found or expired")

    return {
        "upload_id": upload_id,
        "filename": session["filename"],
        "total_size": session["total_size"],
        "chunk_size": session["chunk_size"],
        "total_chunks": session["total_chunks"],
        "received_chunks": len(session["received_chunks"]),
        "missing_chunks": sorted(
            set(range(session["total_chunks"])) - session["received_chunks"]
        ),
        "progress_pct": round(
            len(session["received_chunks"]) / session["total_chunks"] * 100, 1
        ),
    }


@router.delete("/{upload_id}", status_code=204,
               summary="Cancel and clean up an upload")
def cancel_upload(
    upload_id: str,
    user: models.User = Depends(get_current_active_user),
):
    """Cancel an in-progress upload and clean up temp files."""
    _cleanup_session(upload_id)
