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
    from datetime import datetime

    t = tok(client, "admin@constructerp.dev", "admin123")
    # Admin can write anything, incl. POs
    r = client.post("/api/purchase-orders",
                    json={"supplier": "Acme", "item": "Nails", "amount": 500}, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert r.json()["po_number"].startswith(f"PO-{datetime.now().year}-")


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


def test_frontend_role_aliases_map_to_backend_roles(client):
    """Superadmin->admin, Vendor->project_manager, Supplier->accounting."""
    # Vendor behaves as project_manager: projects yes, budget no.
    vt = tok(client, "vendor@constructerp.dev", "vendor123")
    assert client.get("/api/auth/me", headers=hdr(vt)).json()["role"] == "project_manager"
    assert client.post("/api/projects", json={"name": "Vendor Job"}, headers=hdr(vt)).status_code == 201
    assert client.post("/api/budget", json={"category": "X", "budget": 1}, headers=hdr(vt)).status_code == 403

    # Supplier behaves as accounting: POs yes, projects no.
    st = tok(client, "supplier@constructerp.dev", "supplier123")
    assert client.get("/api/auth/me", headers=hdr(st)).json()["role"] == "accounting"
    assert client.post("/api/purchase-orders",
                       json={"supplier": "S", "item": "I", "amount": 1}, headers=hdr(st)).status_code == 201
    assert client.post("/api/projects", json={"name": "No"}, headers=hdr(st)).status_code == 403

    # Superadmin behaves as admin.
    at = tok(client, "superadmin@constructerp.dev", "super123")
    assert client.get("/api/auth/me", headers=hdr(at)).json()["role"] == "admin"


# ── Multi-tenancy ──────────────────────────────────────────────────────
def test_admin_can_create_tenant_and_assign_user(client):
    at = tok(client, "admin@constructerp.dev", "admin123")

    # Create a tenant
    r = client.post("/api/tenants", json={"name": "Acme Construction"}, headers=hdr(at))
    assert r.status_code == 201, r.text
    tenant_id = r.json()["id"]

    # Create a user assigned to that tenant
    r = client.post("/api/auth/users",
                    json={"email": "acme-pm@example.com", "password": "secret1",
                          "full_name": "Acme PM", "role": "project_manager",
                          "tenant_id": tenant_id},
                    headers=hdr(at))
    assert r.status_code == 201, r.text
    assert r.json()["tenant_id"] == tenant_id

    # List tenants
    tenants = client.get("/api/tenants", headers=hdr(at)).json()
    assert any(t["id"] == tenant_id for t in tenants)


def test_tenant_isolation_on_reads(client):
    at = tok(client, "admin@constructerp.dev", "admin123")

    # Create two tenants
    t1 = client.post("/api/tenants", json={"name": "Tenant A"}, headers=hdr(at)).json()["id"]
    t2 = client.post("/api/tenants", json={"name": "Tenant B"}, headers=hdr(at)).json()["id"]

    # Create a PM in each tenant
    client.post("/api/auth/users",
                json={"email": "pm-a@e.com", "password": "secret1", "full_name": "PM A",
                      "role": "project_manager", "tenant_id": t1}, headers=hdr(at))
    client.post("/api/auth/users",
                json={"email": "pm-b@e.com", "password": "secret1", "full_name": "PM B",
                      "role": "project_manager", "tenant_id": t2}, headers=hdr(at))

    # Each PM creates a project — stamped with their tenant_id
    ta = tok(client, "pm-a@e.com", "secret1")
    tb = tok(client, "pm-b@e.com", "secret1")

    r = client.post("/api/projects", json={"name": "Project A"}, headers=hdr(ta))
    assert r.status_code == 201
    assert r.json()["tenant_id"] == t1

    r = client.post("/api/projects", json={"name": "Project B"}, headers=hdr(tb))
    assert r.status_code == 201
    assert r.json()["tenant_id"] == t2

    # PM A only sees Project A
    a_projects = client.get("/api/projects", headers=hdr(ta)).json()
    assert len(a_projects) == 1
    assert a_projects[0]["name"] == "Project A"

    # PM B only sees Project B
    b_projects = client.get("/api/projects", headers=hdr(tb)).json()
    assert len(b_projects) == 1
    assert b_projects[0]["name"] == "Project B"

    # Admin sees both (unscoped)
    admin_projects = client.get("/api/projects", headers=hdr(at)).json()
    project_names = {p["name"] for p in admin_projects}
    assert "Project A" in project_names
    assert "Project B" in project_names


def test_tenant_isolation_on_single_record(client):
    at = tok(client, "admin@constructerp.dev", "admin123")

    t1 = client.post("/api/tenants", json={"name": "Isolation T1"}, headers=hdr(at)).json()["id"]
    t2 = client.post("/api/tenants", json={"name": "Isolation T2"}, headers=hdr(at)).json()["id"]

    client.post("/api/auth/users",
                json={"email": "iso-a@e.com", "password": "secret1", "full_name": "A",
                      "role": "project_manager", "tenant_id": t1}, headers=hdr(at))
    client.post("/api/auth/users",
                json={"email": "iso-b@e.com", "password": "secret1", "full_name": "B",
                      "role": "project_manager", "tenant_id": t2}, headers=hdr(at))

    ta = tok(client, "iso-a@e.com", "secret1")
    tb = tok(client, "iso-b@e.com", "secret1")

    # PM A creates a project
    r = client.post("/api/projects", json={"name": "Secret A"}, headers=hdr(ta))
    pid_a = r.json()["id"]

    # PM B cannot access PM A's project (404, not 403 — no data leak)
    assert client.get(f"/api/projects/{pid_a}", headers=hdr(tb)).status_code == 404

    # PM B cannot delete PM A's project
    assert client.delete(f"/api/projects/{pid_a}", headers=hdr(tb)).status_code == 404

    # PM B cannot update PM A's project
    assert client.patch(f"/api/projects/{pid_a}", json={"name": "Hacked"},
                        headers=hdr(tb)).status_code == 404


# ── File upload ────────────────────────────────────────────────────────
def test_file_upload_requires_auth(client):
    # No token → 401
    r = client.post("/api/files/upload", files={"file": ("test.txt", b"hello", "text/plain")})
    assert r.status_code == 401


def test_file_upload_and_list(client):
    t = tok(client, "pm@constructerp.dev", "pm123")

    # Upload a file
    r = client.post(
        "/api/files/upload",
        files={"file": ("invoice-001.pdf", b"%PDF-1.4 fake", "application/pdf")},
        headers=hdr(t),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["original_filename"] == "invoice-001.pdf"
    assert data["category"] == "invoice"  # auto-classified from filename
    assert data["size_bytes"] > 0
    file_id = data["id"]

    # List files
    files = client.get("/api/files", headers=hdr(t)).json()
    assert len(files) >= 1
    assert any(f["id"] == file_id for f in files)

    # Get metadata
    meta = client.get(f"/api/files/{file_id}", headers=hdr(t)).json()
    assert meta["original_filename"] == "invoice-001.pdf"

    # Download
    r = client.get(f"/api/files/{file_id}/download", headers=hdr(t))
    assert r.status_code == 200
    assert b"fake" in r.content

    # Delete
    assert client.delete(f"/api/files/{file_id}", headers=hdr(t)).status_code == 204
    assert client.get(f"/api/files/{file_id}", headers=hdr(t)).status_code == 404


def test_file_tenant_isolation(client):
    at = tok(client, "admin@constructerp.dev", "admin123")

    t1 = client.post("/api/tenants", json={"name": "File T1"}, headers=hdr(at)).json()["id"]
    t2 = client.post("/api/tenants", json={"name": "File T2"}, headers=hdr(at)).json()["id"]

    client.post("/api/auth/users",
                json={"email": "file-a@e.com", "password": "secret1", "full_name": "A",
                      "role": "project_manager", "tenant_id": t1}, headers=hdr(at))
    client.post("/api/auth/users",
                json={"email": "file-b@e.com", "password": "secret1", "full_name": "B",
                      "role": "project_manager", "tenant_id": t2}, headers=hdr(at))

    ta = tok(client, "file-a@e.com", "secret1")
    tb = tok(client, "file-b@e.com", "secret1")

    # User A uploads a file
    r = client.post("/api/files/upload",
                    files={"file": ("blueprint.dwg", b"data", "application/octet-stream")},
                    headers=hdr(ta))
    assert r.status_code == 201
    file_id = r.json()["id"]

    # User B cannot see or access User A's file
    assert client.get(f"/api/files/{file_id}", headers=hdr(tb)).status_code == 404
    assert client.get(f"/api/files/{file_id}/download", headers=hdr(tb)).status_code == 404
    assert client.delete(f"/api/files/{file_id}", headers=hdr(tb)).status_code == 404

    # User B's file list doesn't include User A's file
    b_files = client.get("/api/files", headers=hdr(tb)).json()
    assert all(f["id"] != file_id for f in b_files)


def test_file_validation_rejects_bad_extension(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    r = client.post(
        "/api/files/upload",
        files={"file": ("malware.exe", b"MZ", "application/x-msdownload")},
        headers=hdr(t),
    )
    assert r.status_code == 400
    assert "not allowed" in r.json()["detail"]


# ── AI agent ────────────────────────────────────────────────────────────
def test_ai_routes_require_auth(client):
    # No token → 401
    assert client.get("/api/ai/status").status_code == 401
    assert client.post("/api/ai/command", json={"command": "hi"}).status_code == 401
    assert client.post("/api/ai/chat", json={"message": "hi"}).status_code == 401
    assert client.get("/api/ai/briefing").status_code == 401
    assert client.post("/api/ai/analyze").status_code == 401


def test_ai_routes_reject_viewers(client):
    """Viewers and accounting cannot access AI routes — PM/admin only."""
    vt = tok(client, "viewer@constructerp.dev", "viewer123")
    assert client.get("/api/ai/status", headers=hdr(vt)).status_code == 403
    assert client.post("/api/ai/command", json={"command": "hi"},
                       headers=hdr(vt)).status_code == 403

    at = tok(client, "accounting@constructerp.dev", "acct123")
    assert client.get("/api/ai/status", headers=hdr(at)).status_code == 403


def test_ai_routes_accept_pm(client):
    """PM role can access AI routes."""
    pt = tok(client, "pm@constructerp.dev", "pm123")
    assert client.get("/api/ai/status", headers=hdr(pt)).status_code == 200


def test_ai_status_reports_unavailable(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    r = client.get("/api/ai/status", headers=hdr(t)).json()
    # Without openai installed or ollama running, AI should be unavailable
    assert "available" in r
    assert r["available"] is False


def test_ai_endpoints_graceful_when_unconfigured(client):
    t = tok(client, "pm@constructerp.dev", "pm123")

    # Each endpoint should return a graceful message, not crash
    r = client.post("/api/ai/command", json={"command": "show projects"},
                    headers=hdr(t))
    assert r.status_code == 200
    assert "not configured" in r.json()["message"].lower()

    r = client.post("/api/ai/chat", json={"message": "hello"}, headers=hdr(t))
    assert r.status_code == 200
    assert "not configured" in r.json()["response"].lower()

    r = client.get("/api/ai/briefing", headers=hdr(t))
    assert r.status_code == 200
    assert "not configured" in r.json()["briefing"].lower()

    r = client.post("/api/ai/analyze", headers=hdr(t))
    assert r.status_code == 200
    assert "not configured" in r.json()["analysis"].lower()


def test_health_reports_ai_status(client):
    r = client.get("/api/health").json()
    assert "ai_available" in r


# ── Soft delete & audit log ───────────────────────────────────────────
def test_soft_delete_hides_from_list(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    r = client.post("/api/projects", json={"name": "Doomed Project"}, headers=hdr(t))
    assert r.status_code == 201
    pid = r.json()["id"]

    # Delete (soft archive)
    assert client.delete(f"/api/projects/{pid}", headers=hdr(t)).status_code == 204

    # Not in default list
    projects = client.get("/api/projects", headers=hdr(t)).json()
    assert all(p["id"] != pid for p in projects)

    # Visible with include_archived=true
    archived = client.get("/api/projects?include_archived=true", headers=hdr(t)).json()
    assert any(p["id"] == pid and p["is_archived"] for p in archived)


def test_audit_log_records_actions(client):
    t = tok(client, "pm@constructerp.dev", "pm123")

    # Create a project
    r = client.post("/api/projects", json={"name": "Audited Project"}, headers=hdr(t))
    pid = r.json()["id"]

    # Update it
    client.patch(f"/api/projects/{pid}", json={"progress": 50}, headers=hdr(t))

    # Delete (archive) it
    client.delete(f"/api/projects/{pid}", headers=hdr(t))

    # Check audit log
    logs = client.get("/api/audit", headers=hdr(t)).json()
    project_logs = [e for e in logs if e["entity_type"] == "projects" and e["entity_id"] == pid]
    actions = [e["action"] for e in project_logs]
    assert "create" in actions
    assert "update" in actions
    assert "archive" in actions


def test_audit_log_filtered_by_entity_type(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    client.post("/api/projects", json={"name": "X"}, headers=hdr(t))

    # Filter by entity_type
    logs = client.get("/api/audit?entity_type=projects", headers=hdr(t)).json()
    assert all(e["entity_type"] == "projects" for e in logs)


def test_audit_log_requires_auth(client):
    assert client.get("/api/audit").status_code == 401


def test_global_exception_handler(client):
    """Unhandled exceptions return clean JSON, not HTML."""
    # A 422 validation error should return structured JSON
    t = tok(client, "pm@constructerp.dev", "pm123")
    r = client.post("/api/projects", json={"name": "X", "progress": 999}, headers=hdr(t))
    assert r.status_code == 422
    assert "detail" in r.json()


# ── JWT refresh tokens ────────────────────────────────────────────────
def test_login_returns_refresh_token(client):
    r = client.post("/api/auth/token", data={"username": "admin@constructerp.dev",
                                              "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"]  # not empty


def test_refresh_token_works(client):
    # Login
    r = client.post("/api/auth/token", data={"username": "pm@constructerp.dev",
                                              "password": "pm123"})
    refresh = r.json()["refresh_token"]

    # Use refresh token to get new tokens
    r2 = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200, r2.text
    new_data = r2.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    # New access token works
    me = client.get("/api/auth/me", headers=hdr(new_data["access_token"])).json()
    assert me["email"] == "pm@constructerp.dev"


def test_refresh_rejects_access_token(client):
    """An access token cannot be used as a refresh token."""
    t = tok(client, "pm@constructerp.dev", "pm123")
    r = client.post("/api/auth/refresh", json={"refresh_token": t})
    assert r.status_code == 401
    assert "Not a refresh token" in r.json()["detail"]


def test_refresh_rejects_garbage(client):
    r = client.post("/api/auth/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401


def test_refresh_missing_token(client):
    r = client.post("/api/auth/refresh", json={})
    assert r.status_code == 400


def test_password_too_long_rejected(client):
    """Passwords >72 bytes are rejected (bcrypt limit)."""
    at = tok(client, "admin@constructerp.dev", "admin123")
    long_pw = "x" * 73
    r = client.post("/api/auth/users",
                    json={"email": "long@e.com", "password": long_pw,
                          "full_name": "Long", "role": "viewer"},
                    headers=hdr(at))
    assert r.status_code == 400
    assert "72 bytes" in r.json()["detail"]


# ── BRD Module tests ───────────────────────────────────────────────────
def test_vendor_crud(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    # Create
    r = client.post("/api/vendors", json={
        "name": "Acme Construction", "registration_no": "SSM-12345",
        "category": "Building", "email": "info@acme.com", "status": "qualified", "rating": 4
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    vid = r.json()["id"]

    # List
    vendors = client.get("/api/vendors", headers=hdr(t)).json()
    assert any(v["id"] == vid for v in vendors)

    # Search
    results = client.get("/api/vendors?q=Acme", headers=hdr(t)).json()
    assert len(results) >= 1

    # Update
    r = client.patch(f"/api/vendors/{vid}", json={"rating": 5}, headers=hdr(t))
    assert r.json()["rating"] == 5

    # Delete (soft archive)
    assert client.delete(f"/api/vendors/{vid}", headers=hdr(t)).status_code == 204
    assert client.get(f"/api/vendors/{vid}", headers=hdr(t)).status_code == 404


def test_tender_and_boq(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    # Create tender
    r = client.post("/api/tenders", json={
        "title": "Riverside Tower Construction", "status": "published",
        "tender_type": "public"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    # Add BOQ items
    r = client.post("/api/boq-items", json={
        "tender_id": tid, "item_no": "01-001", "description": "Site clearing",
        "unit": "lot", "quantity": 1, "rate": 50000
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    boq_id = r.json()["id"]

    # List BOQ items for tender (via search)
    items = client.get("/api/boq-items", headers=hdr(t)).json()
    assert any(i["id"] == boq_id for i in items)


def test_tender_bid(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    # Create tender
    tender = client.post("/api/tenders", json={"title": "Bridge Project"}, headers=hdr(t)).json()
    # Create vendor
    vendor = client.post("/api/vendors", json={"name": "BidCo"}, headers=hdr(t)).json()

    # Submit bid
    r = client.post("/api/tender-bids", json={
        "tender_id": tender["id"], "vendor_id": vendor["id"],
        "bid_amount": 1500000, "technical_score": 85
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "submitted"


def test_progress_claim_and_payment_cert(client):
    t = tok(client, "accounting@constructerp.dev", "acct123")
    # Create progress claim
    r = client.post("/api/progress-claims", json={
        "claim_no": "PC-001", "period": "Jan 2026",
        "claim_amount": 500000, "certified_amount": 450000
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    claim_id = r.json()["id"]

    # Create payment certificate
    r = client.post("/api/payment-certificates", json={
        "certificate_no": "PC-2026-001", "claim_id": claim_id,
        "gross_amount": 450000, "retention_amount": 22500,
        "net_amount": 427500, "status": "issued"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text


def test_consultant_crud(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    r = client.post("/api/consultants", json={
        "name": "Jane Doe", "firm": "Arch Consultants",
        "discipline": "architect", "email": "jane@arch.com"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "active"


def test_cde_modules(client):
    """Submittals, defects, inspections, site diaries."""
    t = tok(client, "pm@constructerp.dev", "pm123")

    # Submittal
    r = client.post("/api/submittals", json={
        "submittal_no": "SUB-001", "title": "Material spec",
        "submitted_by": "Contractor A"
    }, headers=hdr(t))
    assert r.status_code == 201

    # Defect
    r = client.post("/api/defects", json={
        "defect_no": "DEF-001", "title": "Crack in wall",
        "severity": "major", "location": "Level 3, Unit B"
    }, headers=hdr(t))
    assert r.status_code == 201

    # Inspection
    r = client.post("/api/inspections", json={
        "inspection_no": "INS-001", "title": "Concrete pour check",
        "inspector": "John Engineer"
    }, headers=hdr(t))
    assert r.status_code == 201

    # Site diary
    r = client.post("/api/site-diaries", json={
        "weather": "Sunny", "manpower": 45,
        "work_summary": "Concrete pouring on level 5",
        "prepared_by": "Site Supervisor"
    }, headers=hdr(t))
    assert r.status_code == 201


def test_procurement_pipeline(client):
    """Cost codes → purchase request → RFQ → goods receipt → e-invoice."""
    t = tok(client, "accounting@constructerp.dev", "acct123")

    # Cost code
    r = client.post("/api/cost-codes", json={
        "code": "CC-100", "description": "Site work", "category": "Construction"
    }, headers=hdr(t))
    assert r.status_code == 201

    # Purchase request
    r = client.post("/api/purchase-requests", json={
        "request_no": "PR-001", "title": "Cement purchase",
        "estimated_amount": 50000
    }, headers=hdr(t))
    assert r.status_code == 201
    pr_id = r.json()["id"]

    # RFQ
    r = client.post("/api/rfqs", json={
        "purchase_request_id": pr_id, "rfq_no": "RFQ-001",
        "description": "500 bags cement"
    }, headers=hdr(t))
    assert r.status_code == 201

    # Goods receipt (needs a PO — accounting can create POs)
    po = client.post("/api/purchase-orders", json={
        "supplier": "CementCo", "item": "Cement", "amount": 45000
    }, headers=hdr(t)).json()
    po_id = po["id"]

    r = client.post("/api/goods-receipts", json={
        "purchase_order_id": po_id, "receipt_no": "GR-001",
        "quantity_received": 500, "condition": "good"
    }, headers=hdr(t))
    assert r.status_code == 201

    # E-invoice
    r = client.post("/api/e-invoices", json={
        "purchase_order_id": po_id, "invoice_no": "INV-001",
        "vendor_name": "CementCo", "subtotal": 45000,
        "tax_amount": 2700, "total_amount": 47700
    }, headers=hdr(t))
    assert r.status_code == 201


def test_brd_modules_tenant_isolation(client):
    """BRD modules enforce tenant isolation just like core modules."""
    at = tok(client, "admin@constructerp.dev", "admin123")
    t1 = client.post("/api/tenants", json={"name": "BRD T1"}, headers=hdr(at)).json()["id"]
    t2 = client.post("/api/tenants", json={"name": "BRD T2"}, headers=hdr(at)).json()["id"]

    client.post("/api/auth/users",
                json={"email": "brd-a@e.com", "password": "secret1",
                      "full_name": "A", "role": "project_manager", "tenant_id": t1},
                headers=hdr(at))
    client.post("/api/auth/users",
                json={"email": "brd-b@e.com", "password": "secret1",
                      "full_name": "B", "role": "project_manager", "tenant_id": t2},
                headers=hdr(at))

    ta = tok(client, "brd-a@e.com", "secret1")
    tb = tok(client, "brd-b@e.com", "secret1")

    # User A creates a vendor
    r = client.post("/api/vendors", json={"name": "Vendor A"}, headers=hdr(ta))
    assert r.status_code == 201
    vid = r.json()["id"]

    # User B cannot see User A's vendor
    assert client.get(f"/api/vendors/{vid}", headers=hdr(tb)).status_code == 404
    b_vendors = client.get("/api/vendors", headers=hdr(tb)).json()
    assert all(v["id"] != vid for v in b_vendors)


def test_brd_modules_require_auth(client):
    """All BRD endpoints require authentication."""
    for path in ["/api/vendors", "/api/tenders", "/api/boq-items", "/api/tender-bids",
                 "/api/progress-claims", "/api/payment-certificates", "/api/consultants",
                 "/api/submittals", "/api/defects", "/api/inspections", "/api/site-diaries",
                 "/api/cost-codes", "/api/purchase-requests", "/api/rfqs",
                 "/api/goods-receipts", "/api/e-invoices",
                 "/api/tender-addenda", "/api/reverse-auctions", "/api/final-accounts",
                 "/api/cost-benchmarks", "/api/rate-items",
                 "/api/report-templates", "/api/email-reminders"]:
        assert client.get(path).status_code == 401, f"{path} should require auth"


# ── Module 2: Addendum & Reverse E-Auction ────────────────────────────
def test_tender_addendum(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    tender = client.post("/api/tenders", json={"title": "Addendum Tender"}, headers=hdr(t)).json()

    r = client.post("/api/tender-addenda", json={
        "tender_id": tender["id"], "addendum_no": "ADD-01",
        "title": "Scope clarification", "reason": "clarification"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert r.json()["addendum_no"] == "ADD-01"


def test_reverse_auction_bidding(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    # Create tender, vendor, and auction
    tender = client.post("/api/tenders", json={"title": "Auction Tender"}, headers=hdr(t)).json()
    vendor = client.post("/api/vendors", json={"name": "Auction Vendor"}, headers=hdr(t)).json()

    auction = client.post("/api/reverse-auctions", json={
        "tender_id": tender["id"],
        "reserve_price": 500000,
        "decrement_step": 5000,
        "status": "active"
    }, headers=hdr(t)).json()
    aid = auction["id"]

    # First bid — must not exceed reserve price
    r = client.post(f"/api/reverse-auctions/{aid}/bids", json={
        "auction_id": aid, "vendor_id": vendor["id"], "bid_amount": 480000
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert r.json()["is_leading"] is True

    # Second bid — must be at least 5000 lower than 480000
    r = client.post(f"/api/reverse-auctions/{aid}/bids", json={
        "auction_id": aid, "vendor_id": vendor["id"], "bid_amount": 470000
    }, headers=hdr(t))
    assert r.status_code == 201, r.text

    # Bid too high (only 3000 below leading) — rejected
    r = client.post(f"/api/reverse-auctions/{aid}/bids", json={
        "auction_id": aid, "vendor_id": vendor["id"], "bid_amount": 467000
    }, headers=hdr(t))
    assert r.status_code == 400

    # Check leaderboard is sorted ascending
    leaderboard = client.get(f"/api/reverse-auctions/{aid}/leaderboard", headers=hdr(t)).json()
    amounts = [b["bid_amount"] for b in leaderboard]
    assert amounts == sorted(amounts)
    assert amounts[0] == 470000

    # Check auction leading amount updated
    auction_read = client.get(f"/api/reverse-auctions/{aid}", headers=hdr(t)).json()
    assert float(auction_read["leading_amount"]) == 470000


def test_auction_rejects_bid_when_not_active(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    tender = client.post("/api/tenders", json={"title": "T"}, headers=hdr(t)).json()
    auction = client.post("/api/reverse-auctions", json={
        "tender_id": tender["id"], "status": "scheduled", "reserve_price": 100000
    }, headers=hdr(t)).json()

    r = client.post(f"/api/reverse-auctions/{auction['id']}/bids", json={
        "auction_id": auction["id"], "bid_amount": 90000
    }, headers=hdr(t))
    assert r.status_code == 400
    assert "not active" in r.json()["detail"]


# ── Module 3: Final Account ───────────────────────────────────────────
def test_final_account(client):
    t = tok(client, "accounting@constructerp.dev", "acct123")
    r = client.post("/api/final-accounts", json={
        "account_no": "FA-001", "original_contract_sum": 2000000,
        "variation_orders_total": 150000, "approved_claims_total": 2100000,
        "retention_released": 100000, "final_amount": 2200000,
        "status": "draft"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert float(r.json()["final_amount"]) == 2200000


# ── Module 5: Cost Benchmarking & Rate Analysis ───────────────────────
def test_cost_benchmark_and_rate_item(client):
    t = tok(client, "accounting@constructerp.dev", "acct123")

    # Cost benchmark
    r = client.post("/api/cost-benchmarks", json={
        "category": "Foundation", "unit": "m³", "cost_per_unit": 450,
        "benchmark_type": "actual", "region": "Kuala Lumpur"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text

    # Rate item
    r = client.post("/api/rate-items", json={
        "description": "Concrete Grade 30 (m³)", "unit": "m³",
        "standard_rate": 380, "lowest_rate": 350, "highest_rate": 420,
        "average_rate": 390, "source": "Tender 2026-01"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text


# ── Module 7: Report Templates & Email Reminders ──────────────────────
def test_report_template_and_reminder(client):
    t = tok(client, "pm@constructerp.dev", "pm123")

    # Report template
    r = client.post("/api/report-templates", json={
        "name": "Monthly Budget Report",
        "report_type": "budget",
        "config": '{"filters": {"status": "active"}, "columns": ["category", "budget", "spent"]}',
        "created_by": "pm@constructerp.dev"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text

    # Email reminder
    r = client.post("/api/email-reminders", json={
        "entity_type": "tender", "entity_id": 1,
        "recipient_email": "manager@example.com",
        "subject": "Tender deadline approaching",
        "body": "The tender for Riverside Tower closes in 3 days.",
        "reminder_date": "2026-08-01T09:00:00"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text


# ── AI Chat Persistence ────────────────────────────────────────────────
def test_chat_session_persistence(client):
    t = tok(client, "pm@constructerp.dev", "pm123")

    # Create session
    r = client.post("/api/ai/chat/sessions", json={"title": "Project Discussion"}, headers=hdr(t))
    assert r.status_code == 201, r.text
    sid = r.json()["id"]

    # Send a message (AI not configured → still saves user message + AI fallback)
    r = client.post(f"/api/ai/chat/sessions/{sid}/messages", json={
        "session_id": sid, "role": "user", "content": "What's the budget status?"
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "assistant"
    assert "not configured" in r.json()["content"].lower()

    # List messages
    messages = client.get(f"/api/ai/chat/sessions/{sid}/messages", headers=hdr(t)).json()
    assert len(messages) >= 2  # user + assistant

    # List sessions
    sessions = client.get("/api/ai/chat/sessions", headers=hdr(t)).json()
    assert any(s["id"] == sid for s in sessions)

    # Delete session
    assert client.delete(f"/api/ai/chat/sessions/{sid}", headers=hdr(t)).status_code == 204


def test_chat_session_isolation(client):
    """Chat sessions are private to each user."""
    t1 = tok(client, "pm@constructerp.dev", "pm123")
    t2 = tok(client, "vendor@constructerp.dev", "vendor123")  # also PM role

    # User 1 creates a session
    r = client.post("/api/ai/chat/sessions", json={"title": "Private"}, headers=hdr(t1))
    sid = r.json()["id"]

    # User 2 cannot see user 1's session
    sessions2 = client.get("/api/ai/chat/sessions", headers=hdr(t2)).json()
    assert all(s["id"] != sid for s in sessions2)

    # User 2 cannot access messages
    assert client.get(f"/api/ai/chat/sessions/{sid}/messages",
                      headers=hdr(t2)).status_code == 404


# ── OCR Pipeline ────────────────────────────────────────────────────────
def test_ocr_endpoint(client):
    """OCR endpoint processes uploaded files (or returns error if tesseract not installed)."""
    t = tok(client, "pm@constructerp.dev", "pm123")

    # Upload a text file
    r = client.post("/api/files/upload",
                    files={"file": ("test.txt", b"Hello OCR World", "text/plain")},
                    headers=hdr(t))
    assert r.status_code == 201
    file_id = r.json()["id"]

    # Run OCR
    r = client.post(f"/api/files/{file_id}/ocr", headers=hdr(t))
    assert r.status_code == 200
    # Either OCR succeeds (if tesseract installed) or returns an error message
    data = r.json()
    assert "text" in data
    assert "word_count" in data
    # Text file should be readable as plain text
    assert "Hello" in data["text"] or "OCR Error" in data["text"]


def test_ocr_requires_auth(client):
    assert client.post("/api/files/1/ocr").status_code == 401
    # Viewer should be rejected (needs PM role)
    vt = tok(client, "viewer@constructerp.dev", "viewer123")
    assert client.post("/api/files/1/ocr", headers=hdr(vt)).status_code == 403


# ── SSE Streaming ───────────────────────────────────────────────────────
def test_sse_stream_endpoint(client):
    """SSE streaming endpoint returns text/event-stream (or fallback if AI not configured)."""
    t = tok(client, "pm@constructerp.dev", "pm123")
    r = client.post("/api/ai/chat/stream", json={"message": "hello"}, headers=hdr(t))
    # Should return 200 with text/event-stream
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")


def test_sse_requires_auth(client):
    assert client.post("/api/ai/chat/stream", json={"message": "hi"}).status_code == 401
