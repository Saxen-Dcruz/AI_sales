"""
Shared fixtures for the test suite.

All tests run as integration tests against the real PostgreSQL DB inside Docker.
A single test user is created per session and reused across all tests via
`auth_headers`. Test data is created with unique identifiers to avoid conflicts.

Run inside Docker:
    docker compose exec backend bash -c "cd /app && PYTHONPATH=/app pytest tests/ -v"
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.database.core import SessionLocal

AUTH_BASE = "/api/v1/auth"
TEST_PASSWORD = "TestPass123!"


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:10]}@rdltest.com"


@pytest.fixture(scope="session", autouse=True)
def clean_test_products():
    """Delete any leftover test products from previous runs before and after the session."""
    def _purge():
        with SessionLocal() as db:
            db.execute(text("DELETE FROM products WHERE order_code LIKE 'TEST-%'"))
            db.commit()
    _purge()
    yield
    _purge()


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client: TestClient) -> dict:
    """Register a test user once per session and return bearer headers."""
    email = _unique_email()
    client.post(f"{AUTH_BASE}/register", json={"email": email, "password": TEST_PASSWORD})
    resp = client.post(f"{AUTH_BASE}/login", json={"email": email, "password": TEST_PASSWORD})
    assert resp.status_code == 200, f"Test user login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
