"""Thin MyInvois REST client (OAuth2 + document APIs) built on httpx.

Only the endpoints the ERP needs are wrapped. Base URL and an optional httpx
client are injectable so this can be unit-tested against a mock transport
without touching the network.

Endpoints (MyInvois API v1.0):
  POST /connect/token                              OAuth2 client-credentials
  POST /api/v1.0/documentsubmissions/              submit up to 100 signed docs
  GET  /api/v1.0/documentsubmissions/{submissionUID}   submission + per-doc status
  GET  /api/v1.0/documents/{uuid}/details          validated document + long id
  PUT  /api/v1.0/documents/state/{uuid}/state      cancel (supplier, ≤72h)
  GET  /api/v1.0/taxpayer/validate/{tin}           validate a TIN
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from ..config import settings


class MyInvoisError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None,
                 payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def base_url_for(environment: str) -> str:
    return (settings.myinvois_production_url if environment == "production"
            else settings.myinvois_sandbox_url)


class MyInvoisClient:
    def __init__(self, *, environment: str, client_id: str, client_secret: str,
                 onbehalf_tin: str = "", http: Optional[httpx.Client] = None):
        self.environment = environment
        self.client_id = client_id
        self.client_secret = client_secret
        self.onbehalf_tin = onbehalf_tin
        self._base = base_url_for(environment)
        self._http = http or httpx.Client(
            base_url=self._base, timeout=settings.myinvois_http_timeout_seconds
        )
        self._token: Optional[str] = None

    # ── auth ──────────────────────────────────────────────────────────
    def authenticate(self) -> str:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": settings.myinvois_scope,
        }
        # Intermediaries add the taxpayer scope on the token request.
        if self.onbehalf_tin:
            data["onbehalfof"] = self.onbehalf_tin
        r = self._http.post(settings.myinvois_token_path, data=data)
        if r.status_code != 200:
            raise MyInvoisError("MyInvois authentication failed",
                                status_code=r.status_code, payload=_safe_json(r))
        self._token = r.json().get("access_token")
        if not self._token:
            raise MyInvoisError("MyInvois token response had no access_token")
        return self._token

    def _headers(self) -> Dict[str, str]:
        if self._token is None:
            self.authenticate()
        h = {"Authorization": f"Bearer {self._token}"}
        if self.onbehalf_tin:
            h["onbehalfof"] = self.onbehalf_tin
        return h

    # ── documents ─────────────────────────────────────────────────────
    def submit_documents(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """POST a batch. Each item: {format, document(b64), documentHash, codeNumber}."""
        r = self._http.post(
            "/api/v1.0/documentsubmissions/",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={"documents": documents},
        )
        if r.status_code not in (200, 202):
            raise MyInvoisError("Document submission rejected",
                                status_code=r.status_code, payload=_safe_json(r))
        return r.json()

    def get_submission(self, submission_uid: str) -> Dict[str, Any]:
        r = self._http.get(f"/api/v1.0/documentsubmissions/{submission_uid}",
                            headers=self._headers())
        if r.status_code != 200:
            raise MyInvoisError("Could not fetch submission",
                                status_code=r.status_code, payload=_safe_json(r))
        return r.json()

    def get_document(self, uuid: str) -> Dict[str, Any]:
        r = self._http.get(f"/api/v1.0/documents/{uuid}/details",
                            headers=self._headers())
        if r.status_code != 200:
            raise MyInvoisError("Could not fetch document",
                                status_code=r.status_code, payload=_safe_json(r))
        return r.json()

    def cancel_document(self, uuid: str, reason: str) -> Dict[str, Any]:
        r = self._http.put(
            f"/api/v1.0/documents/state/{uuid}/state",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={"status": "cancelled", "reason": reason},
        )
        if r.status_code != 200:
            raise MyInvoisError("Cancellation failed",
                                status_code=r.status_code, payload=_safe_json(r))
        return r.json()

    def validate_tin(self, tin: str, id_type: str = "BRN", id_value: str = "") -> bool:
        params = {}
        if id_type and id_value:
            params = {"idType": id_type, "idValue": id_value}
        r = self._http.get(f"/api/v1.0/taxpayer/validate/{tin}",
                            headers=self._headers(), params=params)
        return r.status_code == 200

    def close(self) -> None:
        self._http.close()


def _safe_json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except Exception:
        return r.text[:500]
