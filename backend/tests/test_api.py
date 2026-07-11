"""End-to-end API + auth/RBAC tests against a throwaway SQLite database."""
import os
import tempfile

# Point the app at an isolated temp DB *before* importing it.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def tok(client, email, password):
    r = client.post("/api/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def hdr(t):
    return {"Authorization": f"Bearer {t}"}


# ── Public / auth basics ──────────────────────────────────────────────
def test_health_is_public(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_reads_require_auth(client):
    assert client.get("/api/projects").status_code == 401


def test_login_and_me(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    me = client.get("/api/auth/me", headers=hdr(t)).json()
    assert me["email"] == "admin@constructerp.dev"
    assert me["role"] == "admin"


def test_bad_credentials_rejected(client):
    r = client.post("/api/auth/token", data={"username": "admin@constructerp.dev", "password": "nope"})
    assert r.status_code == 401


# ── Seed data (authenticated) ─────────────────────────────────────────
def test_seeded_reads(client):
    t = tok(client, "viewer@constructerp.dev", "viewer123")
    assert len(client.get("/api/projects", headers=hdr(t)).json()) >= 3
    assert len(client.get("/api/budget", headers=hdr(t)).json()) == 5
    assert set(client.get("/api/state", headers=hdr(t)).json()["resources"]) == {
        "labor", "equipment", "materials"
    }


# ── RBAC matrix ───────────────────────────────────────────────────────
def test_viewer_cannot_write(client):
    t = tok(client, "viewer@constructerp.dev", "viewer123")
    r = client.post("/api/projects", json={"name": "Nope"}, headers=hdr(t))
    assert r.status_code == 403


def test_pm_can_manage_projects_but_not_budget(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    # PM creates a project → allowed
    r = client.post("/api/projects", json={"name": "PM Tower", "budget": 100000}, headers=hdr(t))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert client.patch(f"/api/projects/{pid}", json={"progress": 40}, headers=hdr(t)).status_code == 200
    assert client.delete(f"/api/projects/{pid}", headers=hdr(t)).status_code == 204
    # PM cannot touch budget
    assert client.post("/api/budget", json={"category": "X", "budget": 1}, headers=hdr(t)).status_code == 403


def test_accounting_can_manage_budget_but_not_projects(client):
    t = tok(client, "accounting@constructerp.dev", "acct123")
    r = client.post("/api/budget", json={"category": "Permits", "budget": 50000}, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert client.post("/api/projects", json={"name": "X"}, headers=hdr(t)).status_code == 403


def test_admin_override_and_po_autonumber(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    # Admin can write anything, incl. POs
    r = client.post("/api/purchase-orders",
                    json={"supplier": "Acme", "item": "Nails", "amount": 500}, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert r.json()["po_number"].startswith("PO-2024-")


# ── Self-signup + admin user management ───────────────────────────────
def test_public_register_is_viewer_and_admin_can_promote(client):
    r = client.post("/api/auth/register",
                    json={"email": "new@example.com", "password": "secret1", "full_name": "New User"})
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "viewer"

    # Duplicate email rejected
    assert client.post("/api/auth/register",
                       json={"email": "new@example.com", "password": "secret1"}).status_code == 409

    # New viewer cannot list users
    vt = tok(client, "new@example.com", "secret1")
    assert client.get("/api/auth/users", headers=hdr(vt)).status_code == 403

    # Admin lists + promotes
    at = tok(client, "admin@constructerp.dev", "admin123")
    users = client.get("/api/auth/users", headers=hdr(at)).json()
    uid = next(u["id"] for u in users if u["email"] == "new@example.com")
    r = client.patch(f"/api/auth/users/{uid}", json={"role": "project_manager"}, headers=hdr(at))
    assert r.json()["role"] == "project_manager"


def test_validation_still_enforced(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    assert client.post("/api/projects", json={"name": ""}, headers=hdr(t)).status_code == 422
    assert client.post("/api/projects", json={"name": "X", "progress": 999}, headers=hdr(t)).status_code == 422
