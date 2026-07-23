"""Document preparation + digital signing for MyInvois submission.

MyInvois' API channel requires each document to be digitally SIGNED with a
certificate issued by a Malaysian CA (e.g. MSC Trustgate, POS Digicert). The
signature is an enveloped UBL `ext:UBLExtensions` XAdES / JSON-signature block
carrying the document digest, signed-properties digest, signature value and
certificate chain.

This scaffold implements everything EXCEPT the real cryptographic signature:
minification, SHA-256 hashing, and base64 encoding are done for real, while the
signature block is a clearly-marked placeholder. A hard guard prevents the
unsigned document from ever being sent to the PRODUCTION environment.

To finish: load the tenant's PKCS#12/PEM cert (resolved from `config.cert_ref`),
build the XAdES signature per
https://sdk.myinvois.hasil.gov.my/signature-creation/ and inject it before
hashing.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import TYPE_CHECKING, Any, Dict

from ..config import settings

if TYPE_CHECKING:
    from .. import models


class SigningError(RuntimeError):
    pass


class PreparedDocument:
    """The submission-ready form of one e-invoice."""

    def __init__(self, *, format: str, document_b64: str,
                 document_hash: str, code_number: str, signed: bool):
        self.format = format
        self.document_b64 = document_b64
        self.document_hash = document_hash
        self.code_number = code_number
        self.signed = signed


def _minify(doc: Dict[str, Any]) -> bytes:
    """MyInvois requires minified content; separators avoid stray whitespace."""
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _apply_signature(doc: Dict[str, Any], config: "models.MyInvoisConfig") -> bool:
    """Inject the XAdES signature block. Returns True if a real signature was
    applied, False if the document is unsigned (dev only).

    TODO: implement real signing from config.cert_ref. Until then this is a
    no-op placeholder.
    """
    if config.cert_ref:
        # A cert is configured but real signing is not yet implemented.
        raise SigningError(
            "cert_ref is set but the XAdES signer is not implemented yet — "
            "wire signer._apply_signature() before enabling production."
        )
    return False


def prepare_document(
    doc: Dict[str, Any],
    config: "models.MyInvoisConfig",
    code_number: str,
) -> PreparedDocument:
    """Sign (if possible), minify, hash and base64-encode a UBL JSON document."""
    signed = _apply_signature(doc, config)

    if not signed and config.environment == "production" \
            and not settings.myinvois_allow_unsigned_production:
        raise SigningError(
            "Refusing to submit an UNSIGNED document to MyInvois production. "
            "Configure a signing certificate (cert_ref) or, for testing only, "
            "set MYINVOIS_ALLOW_UNSIGNED_PRODUCTION=true."
        )

    raw = _minify(doc)
    return PreparedDocument(
        format="JSON",
        document_b64=base64.b64encode(raw).decode("ascii"),
        document_hash=hashlib.sha256(raw).hexdigest(),
        code_number=code_number,
        signed=signed,
    )
