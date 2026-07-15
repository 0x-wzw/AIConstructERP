"""S3 / MinIO storage backend (optional — requires boto3).

Configured via the s3_* settings. Works against AWS S3 or any S3-compatible
object store (MinIO, Cloudflare R2, DigitalOcean Spaces) by setting
`S3_ENDPOINT` and, for MinIO-style hosts, `S3_FORCE_PATH_STYLE=true`.
"""
import os
from typing import Optional

from .config import settings
from .storage import FileInfo, StorageBackend, compute_checksum

try:
    import boto3
    from botocore.config import Config
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
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"},
            ),
        )

    async def save(self, content: bytes, path: str, content_type: str = "") -> FileInfo:
        extra = {"ContentType": content_type} if content_type else {}
        checksum = compute_checksum(content)
        # Store the checksum as object metadata so integrity survives round-trips.
        self.client.put_object(
            Bucket=self.bucket, Key=path, Body=content,
            Metadata={"sha256": checksum}, **extra,
        )
        return FileInfo(
            filename=os.path.basename(path),
            content_type=content_type or "application/octet-stream",
            size_bytes=len(content),
            storage_path=path,
            storage_backend="s3",
            checksum_sha256=checksum,
            storage_bucket=self.bucket,
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

    async def generate_presigned_upload_url(
        self, path: str, content_type: str = "", expires_in: int = 0
    ) -> Optional[str]:
        """Pre-signed PUT URL so the browser uploads straight to the bucket."""
        params = {"Bucket": self.bucket, "Key": path}
        if content_type:
            params["ContentType"] = content_type
        try:
            return self.client.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=expires_in or settings.s3_presigned_expiry_seconds,
            )
        except ClientError:
            return None

    async def generate_presigned_download_url(
        self, path: str, expires_in: int = 0
    ) -> Optional[str]:
        """Pre-signed GET URL for direct download without proxying bytes."""
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": path},
                ExpiresIn=expires_in or settings.s3_presigned_expiry_seconds,
            )
        except ClientError:
            return None
