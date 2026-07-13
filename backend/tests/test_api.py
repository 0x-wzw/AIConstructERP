"""End-to-end API + auth/RBAC tests for the entity system."""
import os
import tempfile

# Point the app at an isolated temp DB *before* importing it.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app


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


# ── Health ────────────────────────────────────────────────────────────

def test_health_is_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Auth ──────────────────────────────────────────────────────────────

def test_reads_require_auth(client):
    assert client.get("/api/entities").status_code == 401


def test_login_and_me(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    me = client.get("/api/auth/me", headers=hdr(t)).json()
    assert me["email"] == "admin@constructerp.dev"
    assert me["role"] == "admin"


def test_bad_credentials_rejected(client):
    r = client.post("/api/auth/token", data={
        "username": "admin@constructerp.dev", "password": "nope"
    })
    assert r.status_code == 401


# ── Entity Types (metamodel) ───────────────────────────────────────────

def test_list_entity_types(client):
    t = tok(client, "viewer@constructerp.dev", "viewer123")
    r = client.get("/api/entity-types", headers=hdr(t))
    assert r.status_code == 200
    types = r.json()
    slugs = [et["slug"] for et in types]
    assert "project" in slugs
    assert "vendor" in slugs
    assert "tender" in slugs


# ── Entity CRUD ───────────────────────────────────────────────────────

def test_create_entity(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    r = client.post("/api/entities", json={
        "entity_type_slug": "project",
        "title": "Test Project",
        "reference_no": "TST-001",
        "status": "active",
        "attributes": [
            {"slug": "location", "value_string": "Test Location"},
            {"slug": "budget", "value_number": 500000},
        ],
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "Test Project"
    assert data["reference_no"] == "TST-001"
    assert data["entity_type_slug"] == "project"
    # Check attributes
    attrs = {a["slug"]: a for a in data["attributes"]}
    assert attrs["location"]["value_string"] == "Test Location"
    assert attrs["budget"]["value_number"] == 500000
    return data["id"]


def test_list_entities(client):
    t = tok(client, "viewer@constructerp.dev", "viewer123")
    r = client.get("/api/entities?entity_type=project&limit=5", headers=hdr(t))
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_get_entity(client):
    t = tok(client, "viewer@constructerp.dev", "viewer123")
    # Get first project
    r = client.get("/api/entities?entity_type=project&limit=1", headers=hdr(t))
    assert r.status_code == 200
    entities = r.json()
    if entities:
        eid = entities[0]["id"]
        r2 = client.get(f"/api/entities/{eid}", headers=hdr(t))
        assert r2.status_code == 200
        assert r2.json()["id"] == eid


def test_update_entity(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    r = client.get("/api/entities?entity_type=project&limit=1", headers=hdr(t))
    entities = r.json()
    if not entities:
        eid = test_create_entity(client)
    else:
        eid = entities[0]["id"]

    r2 = client.patch(f"/api/entities/{eid}", json={
        "title": "Updated Project",
        "status": "active",
    }, headers=hdr(t))
    assert r2.status_code == 200, r2.text
    assert r2.json()["title"] == "Updated Project"


def test_delete_entity(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    # Create then delete
    r = client.post("/api/entities", json={
        "entity_type_slug": "project",
        "title": "Delete Me",
        "status": "active",
    }, headers=hdr(t))
    eid = r.json()["id"]
    r2 = client.delete(f"/api/entities/{eid}", headers=hdr(t))
    assert r2.status_code == 204
    # Verify archived
    r3 = client.get(f"/api/entities/{eid}", headers=hdr(t))
    assert r3.json()["status"] == "archived"


# ── Relationships (Graph) ─────────────────────────────────────────────

def test_create_relationship(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    # Create two entities
    r1 = client.post("/api/entities", json={
        "entity_type_slug": "project", "title": "Graph Source", "status": "active",
    }, headers=hdr(t))
    src_id = r1.json()["id"]
    r2 = client.post("/api/entities", json={
        "entity_type_slug": "vendor", "title": "Graph Target", "status": "active",
    }, headers=hdr(t))
    tgt_id = r2.json()["id"]

    r3 = client.post("/api/relationships", json={
        "source_id": src_id, "target_id": tgt_id,
        "relationship_type": "manages",
    }, headers=hdr(t))
    assert r3.status_code == 201, r3.text
    assert r3.json()["relationship_type"] == "manages"


def test_traverse_graph(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    r = client.post("/api/graph/traverse", json={
        "source_id": 1, "depth": 2,
    }, headers=hdr(t))
    assert r.status_code == 200


# ── Activities ─────────────────────────────────────────────────────────

def test_activity_stream(client):
    t = tok(client, "viewer@constructerp.dev", "viewer123")
    r = client.get("/api/entities/1/activities?limit=3", headers=hdr(t))
    assert r.status_code == 200


# ── Comments ───────────────────────────────────────────────────────────

def test_create_comment(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    r = client.post("/api/comments", json={
        "entity_id": 1, "body": "Test comment",
    }, headers=hdr(t))
    assert r.status_code == 201, r.text
    assert r.json()["body"] == "Test comment"


# ── File Upload ───────────────────────────────────────────────────────

def test_file_upload(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    r = client.post("/api/files/upload", files={
        "file": ("test.txt", b"Hello, World!", "text/plain"),
    }, params={"entity_id": 1}, headers=hdr(t))
    assert r.status_code == 200, r.text
    assert r.json()["original_name"] == "test.txt"


# ── Chunked Upload ─────────────────────────────────────────────────────

def test_chunked_upload_flow(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    # Init — uses Form data, not JSON
    r = client.post("/api/files/upload/init", data={
        "filename": "large.pdf", "total_size": "100000", "content_type": "application/pdf",
    }, headers=hdr(t))
    assert r.status_code == 200, r.text
    upload_id = r.json()["upload_id"]
    assert upload_id

    # Upload chunk — uses Form + file upload
    r2 = client.post(f"/api/files/upload/{upload_id}/chunk", data={
        "chunk_index": "0",
    }, files={"file": ("chunk0.bin", b"hello", "application/octet-stream")}, headers=hdr(t))
    assert r2.status_code == 200, r2.text

    # Complete
    r3 = client.post(f"/api/files/upload/{upload_id}/complete", headers=hdr(t))
    assert r3.status_code == 200, r3.text
    assert r3.json()["file_id"]


# ── Encryption ────────────────────────────────────────────────────────

def test_encryption_roundtrip(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    # Create a bid submission entity
    r = client.post("/api/entities", json={
        "entity_type_slug": "bidder", "title": "Test Bidder", "status": "submitted",
    }, headers=hdr(t))
    bid_id = r.json()["id"]

    # Encrypt
    r2 = client.post(f"/api/bid-submissions/{bid_id}/encrypt", json={
        "financial_data": {"bid_amount": 1500000, "payment_terms": "30 days"},
    }, headers=hdr(t))
    assert r2.status_code == 200, r2.text
    assert r2.json()["encrypted"]

    # Decrypt
    r3 = client.post(f"/api/bid-submissions/{bid_id}/decrypt", headers=hdr(t))
    assert r3.status_code == 200, r3.text
    assert r3.json()["financial_data"]["bid_amount"] == 1500000


# ── Rate History ──────────────────────────────────────────────────────

def test_rate_history(client):
    t = tok(client, "viewer@constructerp.dev", "viewer123")
    r = client.get("/api/rate-history", headers=hdr(t))
    assert r.status_code == 200


# ── RBAC ───────────────────────────────────────────────────────────────

def test_viewer_cannot_write(client):
    t = tok(client, "viewer@constructerp.dev", "viewer123")
    r = client.post("/api/entities", json={
        "entity_type_slug": "project", "title": "Nope", "status": "active",
    }, headers=hdr(t))
    assert r.status_code == 403


def test_pm_can_write(client):
    t = tok(client, "pm@constructerp.dev", "pm123")
    r = client.post("/api/entities", json={
        "entity_type_slug": "project", "title": "PM Project", "status": "active",
    }, headers=hdr(t))
    assert r.status_code == 201, r.text


def test_accounting_cannot_manage_entities(client):
    t = tok(client, "accounting@constructerp.dev", "acct123")
    r = client.post("/api/entities", json={
        "entity_type_slug": "project", "title": "Acct Project", "status": "active",
    }, headers=hdr(t))
    assert r.status_code == 403


# ── Validation ────────────────────────────────────────────────────────

def test_unknown_entity_type_rejected(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    r = client.post("/api/entities", json={
        "entity_type_slug": "nonexistent_type",
        "title": "Bad Entity",
        "status": "active",
    }, headers=hdr(t))
    assert r.status_code == 404


def test_missing_title_rejected(client):
    t = tok(client, "admin@constructerp.dev", "admin123")
    r = client.post("/api/entities", json={
        "entity_type_slug": "project",
        "title": "",
        "status": "active",
    }, headers=hdr(t))
    assert r.status_code == 422


# ── Pagination ────────────────────────────────────────────────────────

def test_pagination_headers(client):
    t = tok(client, "viewer@constructerp.dev", "viewer123")
    r = client.get("/api/entities?limit=2", headers=hdr(t))
    assert r.status_code == 200
    # Check pagination headers
    assert "X-Total-Count" in r.headers
    assert "X-Page" in r.headers
    assert "X-Per-Page" in r.headers
