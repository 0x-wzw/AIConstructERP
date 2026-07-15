"""Ingestion pipeline — turn an uploaded file into structured system data.

Flow:
  1. Ensure we have text for the document (reuse OCR text, or extract it).
  2. Classify the document (falls back to the file's stored category).
  3. Extract normalized fields with deterministic parsers (no external LLM
     dependency, so it runs in CI and offline).
  4. Persist the fields to FileUpload.extracted_data (JSON) and set ingest_status.
  5. For recognized invoices, create/link an EInvoice domain record so the file
     and the structured entity stay connected (ingested_entity_type/id).

The parsers are intentionally conservative: a field that cannot be found is
simply omitted rather than guessed. This keeps ingestion auditable.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .audit import log_action

# ── Field parsers ─────────────────────────────────────────────────────

# 1,234.56 / 1234.56 / RM 1,234.00 — capture the numeric part.
_MONEY = r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)"

# The value must contain at least one digit (lookahead) so the "Invoice" in a
# "Tax Invoice" title is never mistaken for the invoice number.
_INVOICE_NO = re.compile(
    r"(?:invoice|inv|tax\s+invoice)\s*(?:no\.?|number|#|:)?\s*[:#]?\s*"
    r"((?=[A-Z0-9\-/]*\d)[A-Z0-9][A-Z0-9\-/]{2,})",
    re.IGNORECASE,
)
_VENDOR = re.compile(
    r"(?:vendor|supplier|from|billed\s+by|sold\s+by)\s*[:#]?\s*(.+)",
    re.IGNORECASE,
)
_TOTAL = re.compile(r"(?:grand\s+)?total(?:\s+amount)?(?:\s+due)?\s*[:#]?\s*(?:RM|MYR|\$|USD)?\s*" + _MONEY, re.IGNORECASE)
_SUBTOTAL = re.compile(r"sub[\s\-]?total\s*[:#]?\s*(?:RM|MYR|\$|USD)?\s*" + _MONEY, re.IGNORECASE)
_TAX = re.compile(r"(?:tax|gst|sst|vat)\s*(?:\([0-9.]+%\))?\s*[:#]?\s*(?:RM|MYR|\$|USD)?\s*" + _MONEY, re.IGNORECASE)
_PO_NO = re.compile(r"(?:P\.?O\.?|purchase\s+order)\s*(?:no\.?|number|#|:)?\s*[:#]?\s*((?=[A-Z0-9\-/]*\d)[A-Z0-9][A-Z0-9\-/]{2,})", re.IGNORECASE)
_DATE = re.compile(
    r"(?:date|dated|invoice\s+date)\s*[:#]?\s*"
    r"(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",
    re.IGNORECASE,
)

_DATE_FORMATS = (
    "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y",
    "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%d-%m-%y", "%d/%m/%y",
)


def _to_float(raw: str) -> Optional[float]:
    try:
        return float(raw.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _parse_date(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _first(pattern: re.Pattern, text: str) -> Optional[str]:
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def extract_invoice_fields(text: str) -> dict:
    """Pull invoice fields from document text. Missing fields are omitted."""
    out: dict = {}
    if inv := _first(_INVOICE_NO, text):
        out["invoice_no"] = inv
    if vendor := _first(_VENDOR, text):
        # Keep the vendor line short and single-line.
        out["vendor_name"] = vendor.splitlines()[0][:200]
    if date_raw := _first(_DATE, text):
        out["invoice_date_raw"] = date_raw
        if dt := _parse_date(date_raw):
            out["invoice_date"] = dt.date().isoformat()
    if sub := _first(_SUBTOTAL, text):
        if (v := _to_float(sub)) is not None:
            out["subtotal"] = v
    if tax := _first(_TAX, text):
        if (v := _to_float(tax)) is not None:
            out["tax_amount"] = v
    # Prefer the largest "total" match — grand totals appear after subtotals.
    totals = [v for v in (_to_float(m.group(1)) for m in _TOTAL.finditer(text)) if v is not None]
    if totals:
        out["total_amount"] = max(totals)
    return out


def extract_po_fields(text: str) -> dict:
    out: dict = {}
    if po := _first(_PO_NO, text):
        out["po_number"] = po
    if vendor := _first(_VENDOR, text):
        out["vendor_name"] = vendor.splitlines()[0][:200]
    totals = [v for v in (_to_float(m.group(1)) for m in _TOTAL.finditer(text)) if v is not None]
    if totals:
        out["total_amount"] = max(totals)
    return out


def extract_fields(category: str, text: str) -> dict:
    """Dispatch to the parser for the document category."""
    if category == "invoice":
        return extract_invoice_fields(text)
    if category == "po":
        return extract_po_fields(text)
    # Generic: capture any total we can see so the record isn't empty.
    return extract_po_fields(text)


# ── Text acquisition ──────────────────────────────────────────────────

def _get_text(f: models.FileUpload) -> str:
    """Return document text, running OCR on demand if not already cached."""
    if f.ocr_text:
        return f.ocr_text
    import asyncio
    import os
    import tempfile

    from .ocr_routes import _run_ocr
    from .storage import get_storage_backend

    storage = get_storage_backend()
    content = asyncio.run(storage.read(f.storage_path))
    ext = os.path.splitext(f.original_filename)[1]
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        return _run_ocr(tmp_path)
    finally:
        os.unlink(tmp_path)


# ── Entity linking ────────────────────────────────────────────────────

def _create_einvoice(db: Session, f: models.FileUpload, fields: dict) -> models.EInvoice:
    """Create an EInvoice from extracted fields and link it to the file."""
    invoice_date = None
    if raw := fields.get("invoice_date"):
        invoice_date = _parse_date(raw)
    inv = models.EInvoice(
        tenant_id=f.tenant_id,
        invoice_no=fields.get("invoice_no", ""),
        vendor_name=fields.get("vendor_name", ""),
        invoice_date=invoice_date,
        subtotal=fields.get("subtotal", 0) or 0,
        tax_amount=fields.get("tax_amount", 0) or 0,
        total_amount=fields.get("total_amount", 0) or 0,
        status="draft",
    )
    db.add(inv)
    db.flush()
    return inv


# ── Orchestrator ──────────────────────────────────────────────────────

def ingest_file(db: Session, f: models.FileUpload, user: models.User) -> dict:
    """Run the full ingestion pipeline for one file. Returns a result summary.

    Idempotent-ish: re-running re-extracts and updates the same FileUpload; it
    creates at most one linked entity (skips creation if already linked).
    """
    f.ingest_status = "processing"
    db.flush()

    try:
        text = _get_text(f)
        # Cache OCR text if we just produced it.
        if text and not f.ocr_text and not text.startswith("[OCR Error"):
            f.ocr_text = text
            f.ocr_processed = True

        fields = extract_fields(f.category, text or "")

        entity_type = ""
        entity_id: Optional[int] = None
        if f.category == "invoice" and not f.ingested_entity_id:
            inv = _create_einvoice(db, f, fields)
            entity_type, entity_id = "e_invoices", inv.id

        f.extracted_data = json.dumps(fields)
        f.ingest_status = "ingested"
        f.ingested_at = datetime.utcnow()
        if entity_id:
            f.ingested_entity_type = entity_type
            f.ingested_entity_id = entity_id

        log_action(db, user=user, action="update", entity_type="file_uploads",
                   entity_id=f.id,
                   summary=f"Ingested {f.category or 'file'}: {f.original_filename} "
                           f"({len(fields)} fields"
                           + (f", linked {entity_type}#{entity_id}" if entity_id else "") + ")")
        db.commit()
        db.refresh(f)
        return {
            "file_id": f.id,
            "status": f.ingest_status,
            "category": f.category,
            "extracted_data": fields,
            "linked_entity_type": f.ingested_entity_type or None,
            "linked_entity_id": f.ingested_entity_id,
        }
    except Exception as e:  # noqa: BLE001 — record failure, don't 500 silently
        db.rollback()
        f.ingest_status = "failed"
        db.commit()
        return {"file_id": f.id, "status": "failed", "error": str(e)}
