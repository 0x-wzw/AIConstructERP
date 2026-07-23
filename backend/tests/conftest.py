"""Shared pytest fixtures + helpers for the API test suite.

Env is configured here (before the app is imported) so every test module runs
against the same throwaway SQLite database with demo users seeded.
"""
import os
import tempfile

# Point the app at an isolated temp DB *before* importing it.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
# Demo users are OFF by default (public passwords) — the suite opts in
# explicitly, on its throwaway SQLite DB, to exercise the RBAC matrix.
os.environ["SEED_DEMO_USERS"] = "true"

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
