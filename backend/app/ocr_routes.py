"""OCR endpoint — extracts text from uploaded files using tesseract.

Requires pytesseract + Pillow for images, pdf2image + poppler for PDFs.
When the OCR engine is not installed, the endpoint returns a helpful
message instead of crashing.
"""
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import models
from .audit import log_action
from .database import get_db
from .models import User
from .security import get_current_active_user, require_roles
from .storage import get_storage_backend

logger = logging.getLogger("constructerp.ocr")

router = APIRouter(prefix="/files", tags=["ocr"])

storage = get_storage_backend()


def _run_ocr(file_path: str, lang: str = "eng") -> str:
    """Run OCR on an image/PDF and return extracted text."""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(file_path, dpi=300)
            text = "\n".join(
                pytesseract.image_to_string(img, lang=lang) for img in images
            )
            return text.strip()
        elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
            from PIL import Image
            import pytesseract

            text = pytesseract.image_to_string(
                Image.open(file_path), lang=lang
            )
            return text.strip()
        else:
            # Try reading as plain text.
            with open(file_path, "r", errors="ignore") as f:
                return f.read()[:10000]
    except ImportError as e:
        return f"[OCR Error: {e}. Install pytesseract and system tesseract.]"
    except Exception as e:
        return f"[OCR Error: {e}]"


@router.post("/{file_id}/ocr", summary="Run OCR on an uploaded file",
             dependencies=[Depends(require_roles("project_manager"))])
def ocr_file(file_id: int, db: Session = Depends(get_db),
             user: User = Depends(get_current_active_user)):
    """Run OCR on an uploaded file and store the extracted text."""
    f = db.get(models.FileUpload, file_id)
    if f is None:
        raise HTTPException(status_code=404, detail="File not found")
    if user.tenant_id is not None and f.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="File not found")
    if f.is_archived:
        raise HTTPException(status_code=404, detail="File not found")

    if f.ocr_processed and f.ocr_text:
        return {
            "text": f.ocr_text[:2000],
            "classification": f.category,
            "cached": True,
            "word_count": len(f.ocr_text.split()),
        }

    # Download file to temp location for OCR.
    import asyncio

    content = asyncio.run(storage.read(f.storage_path))
    ext = os.path.splitext(f.original_filename)[1]
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        text = _run_ocr(tmp_path)
        f.ocr_text = text
        f.ocr_processed = True
        log_action(db, user=user, action="update", entity_type="file_uploads",
                   entity_id=f.id, summary=f"OCR processed: {f.original_filename}")
        db.commit()
        return {
            "text": text[:2000],
            "classification": f.category,
            "cached": False,
            "word_count": len(text.split()),
        }
    finally:
        os.unlink(tmp_path)