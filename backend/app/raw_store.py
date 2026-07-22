"""Raw landing zone (bronze tier) — where unstructured documents land first.

This module owns the *storage side* of the landing zone. It writes verbatim
bytes into a dedicated `raw/` key prefix so the raw tier is cleanly separated
from curated/processed objects on every backend (local, S3, MinIO, R2) without
needing a second bucket. The landing zone is treated as immutable: the ETL
pipeline reads from it but never mutates or deletes landed objects.

The *manifest side* (the `RawDocument` rows and ETL orchestration) lives in
`raw_routes.py`; the reusable field-extraction logic lives in `ingestion.py`.
Both are reused here rather than duplicated.
"""
import os
import uuid
from datetime import datetime
from typing import Optional

from .config import settings
from .storage import StorageBackend, compute_checksum, get_storage_backend


def raw_storage_path(tenant_id: Optional[int], original_filename: str) -> str:
    """Landing-zone key: raw/{tenant}/yyyy/mm/dd/uuid.ext.

    Day-level partitioning keeps object listings manageable and mirrors the
    common lakehouse `raw/dt=.../` convention.
    """
    now = datetime.utcnow()
    ext = os.path.splitext(original_filename)[1].lower()
    unique = str(uuid.uuid4())[:12]
    tenant_part = str(tenant_id) if tenant_id else "shared"
    prefix = settings.raw_prefix.strip("/")
    return f"{prefix}/{tenant_part}/{now.year}/{now.month:02d}/{now.day:02d}/{unique}{ext}"


def is_raw_path(path: str) -> bool:
    """True if a storage path points inside the landing zone."""
    return path.startswith(settings.raw_prefix.strip("/") + "/")


class LandedObject:
    """Result of writing bytes into the landing zone."""

    def __init__(self, storage_path: str, storage_backend: str,
                 storage_bucket: str, checksum_sha256: str, size_bytes: int):
        self.storage_path = storage_path
        self.storage_backend = storage_backend
        self.storage_bucket = storage_bucket
        self.checksum_sha256 = checksum_sha256
        self.size_bytes = size_bytes


async def land_bytes(content: bytes, path: str, content_type: str = "",
                     storage: Optional[StorageBackend] = None) -> LandedObject:
    """Write raw bytes to the landing zone at `path` and return its manifest."""
    storage = storage or get_storage_backend()
    info = await storage.save(content, path, content_type)
    return LandedObject(
        storage_path=info.storage_path,
        storage_backend=info.storage_backend,
        storage_bucket=info.storage_bucket,
        checksum_sha256=info.checksum_sha256,
        size_bytes=info.size_bytes,
    )


async def verify_landed(path: str, storage: Optional[StorageBackend] = None
                        ) -> Optional[LandedObject]:
    """Read a landed object back and return its true size/checksum, or None if
    it is not present. Used to confirm direct-to-cloud (pre-signed) uploads."""
    storage = storage or get_storage_backend()
    if not await storage.exists(path):
        return None
    content = await storage.read(path)
    return LandedObject(
        storage_path=path,
        storage_backend=settings.storage_backend.lower(),
        storage_bucket=getattr(storage, "bucket", "") or "",
        checksum_sha256=compute_checksum(content),
        size_bytes=len(content),
    )
