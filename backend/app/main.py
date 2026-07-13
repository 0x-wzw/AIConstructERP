"""AIConstructERP — AI-native ERP backend.

Architecture: Unified Entity System
  - One `entities` table for all domain objects
  - Dynamic attributes via `entity_attributes`
  - Graph relationships via `entity_relationships`
  - Activity stream via `entity_activities`
  - Comments via `entity_comments`
  - File attachments via `entity_files`
  - Metamodel via `entity_types` + `attribute_definitions`
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import router as auth_router
from .chunked_upload import router as chunked_upload_router
from .config import settings
from .crud import make_crud_router
from .database import Base, SessionLocal, engine, get_db
from .encryption import decrypt_financial_proposal, encrypt_financial_proposal
from .filestore import get_file_store
from .scheduler import start_scheduler, stop_scheduler
from .security import Role, get_current_active_user, require_roles

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
)
log = logging.getLogger("aicontructerp")

PM = Role.project_manager.value
ACCT = Role.accounting.value
ADMIN = Role.admin.value


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from .seed import seed_builtin_types, seed_demo_users, seed_demo_data
        seed_builtin_types(db)
        seed_demo_users(db)
        seed_demo_data(db)
    finally:
        db.close()
    # Start background scheduler
    start_scheduler()
    log.info("AIConstructERP started — scheduler active")
    yield
    # Stop background scheduler
    stop_scheduler()
    log.info("AIConstructERP shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AIConstructERP — AI-native ERP with unified entity system.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*"
    else [o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Logging Middleware ────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    log.info(
        "%s %s → %s (%.0fms)",
        request.method, request.url.path, response.status_code, duration * 1000,
    )
    return response


# ── Global Exception Handler ──────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# ══════════════════════════════════════════════════════════════════════════
# ENTITY TYPE METAMODEL
# ══════════════════════════════════════════════════════════════════════════

ROUTERS = [
    make_crud_router(
        model=models.EntityType, read_schema=schemas.EntityTypeRead,
        create_schema=schemas.EntityTypeCreate, update_schema=None,
        prefix="/entity-types", tag="entity_types",
        search_fields=["slug", "name"],
        write_roles=[ADMIN],
    ),
    make_crud_router(
        model=models.AttributeDefinition, read_schema=schemas.AttributeDefinitionRead,
        create_schema=schemas.AttributeDefinitionCreate, update_schema=None,
        prefix="/attribute-definitions", tag="attribute_definitions",
        search_fields=["slug", "name"],
        write_roles=[ADMIN],
    ),
]

app.include_router(auth_router, prefix="/api")
app.include_router(chunked_upload_router)
for r in ROUTERS:
    app.include_router(r, prefix="/api")


# ══════════════════════════════════════════════════════════════════════════
# ENTITY CRUD — the universal endpoint
# ══════════════════════════════════════════════════════════════════════════


@app.post("/api/entities", response_model=schemas.EntityRead, status_code=201,
          tags=["entities"], summary="Create any entity",
          dependencies=[Depends(require_roles(PM, ADMIN))])
def create_entity(
    payload: schemas.EntityCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_active_user),
):
    """Create any entity in the system with dynamic attributes."""
    # Resolve entity type
    etype = db.query(models.EntityType).filter(
        models.EntityType.slug == payload.entity_type_slug
    ).first()
    if etype is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown entity type: {payload.entity_type_slug}. "
                   f"Create it via POST /api/entity-types first.",
        )

    # Create the entity
    entity = models.Entity(
        entity_type_id=etype.id,
        title=payload.title,
        reference_no=payload.reference_no,
        status=payload.status,
        parent_id=payload.parent_id,
        summary=payload.summary,
        owner_id=user.id,
    )
    db.add(entity)
    db.flush()  # Get entity.id

    # Create attributes
    for attr in payload.attributes:
        ea = models.EntityAttribute(
            entity_id=entity.id,
            slug=attr.slug,
            value_string=attr.value_string,
            value_text=attr.value_text,
            value_number=attr.value_number,
            value_date=attr.value_date,
            value_datetime=attr.value_datetime,
            value_boolean=attr.value_boolean,
            value_json=attr.value_json,
            value_entity_id=attr.value_entity_id,
            value_user_id=attr.value_user_id,
        )
        db.add(ea)

    # Record activity
    db.add(models.EntityActivity(
        entity_id=entity.id,
        activity_type="created",
        description=f"{etype.name} '{entity.title}' created",
        performed_by=user.id,
    ))

    db.commit()
    db.refresh(entity)
    return schemas.EntityRead.from_orm_with_type(entity)


@app.get("/api/entities",
         tags=["entities"], summary="List entities",
         dependencies=[Depends(get_current_active_user)])
def list_entities(
    entity_type: str = Query("", description="Filter by entity type slug"),
    status: str = Query("", description="Filter by status"),
    q: str = Query("", description="Search title and reference_no"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(models.Entity)

    if entity_type:
        etype = db.query(models.EntityType).filter(
            models.EntityType.slug == entity_type
        ).first()
        if etype:
            query = query.filter(models.Entity.entity_type_id == etype.id)

    if status:
        query = query.filter(models.Entity.status == status)

    if q:
        like = f"%{q}%"
        query = query.filter(
            models.Entity.title.ilike(like) | models.Entity.reference_no.ilike(like)
        )

    # Count total for pagination headers
    total = query.count()
    page = (skip // limit) + 1 if limit > 0 else 1

    results = (
        query.order_by(models.Entity.id.desc())
        .offset(skip).limit(limit)
        .all()
    )

    # Build response with pagination headers
    from fastapi.responses import JSONResponse

    data = [schemas.EntityRead.model_validate(e) for e in results]
    response = JSONResponse(content=[d.model_dump(mode="json") for d in data])
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    response.headers["X-Per-Page"] = str(limit)
    return response


@app.get("/api/entities/{entity_id}",
         tags=["entities"], summary="Get entity with attributes",
         dependencies=[Depends(get_current_active_user)])
def get_entity(entity_id: int, db: Session = Depends(get_db)):
    entity = db.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return schemas.EntityRead.from_orm_with_type(entity)


@app.patch("/api/entities/{entity_id}", response_model=schemas.EntityRead,
           tags=["entities"], summary="Update entity",
           dependencies=[Depends(require_roles(PM, ADMIN))])
def update_entity(
    entity_id: int,
    payload: schemas.EntityUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_active_user),
):
    entity = db.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Track changes for activity
    changes = []

    if payload.title is not None and payload.title != entity.title:
        changes.append(f"title: '{entity.title}' -> '{payload.title}'")
        entity.title = payload.title
    if payload.reference_no is not None:
        entity.reference_no = payload.reference_no
    if payload.status is not None and payload.status != entity.status:
        changes.append(f"status: '{entity.status}' -> '{payload.status}'")
        entity.status = payload.status
    if payload.parent_id is not None:
        entity.parent_id = payload.parent_id
    if payload.summary is not None:
        entity.summary = payload.summary

    # Update attributes
    if payload.attributes is not None:
        # Delete existing attributes and recreate
        db.query(models.EntityAttribute).filter(
            models.EntityAttribute.entity_id == entity_id
        ).delete()
        for attr in payload.attributes:
            ea = models.EntityAttribute(
                entity_id=entity_id,
                slug=attr.slug,
                value_string=attr.value_string,
                value_text=attr.value_text,
                value_number=attr.value_number,
                value_date=attr.value_date,
                value_datetime=attr.value_datetime,
                value_boolean=attr.value_boolean,
                value_json=attr.value_json,
                value_entity_id=attr.value_entity_id,
                value_user_id=attr.value_user_id,
            )
            db.add(ea)
        changes.append("attributes updated")

    # Record activity
    if changes:
        db.add(models.EntityActivity(
            entity_id=entity_id,
            activity_type="updated",
            description="; ".join(changes),
            performed_by=user.id,
        ))

    db.commit()
    db.refresh(entity)
    return schemas.EntityRead.from_orm_with_type(entity)


@app.delete("/api/entities/{entity_id}", status_code=204,
            tags=["entities"], summary="Delete entity (archives it)",
            dependencies=[Depends(require_roles(ADMIN))])
def delete_entity(entity_id: int, db: Session = Depends(get_db)):
    entity = db.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    # Soft-delete: archive instead of hard delete
    entity.archived_at = __import__('datetime').datetime.utcnow()
    entity.status = "archived"
    db.commit()


# ══════════════════════════════════════════════════════════════════════════
# ENTITY RELATIONSHIPS — Graph
# ══════════════════════════════════════════════════════════════════════════


@app.post("/api/relationships", response_model=schemas.EntityRelationshipRead,
          status_code=201, tags=["relationships"], summary="Create relationship",
          dependencies=[Depends(require_roles(PM, ADMIN))])
def create_relationship(
    payload: schemas.EntityRelationshipCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_active_user),
):
    # Verify both entities exist
    source = db.get(models.Entity, payload.source_id)
    target = db.get(models.Entity, payload.target_id)
    if source is None or target is None:
        raise HTTPException(status_code=404, detail="Source or target entity not found")

    rel = models.EntityRelationship(
        source_id=payload.source_id,
        target_id=payload.target_id,
        relationship_type=payload.relationship_type,
        label=payload.label,
        metadata_json=payload.metadata_json,
        created_by=user.id,
    )
    db.add(rel)

    # Record activity on both entities
    for eid, direction in [(payload.source_id, "source"), (payload.target_id, "target")]:
        db.add(models.EntityActivity(
            entity_id=eid,
            activity_type="relationship_added",
            description=f"Relationship '{payload.relationship_type}' added ({direction})",
            performed_by=user.id,
        ))

    db.commit()
    db.refresh(rel)
    return rel


@app.get("/api/relationships", response_model=List[schemas.EntityRelationshipRead],
         tags=["relationships"], summary="Query relationships",
         dependencies=[Depends(get_current_active_user)])
def list_relationships(
    source_id: int = Query(0, description="Filter by source entity"),
    target_id: int = Query(0, description="Filter by target entity"),
    relationship_type: str = Query("", description="Filter by type"),
    db: Session = Depends(get_db),
):
    query = db.query(models.EntityRelationship).filter(
        models.EntityRelationship.is_active == True
    )
    if source_id:
        query = query.filter(models.EntityRelationship.source_id == source_id)
    if target_id:
        query = query.filter(models.EntityRelationship.target_id == target_id)
    if relationship_type:
        query = query.filter(
            models.EntityRelationship.relationship_type == relationship_type
        )
    return query.order_by(models.EntityRelationship.id.desc()).all()


@app.delete("/api/relationships/{rel_id}", status_code=204,
            tags=["relationships"], summary="Deactivate relationship",
            dependencies=[Depends(require_roles(PM, ADMIN))])
def delete_relationship(rel_id: int, db: Session = Depends(get_db)):
    rel = db.get(models.EntityRelationship, rel_id)
    if rel is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    rel.is_active = False
    db.commit()


# ══════════════════════════════════════════════════════════════════════════
# GRAPH TRAVERSAL
# ══════════════════════════════════════════════════════════════════════════


@app.post("/api/graph/traverse", response_model=schemas.GraphResponse,
          tags=["graph"], summary="Traverse the entity graph",
          dependencies=[Depends(get_current_active_user)])
def traverse_graph(
    query: schemas.GraphQuery,
    db: Session = Depends(get_db),
):
    """Traverse the entity graph starting from a source or target entity.
    
    Returns all connected entities and the relationships between them.
    """
    seen_ids = set()
    nodes = []
    edges = []

    # Start from source or target
    if query.source_id:
        start_ids = [query.source_id]
    elif query.target_id:
        start_ids = [query.target_id]
    else:
        raise HTTPException(status_code=400, detail="Provide source_id or target_id")

    current_ids = set(start_ids)
    for _ in range(query.depth):
        if not current_ids:
            break

        # Find relationships
        rel_query = db.query(models.EntityRelationship).filter(
            models.EntityRelationship.is_active == True
        )
        if query.relationship_types:
            rel_query = rel_query.filter(
                models.EntityRelationship.relationship_type.in_(
                    query.relationship_types
                )
            )

        # Get relationships where current entities are source or target
        rels = rel_query.filter(
            (models.EntityRelationship.source_id.in_(current_ids)) |
            (models.EntityRelationship.target_id.in_(current_ids))
        ).all()

        next_ids = set()
        for rel in rels:
            edges.append(rel)
            if rel.source_id not in seen_ids:
                next_ids.add(rel.source_id)
            if rel.target_id not in seen_ids:
                next_ids.add(rel.target_id)

        seen_ids.update(current_ids)
        current_ids = next_ids - seen_ids

    # Fetch all entity nodes
    if seen_ids:
        entity_map = {
            e.id: e for e in db.query(models.Entity)
            .filter(models.Entity.id.in_(seen_ids))
            .all()
        }
        for eid in seen_ids:
            if eid in entity_map:
                entity_rels = [r for r in edges if r.source_id == eid or r.target_id == eid]
                nodes.append(schemas.GraphNode(
                    entity=schemas.EntityBrief.model_validate(entity_map[eid]),
                    relationships=[schemas.EntityRelationshipRead.model_validate(r) for r in entity_rels],
                ))

    return schemas.GraphResponse(nodes=nodes, edges=[
        schemas.EntityRelationshipRead.model_validate(e) for e in edges
    ])


# ══════════════════════════════════════════════════════════════════════════
# ACTIVITY STREAM
# ══════════════════════════════════════════════════════════════════════════


@app.get("/api/entities/{entity_id}/activities",
         response_model=List[schemas.EntityActivityRead],
         tags=["activities"], summary="Get activity stream for an entity",
         dependencies=[Depends(get_current_active_user)])
def list_activities(
    entity_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.EntityActivity)
        .filter(models.EntityActivity.entity_id == entity_id)
        .order_by(models.EntityActivity.id.desc())
        .limit(limit)
        .all()
    )


# ══════════════════════════════════════════════════════════════════════════
# COMMENTS
# ══════════════════════════════════════════════════════════════════════════


@app.post("/api/comments", response_model=schemas.EntityCommentRead,
          status_code=201, tags=["comments"], summary="Add comment to entity",
          dependencies=[Depends(require_roles(PM, ADMIN))])
def create_comment(
    payload: schemas.EntityCommentCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_active_user),
):
    entity = db.get(models.Entity, payload.entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    comment = models.EntityComment(
        entity_id=payload.entity_id,
        parent_id=payload.parent_id,
        body=payload.body,
        comment_type=payload.comment_type,
        author_id=user.id,
    )
    db.add(comment)

    db.add(models.EntityActivity(
        entity_id=payload.entity_id,
        activity_type="commented",
        description=f"Comment added: {payload.body[:100]}",
        performed_by=user.id,
    ))

    db.commit()
    db.refresh(comment)
    return comment


@app.get("/api/entities/{entity_id}/comments",
         response_model=List[schemas.EntityCommentRead],
         tags=["comments"], summary="List comments on an entity",
         dependencies=[Depends(get_current_active_user)])
def list_comments(entity_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.EntityComment)
        .filter(models.EntityComment.entity_id == entity_id)
        .order_by(models.EntityComment.id.asc())
        .all()
    )


# ══════════════════════════════════════════════════════════════════════════
# FILE ATTACHMENTS
# ══════════════════════════════════════════════════════════════════════════


@app.post("/api/entities/{entity_id}/files", response_model=schemas.EntityFileRead,
          status_code=201, tags=["entity_files"], summary="Attach file to entity",
          dependencies=[Depends(require_roles(PM, ADMIN))])
def attach_file(
    entity_id: int,
    payload: schemas.EntityFileCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_active_user),
):
    entity = db.get(models.Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    fm = db.get(models.FileMetadata, payload.file_metadata_id)
    if fm is None:
        raise HTTPException(status_code=404, detail="File metadata not found")

    ef = models.EntityFile(
        entity_id=entity_id,
        file_metadata_id=payload.file_metadata_id,
        file_category=payload.file_category,
        title=payload.title,
        description=payload.description,
        is_encrypted=payload.is_encrypted,
        uploaded_by=user.id,
    )
    db.add(ef)

    db.add(models.EntityActivity(
        entity_id=entity_id,
        activity_type="file_uploaded",
        description=f"File attached: {fm.original_name} ({payload.file_category})",
        performed_by=user.id,
    ))

    db.commit()
    db.refresh(ef)
    return ef


@app.get("/api/entities/{entity_id}/files",
         response_model=List[schemas.EntityFileRead],
         tags=["entity_files"], summary="List files attached to entity",
         dependencies=[Depends(get_current_active_user)])
def list_entity_files(entity_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.EntityFile)
        .filter(models.EntityFile.entity_id == entity_id)
        .order_by(models.EntityFile.id.desc())
        .all()
    )


# ══════════════════════════════════════════════════════════════════════════
# FILE UPLOAD (standalone — upload then attach via entity_files)
# ══════════════════════════════════════════════════════════════════════════


@app.post("/api/files/upload", response_model=schemas.UploadResponse,
          tags=["files"], summary="Upload a file",
          dependencies=[Depends(get_current_active_user)])
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_active_user),
):
    data = await file.read()
    if len(data) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.max_upload_size_bytes // (1024*1024)} MB.",
        )

    store = get_file_store()
    storage_path, original_name, size_bytes, checksum = store.save(
        data, file.filename or "unnamed", file.content_type or ""
    )

    fm = models.FileMetadata(
        original_name=original_name,
        storage_path=storage_path,
        content_type=file.content_type or "",
        size_bytes=size_bytes,
        checksum_sha256=checksum,
        uploaded_by=user.id,
    )
    db.add(fm)
    db.commit()
    db.refresh(fm)

    return schemas.UploadResponse(
        file_id=fm.id,
        original_name=original_name,
        size_bytes=size_bytes,
        storage_path=storage_path,
        checksum_sha256=checksum,
        upload_url=store.get_url(storage_path),
    )


# ══════════════════════════════════════════════════════════════════════════
# PRE-SIGNED URL UPLOADS (S3 direct upload)
# ══════════════════════════════════════════════════════════════════════════


@app.get("/api/files/presigned", tags=["files"],
         summary="Get a pre-signed URL for direct S3 upload",
         dependencies=[Depends(get_current_active_user)])
def get_presigned_upload_url(
    filename: str = Query(..., description="Original filename"),
    content_type: str = Query("application/octet-stream"),
    expires_in: int = Query(3600, description="URL expiry in seconds"),
):
    """Generate a pre-signed URL for direct upload to S3/MinIO.
    
    Bidders can upload their proposal files directly to S3 without going
    through the API server. Only works with S3 storage backend.
    """
    store = get_file_store()
    if not hasattr(store, "generate_presigned_upload_url"):
        raise HTTPException(
            status_code=400,
            detail="Pre-signed URLs only available with S3 storage backend. "
                   "Set FILE_STORAGE_BACKEND=s3 in your .env.",
        )
    url = store.generate_presigned_upload_url(filename, content_type, expires_in)
    return {"upload_url": url, "expires_in": expires_in, "filename": filename}

@app.get("/api/files/{file_id}", response_model=schemas.FileMetadataRead,
         tags=["files"], summary="Get file metadata",
         dependencies=[Depends(get_current_active_user)])
def get_file_metadata(file_id: int, db: Session = Depends(get_db)):
    fm = db.get(models.FileMetadata, file_id)
    if fm is None or fm.is_deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return fm


@app.get("/api/files/{file_id}/download", tags=["files"],
         summary="Download a file",
         dependencies=[Depends(get_current_active_user)])
def download_file(file_id: int, db: Session = Depends(get_db)):
    fm = db.get(models.FileMetadata, file_id)
    if fm is None or fm.is_deleted:
        raise HTTPException(status_code=404, detail="File not found")

    store = get_file_store()
    data = store.read(fm.storage_path)
    if data is None:
        raise HTTPException(status_code=404, detail="File data not found in storage")

    from fastapi.responses import Response
    return Response(
        content=data,
        media_type=fm.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{fm.original_name}"'},
    )


@app.delete("/api/files/{file_id}", status_code=204, tags=["files"],
            summary="Soft-delete a file",
            dependencies=[Depends(get_current_active_user)])
def delete_file(file_id: int, db: Session = Depends(get_db)):
    fm = db.get(models.FileMetadata, file_id)
    if fm is None:
        raise HTTPException(status_code=404, detail="File not found")
    fm.is_deleted = True
    db.commit()





# ══════════════════════════════════════════════════════════════════════════
# ENCRYPTION — Two-Bid Opening (Entity-based)
# ══════════════════════════════════════════════════════════════════════════


@app.post("/api/bid-submissions/{bid_id}/encrypt", tags=["encryption"],
          summary="Encrypt a financial proposal (two-bid opening)",
          dependencies=[Depends(require_roles(PM, ADMIN))])
def encrypt_bid_api(
    bid_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_active_user),
):
    """Encrypt the financial proposal for a bid submission.
    
    In a two-bid opening system, financial proposals are encrypted at
    submission time and only decrypted after technical evaluation is complete.
    """
    entity = db.get(models.Entity, bid_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    import json
    data = json.dumps(payload.get("financial_data", payload)).encode()
    encrypted = encrypt_financial_proposal(data)
    
    # Store encrypted data as an attribute
    db.query(models.EntityAttribute).filter(
        models.EntityAttribute.entity_id == bid_id,
        models.EntityAttribute.slug == "encrypted_proposal",
    ).delete()
    
    ea = models.EntityAttribute(
        entity_id=bid_id,
        slug="encrypted_proposal",
        value_text=encrypted.decode() if isinstance(encrypted, bytes) else encrypted,
    )
    db.add(ea)
    
    db.add(models.EntityActivity(
        entity_id=bid_id,
        activity_type="financial_proposal_encrypted",
        description="Financial proposal encrypted for two-bid opening",
        performed_by=user.id,
    ))
    
    db.commit()
    return {"encrypted": True, "bid_id": bid_id}


@app.post("/api/bid-submissions/{bid_id}/decrypt", tags=["encryption"],
          summary="Decrypt a financial proposal (authorized only)",
          dependencies=[Depends(require_roles(PM, ADMIN))])
def decrypt_bid_api(
    bid_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_active_user),
):
    """Decrypt the financial proposal for a bid submission.
    
    Only callable after technical evaluation is complete.
    Records an audit trail of who decrypted and when.
    """
    entity = db.get(models.Entity, bid_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    attr = db.query(models.EntityAttribute).filter(
        models.EntityAttribute.entity_id == bid_id,
        models.EntityAttribute.slug == "encrypted_proposal",
    ).first()
    
    if attr is None or not attr.value_text:
        raise HTTPException(status_code=404, detail="No encrypted proposal found")
    
    try:
        decrypted = decrypt_financial_proposal(attr.value_text.encode())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {e}")
    
    import json
    financial_data = json.loads(decrypted.decode())
    
    db.add(models.EntityActivity(
        entity_id=bid_id,
        activity_type="financial_proposal_decrypted",
        description=f"Financial proposal decrypted by {user.email}",
        performed_by=user.id,
    ))
    db.commit()
    
    return {"decrypted": True, "bid_id": bid_id, "financial_data": financial_data}


# ══════════════════════════════════════════════════════════════════════════
# RATE HISTORY — Materialized View
# ══════════════════════════════════════════════════════════════════════════


@app.get("/api/rate-history", tags=["analytics"],
         summary="Get rate comparison data across tenders",
         dependencies=[Depends(get_current_active_user)])
def get_rate_history(
    tender_id: Optional[int] = Query(None, description="Filter by tender"),
    boq_item_slug: str = Query("", description="Filter by BOQ item slug"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get historical rate comparison data across tenders.
    
    Returns rates quoted by bidders for similar items across different tenders,
    enabling rate benchmarking and rationalisation.
    """
    # Find the tender entity type
    tender_type = db.query(models.EntityType).filter(
        models.EntityType.slug == "tender"
    ).first()
    bidder_type = db.query(models.EntityType).filter(
        models.EntityType.slug == "bidder"
    ).first()
    boq_type = db.query(models.EntityType).filter(
        models.EntityType.slug == "boq_item"
    ).first()

    if not all([tender_type, bidder_type, boq_type]):
        return []

    # Get all bidders with their attributes
    query = db.query(models.Entity).filter(
        models.Entity.entity_type_id == bidder_type.id
    )

    if tender_id:
        # Find bidders related to this tender
        rels = db.query(models.EntityRelationship).filter(
            models.EntityRelationship.source_id == tender_id,
            models.EntityRelationship.relationship_type == "has_bidder",
        ).all()
        bidder_ids = [r.target_id for r in rels]
        if bidder_ids:
            query = query.filter(models.Entity.id.in_(bidder_ids))

    bidders = query.order_by(models.Entity.id.desc()).limit(limit).all()

    results = []
    for bidder in bidders:
        attrs = {a.slug: a for a in bidder.attributes}
        bid_amount = attrs.get("bid_amount")
        bidder_name = bidder.title

        # Find the tender this bidder belongs to
        parent_rel = db.query(models.EntityRelationship).filter(
            models.EntityRelationship.target_id == bidder.id,
            models.EntityRelationship.relationship_type == "has_bidder",
        ).first()

        tender_ref = ""
        if parent_rel:
            parent = db.get(models.Entity, parent_rel.source_id)
            if parent:
                tender_ref = parent.reference_no

        results.append({
            "bidder_name": bidder_name,
            "tender_reference": tender_ref,
            "bid_amount": float(bid_amount.value_number) if bid_amount and bid_amount.value_number else 0,
            "technical_score": float(attrs["technical_score"].value_number) if "technical_score" in attrs and attrs["technical_score"].value_number else 0,
            "financial_score": float(attrs["financial_score"].value_number) if "financial_score" in attrs and attrs["financial_score"].value_number else 0,
            "total_score": float(attrs["total_score"].value_number) if "total_score" in attrs and attrs["total_score"].value_number else 0,
            "status": bidder.status,
        })

    return results


# ══════════════════════════════════════════════════════════════════════════
# META
# ══════════════════════════════════════════════════════════════════════════


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/", tags=["meta"])
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}
