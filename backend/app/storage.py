"""Storage backend abstraction — the single canonical file-storage layer.

Supports local filesystem and S3/MinIO-compatible object storage. The backend
is selected by the `STORAGE_BACKEND` setting (local | s3).

Every stored object records its backend, bucket/container, and a SHA-256
checksum so integrity can be verified on read and the same content can be
de-duplicated. S3 additionally supports pre-signed URLs for direct
browser-to-cloud upload and download without proxying bytes through the API.
"""
import hashlib
import os
import uuid
from datetime import datetime
from typing import BinaryIO, Optional


def compute_checksum(content: bytes) -> str:
    """SHA-256 hex digest — the content-addressable identity of a file."""
    return hashlib.sha256(content).hexdigest()


class FileInfo:
    """Lightweight container for storage operation results."""

    def __init__(self, filename: str, content_type: str, size_bytes: int,
                 storage_path: str, storage_backend: str,
                 checksum_sha256: str = "", storage_bucket: str = ""):
        self.filename = filename
        self.content_type = content_type
        self.size_bytes = size_bytes
        self.storage_path = storage_path
        self.storage_backend = storage_backend
        self.checksum_sha256 = checksum_sha256
        self.storage_bucket = storage_bucket


class StorageBackend:
    """Abstract base — all methods are async.

    `bucket` names the specific cloud container (S3 bucket / MinIO bucket) or is
    empty for the local backend.
    """

    bucket: str = ""

    async def save(self, content: bytes, path: str, content_type: str = "") -> FileInfo:
        raise NotImplementedError

    async def save_stream(self, stream: BinaryIO, path: str,
                          content_type: str = "") -> FileInfo:
        """Save from a file-like object (used for large/assembled uploads)."""
        return await self.save(stream.read(), path, content_type)

    async def read(self, path: str) -> bytes:
        raise NotImplementedError

    async def delete(self, path: str) -> bool:
        raise NotImplementedError

    async def exists(self, path: str) -> bool:
        raise NotImplementedError

    async def get_url(self, path: str) -> str:
        raise NotImplementedError

    async def generate_presigned_upload_url(
        self, path: str, content_type: str = "", expires_in: int = 3600
    ) -> Optional[str]:
        """Return a pre-signed PUT URL for direct-to-cloud upload, or None if
        the backend does not support it (e.g. local filesystem)."""
        return None


def get_storage_backend() -> StorageBackend:
    from .config import settings

    backend = settings.storage_backend.lower()
    if backend == "s3":
        from .storage_s3 import S3Storage
        return S3Storage()
    from .storage_local import LocalStorage
    return LocalStorage()


def generate_storage_path(tenant_id: Optional[int], original_filename: str) -> str:
    """Generate a unique storage path: tenant_id/yyyy/mm/uuid.ext"""
    now = datetime.utcnow()
    ext = os.path.splitext(original_filename)[1].lower()
    unique = str(uuid.uuid4())[:12]
    tenant_part = str(tenant_id) if tenant_id else "shared"
    return f"{tenant_part}/{now.year}/{now.month:02d}/{unique}{ext}"


def guess_file_category(filename: str, content_type: str = "") -> str:
    """Auto-classify uploaded files based on name and type."""
    name = filename.lower()
    if any(w in name for w in ["invoice", "inv-", "bill"]):
        return "invoice"
    if any(w in name for w in ["po-", "purchase", "order"]):
        return "po"
    if any(w in name for w in ["blueprint", "drawing", "plan", "dwg"]):
        return "blueprint"
    if any(w in name for w in ["permit", "license", "approval"]):
        return "permit"
    if any(w in name for w in ["report", "rpt"]):
        return "report"
    if any(w in name for w in ["photo", "img", "image", "site"]):
        return "photo"
    if content_type and "image" in content_type:
        return "photo"
    if content_type == "application/pdf":
        return "document"
    return "other"


ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif",
    ".doc", ".docx", ".xls", ".xlsx", ".csv",
    ".json", ".txt", ".zip",
    ".dwg", ".dxf",  # CAD drawings
    ".rvt",  # Revit
}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png", "image/jpeg", "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv", "text/plain", "application/json",
    "application/zip",
}


def validate_file(filename: str, content_type: str, size_bytes: int) -> Optional[str]:
    """Validate file. Returns error message or None if valid."""
    from .config import settings

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"File extension '{ext}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        return f"File too large. Maximum size is {settings.max_upload_size_mb}MB"
    return None