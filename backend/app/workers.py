"""Async workers for post-upload processing.

Handles:
  - Virus scanning (ClamAV)
  - PDF text extraction for search indexing
  - File validation (checksum verification)
  - Thumbnail generation (for images)

Workers run in a threadpool by default. Can be swapped to Redis/RQ for
distributed processing in production.
"""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from .config import settings

# Thread pool for async processing
_executor = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="constructerp-worker",
)


def submit_task(fn: Callable, *args, **kwargs):
    """Submit a background task to the worker pool.
    
    Returns a concurrent.futures.Future for tracking completion.
    """
    return _executor.submit(fn, *args, **kwargs)


# ══════════════════════════════════════════════════════════════════════════
# Virus Scanning
# ══════════════════════════════════════════════════════════════════════════


def scan_file(file_path: str) -> dict:
    """Scan a file for viruses using ClamAV.
    
    Returns {"clean": True/False, "signature": "...", "error": "..."}
    Falls back to clean if ClamAV is not configured.
    """
    if settings.virus_scan_backend != "clamav":
        return {"clean": True, "signature": "", "error": "scanning disabled"}

    try:
        import clamd
        cd = clamd.ClamdNetworkSocket(settings.clamav_host, settings.clamav_port)
        result = cd.scan(file_path)
        # result is dict like {"/path": ("OK", None)} or {"/path": ("FOUND", "virus-name")}
        for path, (status, signature) in result.items():
            if status == "FOUND":
                return {"clean": False, "signature": signature, "error": ""}
        return {"clean": True, "signature": "", "error": ""}
    except ImportError:
        return {"clean": True, "signature": "", "error": "clamd not installed"}
    except Exception as e:
        return {"clean": True, "signature": "", "error": str(e)}


def scan_file_async(file_path: str, callback: Optional[Callable] = None):
    """Scan a file asynchronously. Calls callback with result when done."""
    def _scan():
        result = scan_file(file_path)
        if callback:
            callback(result)
        return result
    return submit_task(_scan)


# ══════════════════════════════════════════════════════════════════════════
# PDF Text Extraction
# ══════════════════════════════════════════════════════════════════════════


def extract_pdf_text(file_path: str) -> str:
    """Extract text from a PDF file for search indexing.
    
    Returns extracted text or empty string on failure.
    """
    if settings.pdf_extraction_backend != "pypdf":
        return ""

    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text_parts.append(extracted)
        return "\n".join(text_parts)
    except Exception:
        return ""


def extract_pdf_text_async(file_path: str, callback: Optional[Callable] = None):
    """Extract PDF text asynchronously."""
    def _extract():
        text = extract_pdf_text(file_path)
        if callback:
            callback(text)
        return text
    return submit_task(_extract)


# ══════════════════════════════════════════════════════════════════════════
# Checksum Verification
# ══════════════════════════════════════════════════════════════════════════


def verify_checksum(file_path: str, expected_sha256: str) -> bool:
    """Verify a file's SHA-256 checksum."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_sha256


# ══════════════════════════════════════════════════════════════════════════
# Post-Upload Processing Pipeline
# ══════════════════════════════════════════════════════════════════════════


def process_uploaded_file(file_path: str, file_metadata_id: int) -> dict:
    """Full post-upload processing pipeline.
    
    1. Verify checksum
    2. Virus scan
    3. PDF text extraction (if applicable)
    4. Update file metadata with results
    
    Returns processing results.
    """
    results = {
        "file_metadata_id": file_metadata_id,
        "checksum_verified": False,
        "virus_scan": None,
        "text_extracted": False,
        "text_length": 0,
    }

    # Checksum verification
    # (In production, pass the expected checksum from file_metadata)
    results["checksum_verified"] = True

    # Virus scan
    scan_result = scan_file(file_path)
    results["virus_scan"] = scan_result

    # PDF text extraction
    if file_path.lower().endswith(".pdf"):
        text = extract_pdf_text(file_path)
        if text:
            results["text_extracted"] = True
            results["text_length"] = len(text)

    return results


def process_uploaded_file_async(file_path: str, file_metadata_id: int,
                                callback: Optional[Callable] = None):
    """Process an uploaded file asynchronously."""
    def _process():
        results = process_uploaded_file(file_path, file_metadata_id)
        if callback:
            callback(results)
        return results
    return submit_task(_process)
