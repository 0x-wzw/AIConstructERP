"""S3 / MinIO storage backend (optional — requires boto3)."""
import os
from typing import Optional

from .config import settings
from .storage import FileInfo, StorageBackend

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False


class S3Storage(StorageBackend):
    def __init__(self):
        if not HAS_BOTO:
            raise ImportError("boto3 is required for S3 storage: pip install boto3")
        if not settings.s3_bucket:
            raise ValueError("S3_BUCKET setting is required when STORAGE_BACKEND=s3")
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.s3_key or None,
            aws_secret_access_key=settings.s3_secret or None,
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint or None,
        )

    async def save(self, content: bytes, path: str) -> FileInfo:
        self.client.put_object(Bucket=self.bucket, Key=path, Body=content)
        return FileInfo(
            filename=os.path.basename(path),
            content_type="application/octet-stream",
            size_bytes=len(content),
            storage_path=path,
            storage_backend="s3",
        )

    async def read(self, path: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=path)
        return resp["Body"].read()

    async def delete(self, path: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=path)
            return True
        except ClientError:
            return False

    async def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=path)
            return True
        except ClientError:
            return False

    async def get_url(self, path: str) -> str:
        if settings.s3_endpoint:
            return f"{settings.s3_endpoint}/{self.bucket}/{path}"
        return f"https://{self.bucket}.s3.{settings.s3_region}.amazonaws.com/{path}"