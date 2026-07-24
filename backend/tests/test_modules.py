"""Module registry + per-tenant enablement tests.

Uses the `einvoice` module (registered as the registry proof-point) to verify
gating: a disabled module 404s for the tenant, an enabled one reaches its route.
"""
from .conftest import hdr, tok


def test_modules_listed(client):
    adm = tok(client, "admin@constructerp.dev", "admin123")
    mods = client.get("/api/modules", headers=hdr(adm)).json()
    einv = next((m for m in mods if m["name"] == "einvoice"), None)
    assert einv is not None
    assert einv["enabled"] is True and einv["default_enabled"] is True


def test_toggle_is_admin_only(client):
    acct = tok(client, "accounting@constructerp.dev", "acct123")
    r = client.put("/api/modules/einvoice", json={"enabled": False}, headers=hdr(acct))
    assert r.status_code == 403


def test_unknown_module_404(client):
    adm = tok(client, "admin@constructerp.dev", "admin123")
    r = client.put("/api/modules/does-not-exist", json={"enabled": True}, headers=hdr(adm))
    assert r.status_code == 404


def test_per_tenant_gate_disables_and_reenables_module(client):
    adm = tok(client, "admin@constructerp.dev", "admin123")
    tnt = client.post("/api/tenants", json={"name": "Gated Co"}, headers=hdr(adm)).json()["id"]
    client.post("/api/auth/users",
                json={"email": "gated-acc@e.com", "password": "secret1", "full_name": "G",
                      "role": "accounting", "tenant_id": tnt}, headers=hdr(adm))
    acc = tok(client, "gated-acc@e.com", "secret1")

    # Enabled by default → the einvoice route is reached (400: no config yet, NOT 404).
    assert client.get("/api/einvoice/validate-tin/123", headers=hdr(acc)).status_code == 400

    # Admin disables the module for this tenant → the whole module 404s.
    off = client.put("/api/modules/einvoice",
                     json={"enabled": False, "tenant_id": tnt}, headers=hdr(adm))
    assert off.status_code == 200 and off.json()["enabled"] is False
    assert client.get("/api/einvoice/validate-tin/123", headers=hdr(acc)).status_code == 404
    # Config (a different einvoice route) is gated too.
    assert client.get("/api/einvoice/config", headers=hdr(acc)).status_code in (403, 404)

    # The tenant user sees the module as disabled in the listing.
    mods = client.get("/api/modules", headers=hdr(acc)).json()
    assert next(m for m in mods if m["name"] == "einvoice")["enabled"] is False

    # Re-enable → route reachable again.
    on = client.put("/api/modules/einvoice",
                    json={"enabled": True, "tenant_id": tnt}, headers=hdr(adm))
    assert on.status_code == 200 and on.json()["enabled"] is True
    assert client.get("/api/einvoice/validate-tin/123", headers=hdr(acc)).status_code == 400


def test_admin_bypasses_gate(client):
    # Even with the module disabled for a tenant, a platform admin is unaffected.
    adm = tok(client, "admin@constructerp.dev", "admin123")
    tnt = client.post("/api/tenants", json={"name": "AdminBypass Co"}, headers=hdr(adm)).json()["id"]
    client.put("/api/modules/einvoice", json={"enabled": False, "tenant_id": tnt}, headers=hdr(adm))
    # admin (null tenant) still reaches the einvoice route — never gated to 404.
    assert client.get("/api/einvoice/validate-tin/123", headers=hdr(adm)).status_code != 404
