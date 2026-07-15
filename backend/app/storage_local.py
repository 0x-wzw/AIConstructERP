"""Local filesystem storage backend."""
import os
from typing import Optional

from .config import settings
from .storage import FileInfo, StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self):
        self.base_path = os.path.abspath(settings.upload_dir)
        os.makedirs(self.base_path, exist_ok=True)

    def _full_path(self, path: str) -> str:
        return os.path.join(self.base_path, path)

    async def save(self, content: bytes, path: str) -> FileInfo:
        full_path = self._full_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(content)
        return FileInfo(
            filename=os.path.basename(path),
            content_type=self._guess_type(path),
            size_bytes=len(content),
            storage_path=path,
            storage_backend="local",
        )

    async def read(self, path: str) -> bytes:
        with open(self._full_path(path), "rb") as f:
            return f.read()

    async def delete(self, path: str) -> bool:
        full_path = self._full_path(path)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False

    async def exists(self, path: str) -> bool:
        return os.path.exists(self._full_path(path))

    async def get_url(self, path: str) -> str:
        return f"/api/files/download/{path}"

    def _guess_type(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        return {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".csv": "text/csv",
            ".json": "application/json",
            ".txt": "text/plain",
        }.get(ext, "application/octet-stream")