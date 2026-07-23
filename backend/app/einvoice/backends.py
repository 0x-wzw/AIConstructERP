"""Pluggable e-invoice clearance backends.

`get_einvoice_backend()` returns the backend named by settings.einvoice_backend
(mirrors storage.get_storage_backend). Backends take a domain EInvoice + the
tenant's MyInvoisConfig and return a plain result dict; the caller persists.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from ..config import settings

if TYPE_CHECKING:
    from .. import models


class EInvoiceBackend:
    name = "base"

    def submit(self, invoice: "models.EInvoice", config: "models.MyInvoisConfig") -> Dict[str, Any]:
        raise NotImplementedError

    def get_status(self, invoice: "models.EInvoice", config: "models.MyInvoisConfig") -> Dict[str, Any]:
        raise NotImplementedError

    def cancel(self, invoice: "models.EInvoice", config: "models.MyInvoisConfig",
               reason: str) -> Dict[str, Any]:
        raise NotImplementedError

    def validate_tin(self, config: "models.MyInvoisConfig", tin: str,
                     id_type: str = "BRN", id_value: str = "") -> bool:
        raise NotImplementedError


class StubBackend(EInvoiceBackend):
    """Offline echo backend — no network, deterministic. Default for dev/test.

    Simulates instant clearance so the full submit → status → cancel lifecycle
    can be exercised without LHDN credentials or a signing certificate.
    """
    name = "stub"

    def submit(self, invoice, config) -> Dict[str, Any]:
        uuid = f"STUB-{invoice.tenant_id or 0}-{invoice.id}"
        return {
            "myinvois_status": "valid",
            "submission_uid": f"SUBSTUB{invoice.id:018d}",
            "myinvois_uuid": uuid,
            "myinvois_long_id": f"LONG-{uuid}",
            "validation_link": f"https://preprod.myinvois.hasil.gov.my/{uuid}",
            "error": "",
        }

    def get_status(self, invoice, config) -> Dict[str, Any]:
        return {
            "myinvois_status": invoice.myinvois_status or "valid",
            "myinvois_uuid": invoice.myinvois_uuid,
            "myinvois_long_id": invoice.myinvois_long_id or f"LONG-{invoice.myinvois_uuid}",
            "validation_link": invoice.validation_link,
            "error": "",
        }

    def cancel(self, invoice, config, reason) -> Dict[str, Any]:
        return {"myinvois_status": "cancelled", "error": ""}

    def validate_tin(self, config, tin, id_type="BRN", id_value="") -> bool:
        return bool(tin)


class DirectLHDNBackend(EInvoiceBackend):
    """Real MyInvois API backend: map → sign → submit → poll."""
    name = "direct"

    def _client(self, config: "models.MyInvoisConfig"):
        from ..encryption import decrypt_secret
        from .client import MyInvoisClient
        return MyInvoisClient(
            environment=config.environment,
            client_id=config.client_id,
            client_secret=decrypt_secret(config.client_secret_enc),
            onbehalf_tin=config.onbehalf_tin if config.is_intermediary else "",
        )

    def submit(self, invoice, config) -> Dict[str, Any]:
        from .signer import prepare_document
        from .ubl_mapper import build_document

        doc = build_document(invoice, config)
        prepared = prepare_document(doc, config, code_number=invoice.invoice_no or str(invoice.id))
        client = self._client(config)
        try:
            resp = client.submit_documents([{
                "format": prepared.format,
                "document": prepared.document_b64,
                "documentHash": prepared.document_hash,
                "codeNumber": prepared.code_number,
            }])
        finally:
            client.close()

        rejected = resp.get("rejectedDocuments") or []
        if rejected:
            err = rejected[0].get("error") or rejected[0]
            return {"myinvois_status": "invalid", "submission_uid": resp.get("submissionUID", ""),
                    "myinvois_uuid": "", "validation_link": "", "error": str(err)[:2000]}
        accepted = (resp.get("acceptedDocuments") or [{}])[0]
        return {
            "myinvois_status": "submitted",  # becomes valid after polling get_status
            "submission_uid": resp.get("submissionUID", ""),
            "myinvois_uuid": accepted.get("uuid", ""),
            "myinvois_long_id": "",
            "validation_link": "",
            "error": "",
        }

    def get_status(self, invoice, config) -> Dict[str, Any]:
        client = self._client(config)
        try:
            if invoice.submission_uid:
                sub = client.get_submission(invoice.submission_uid)
                docs = sub.get("documentSummary") or []
                summary = next((d for d in docs if d.get("uuid") == invoice.myinvois_uuid),
                               docs[0] if docs else {})
                raw_status = (summary.get("status") or "").lower()
                long_id = summary.get("longId", "")
            else:
                detail = client.get_document(invoice.myinvois_uuid)
                raw_status = (detail.get("status") or "").lower()
                long_id = detail.get("longId", "")
        finally:
            client.close()

        status_map = {"valid": "valid", "invalid": "invalid",
                      "submitted": "submitted", "cancelled": "cancelled"}
        status = status_map.get(raw_status, "submitted")
        link = (f"{('https://myinvois.hasil.gov.my' if config.environment == 'production' else 'https://preprod.myinvois.hasil.gov.my')}"
                f"/{invoice.myinvois_uuid}/share/{long_id}" if long_id else invoice.validation_link)
        return {"myinvois_status": status, "myinvois_uuid": invoice.myinvois_uuid,
                "myinvois_long_id": long_id or invoice.myinvois_long_id,
                "validation_link": link, "error": ""}

    def cancel(self, invoice, config, reason) -> Dict[str, Any]:
        client = self._client(config)
        try:
            client.cancel_document(invoice.myinvois_uuid, reason)
        finally:
            client.close()
        return {"myinvois_status": "cancelled", "error": ""}

    def validate_tin(self, config, tin, id_type="BRN", id_value="") -> bool:
        client = self._client(config)
        try:
            return client.validate_tin(tin, id_type, id_value)
        finally:
            client.close()


def get_einvoice_backend() -> EInvoiceBackend:
    if settings.einvoice_backend.lower() == "direct":
        return DirectLHDNBackend()
    return StubBackend()
