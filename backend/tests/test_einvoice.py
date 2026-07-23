"""MyInvois e-invoice scaffold tests — exercised against the offline `stub`
backend (EINVOICE_BACKEND defaults to stub, so no network/credentials needed)."""
from .conftest import hdr, tok  # `client` fixture is auto-injected by pytest

_CONFIG = {
    "enabled": True,
    "environment": "sandbox",
    "tin": "C1234567890",
    "registration_no": "201901000005",
    "msic_code": "41001",
    "business_activity": "Construction of buildings",
    "client_id": "test-client-id",
    "client_secret": "super-secret-value",
}


def _enable_config(client, admin_token):
    return client.put("/api/einvoice/config", json=_CONFIG, headers=hdr(admin_token))


# ── config is admin-only and never leaks the secret ───────────────────
def test_einvoice_config_admin_only_and_secret_hidden(client):
    acct = tok(client, "accounting@constructerp.dev", "acct123")
    assert client.get("/api/einvoice/config", headers=hdr(acct)).status_code == 403
    assert client.put("/api/einvoice/config", json=_CONFIG, headers=hdr(acct)).status_code == 403

    adm = tok(client, "admin@constructerp.dev", "admin123")
    r = _enable_config(client, adm)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_client_secret"] is True
    assert "client_secret" not in body                  # write-only, never echoed
    assert body["tin"] == "C1234567890" and body["enabled"] is True

    got = client.get("/api/einvoice/config", headers=hdr(adm)).json()
    assert got["client_id"] == "test-client-id"
    assert "client_secret" not in got


# ── full submit → status → cancel lifecycle (stub backend) ────────────
def test_einvoice_submit_lifecycle(client):
    adm = tok(client, "admin@constructerp.dev", "admin123")
    _enable_config(client, adm)

    acct = tok(client, "accounting@constructerp.dev", "acct123")
    inv = client.post("/api/e-invoices",
                      json={"invoice_no": "INV-1001", "vendor_name": "Steel Co",
                            "subtotal": 100, "tax_amount": 8, "total_amount": 108},
                      headers=hdr(acct))
    assert inv.status_code == 201, inv.text
    iid = inv.json()["id"]

    lines = client.put(f"/api/einvoice/{iid}/lines",
                       json=[{"line_no": 1, "classification_code": "022",
                              "description": "Structural steel", "quantity": 1,
                              "unit_price": 100, "tax_type": "01", "tax_rate": 8,
                              "tax_amount": 8, "subtotal": 100}],
                       headers=hdr(acct))
    assert lines.status_code == 200 and len(lines.json()) == 1

    sub = client.post(f"/api/einvoice/{iid}/submit", headers=hdr(acct))
    assert sub.status_code == 200, sub.text
    body = sub.json()
    assert body["myinvois_status"] == "valid"
    assert body["myinvois_uuid"].startswith("STUB-")
    assert body["validation_link"]

    st = client.get(f"/api/einvoice/{iid}/status", headers=hdr(acct)).json()
    assert st["myinvois_status"] == "valid"
    assert st["myinvois_long_id"]

    # Re-submitting a valid document is refused.
    assert client.post(f"/api/einvoice/{iid}/submit", headers=hdr(acct)).status_code == 409
    # Lines can't be edited after submission.
    assert client.put(f"/api/einvoice/{iid}/lines", json=[], headers=hdr(acct)).status_code == 409

    cancel = client.post(f"/api/einvoice/{iid}/cancel",
                         json={"reason": "issued in error"}, headers=hdr(acct))
    assert cancel.status_code == 200 and cancel.json()["myinvois_status"] == "cancelled"


# ── submit is blocked until MyInvois is configured for the tenant ─────
def test_einvoice_submit_requires_config(client):
    adm = tok(client, "admin@constructerp.dev", "admin123")
    tnt = client.post("/api/tenants", json={"name": "NoEinvoice Co"}, headers=hdr(adm)).json()["id"]
    client.post("/api/auth/users",
                json={"email": "acc-x@e.com", "password": "secret1", "full_name": "X",
                      "role": "accounting", "tenant_id": tnt}, headers=hdr(adm))
    xt = tok(client, "acc-x@e.com", "secret1")

    inv = client.post("/api/e-invoices",
                      json={"invoice_no": "INV-X", "vendor_name": "X"}, headers=hdr(xt))
    iid = inv.json()["id"]
    # This tenant has no MyInvoisConfig → submit is a 400, not a crash.
    assert client.post(f"/api/einvoice/{iid}/submit", headers=hdr(xt)).status_code == 400


# ── a viewer (read-only) cannot submit ────────────────────────────────
def test_einvoice_viewer_cannot_submit(client):
    adm = tok(client, "admin@constructerp.dev", "admin123")
    _enable_config(client, adm)
    acct = tok(client, "accounting@constructerp.dev", "acct123")
    iid = client.post("/api/e-invoices", json={"invoice_no": "INV-RO", "vendor_name": "Y"},
                      headers=hdr(acct)).json()["id"]

    viewer = tok(client, "viewer@constructerp.dev", "viewer123")
    assert client.post(f"/api/einvoice/{iid}/submit", headers=hdr(viewer)).status_code == 403
