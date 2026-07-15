"""File storage abstraction — supports local filesystem and S3/MinIO backends.

Usage:
    store = get_file_store()
    path = store.save("bucket/key.pdf", file_bytes)
    url = store.get_url(path)
    store.delete(path)
"""
from __future__ import annotations

import hashlib
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional

from .config import settings


class FileStore(ABC):
    """Abstract file storage backend."""

    @abstractmethod
    def save(self, data: bytes, filename: str, content_type: str = "") -> tuple[str, str, int, str]:
        """Save a file. Returns (storage_path, original_name, size_bytes, checksum_sha256)."""
        ...

    @abstractmethod
    def save_stream(self, stream: BinaryIO, filename: str, content_type: str = "") -> tuple[str, str, int, str]:
        """Save a file from a stream. Returns (storage_path, original_name, size_bytes, checksum_sha256)."""
        ...

    @abstractmethod
    def get_url(self, storage_path: str) -> str:
        """Get a URL/path for the stored file."""
        ...

    @abstractmethod
    def delete(self, storage_path: str) -> bool:
        """Delete a stored file. Returns True if deleted."""
        ...

    @abstractmethod
    def read(self, storage_path: str) -> Optional[bytes]:
        """Read file contents. Returns None if not found."""
        ...


class LocalFileStore(FileStore):
    """Stores files on the local filesystem under the configured path."""

    def __init__(self) -> None:
        self.base_path = Path(settings.file_storage_local_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _generate_path(self, filename: str) -> tuple[Path, str]:
        """Generate a unique storage path preserving the extension."""
        ext = Path(filename).suffix or ""
        unique_name = f"{uuid.uuid4().hex}{ext}"
        # Organise by date prefix to avoid too many files in one dir
        date_prefix = unique_name[:2]
        dir_path = self.base_path / date_prefix
        dir_path.mkdir(parents=True, exist_ok=True)
        storage_path = f"{date_prefix}/{unique_name}"
        return dir_path / unique_name, storage_path

    def save(self, data: bytes, filename: str, content_type: str = "") -> tuple[str, str, int, str]:
        file_path, storage_path = self._generate_path(filename)
        checksum = hashlib.sha256(data).hexdigest()
        file_path.write_bytes(data)
        return storage_path, filename, len(data), checksum

    def save_stream(self, stream: BinaryIO, filename: str, content_type: str = "") -> tuple[str, str, int, str]:
        data = stream.read()
        return self.save(data, filename, content_type)

    def get_url(self, storage_path: str) -> str:
        full_path = self.base_path / storage_path
        if full_path.exists():
            return str(full_path)
        return ""

    def delete(self, storage_path: str) -> bool:
        full_path = self.base_path / storage_path
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def read(self, storage_path: str) -> Optional[bytes]:
        full_path = self.base_path / storage_path
        if full_path.exists():
            return full_path.read_bytes()
        return None


class S3FileStore(FileStore):
    """Stores files on S3 or MinIO-compatible storage."""

    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        session = boto3.session.Session(
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )
        client_kwargs = {
            "service_name": "s3",
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"},
            ),
        }
        if settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url
        self.client = session.client(**client_kwargs)
        self.bucket = settings.s3_bucket

    def _generate_key(self, filename: str) -> str:
        ext = Path(filename).suffix or ""
        return f"{uuid.uuid4().hex}{ext}"

    def save(self, data: bytes, filename: str, content_type: str = "") -> tuple[str, str, int, str]:
        key = self._generate_key(filename)
        checksum = hashlib.sha256(data).hexdigest()
        extra = {"ContentType": content_type} if content_type else {}
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        return key, filename, len(data), checksum

    def save_stream(self, stream: BinaryIO, filename: str, content_type: str = "") -> tuple[str, str, int, str]:
        data = stream.read()
        return self.save(data, filename, content_type)

    def get_url(self, storage_path: str) -> str:
        return f"s3://{self.bucket}/{storage_path}"

    def delete(self, storage_path: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=storage_path)
            return True
        except Exception:
            return False

    def read(self, storage_path: str) -> Optional[bytes]:
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=storage_path)
            return resp["Body"].read()
        except Exception:
            return None

    def generate_presigned_upload_url(self, filename: str, content_type: str = "", expires_in: int = 3600) -> str:
        """Generate a pre-signed URL for direct upload from the client."""
        key = self._generate_key(filename)
        params = {
            "Bucket": self.bucket,
            "Key": key,
        }
        if content_type:
            params["ContentType"] = content_type
        url = self.client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires_in,
        )
        return url


# Singleton
_store: Optional[FileStore] = None


def get_file_store() -> FileStore:
    """Get the configured file store backend (singleton)."""
    global _store
    if _store is not None:
        return _store
    if settings.file_storage_backend == "s3":
        _store = S3FileStore()
    else:
        _store = LocalFileStore()
    return _store
