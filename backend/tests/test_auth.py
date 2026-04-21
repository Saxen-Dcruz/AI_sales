import uuid
import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/auth"
PASSWORD = "SecurePass1!"


def _email() -> str:
    return f"auth_{uuid.uuid4().hex[:10]}@rdltest.com"


def _register_and_login(client: TestClient) -> dict:
    """Helper: fresh user, returns login response JSON."""
    email = _email()
    client.post(f"{BASE}/register", json={"email": email, "password": PASSWORD})
    resp = client.post(f"{BASE}/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()


# ── Register ──────────────────────────────────────────────────────────────────

def test_register_success(client: TestClient):
    resp = client.post(f"{BASE}/register", json={"email": _email(), "password": PASSWORD})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "hashed_password" not in data


def test_register_duplicate_email(client: TestClient):
    email = _email()
    client.post(f"{BASE}/register", json={"email": email, "password": PASSWORD})
    resp = client.post(f"{BASE}/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 409


def test_register_invalid_email(client: TestClient):
    resp = client.post(f"{BASE}/register", json={"email": "not-an-email", "password": PASSWORD})
    assert resp.status_code == 422


def test_register_missing_password(client: TestClient):
    resp = client.post(f"{BASE}/register", json={"email": _email()})
    assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_success(client: TestClient):
    email = _email()
    client.post(f"{BASE}/register", json={"email": email, "password": PASSWORD})
    resp = client.post(f"{BASE}/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Cookies must be set
    assert "access_token" in resp.cookies
    assert "refresh_token" in resp.cookies


def test_login_wrong_password(client: TestClient):
    email = _email()
    client.post(f"{BASE}/register", json={"email": email, "password": PASSWORD})
    resp = client.post(f"{BASE}/login", json={"email": email, "password": "WrongPass1!"})
    assert resp.status_code == 401


def test_login_nonexistent_user(client: TestClient):
    resp = client.post(f"{BASE}/login", json={"email": _email(), "password": PASSWORD})
    assert resp.status_code == 401


# ── Refresh ───────────────────────────────────────────────────────────────────

def test_refresh_success(client: TestClient):
    tokens = _register_and_login(client)
    resp = client.post(f"{BASE}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.json()


def test_refresh_rotates_token(client: TestClient):
    """After rotation the old refresh token must be rejected."""
    tokens = _register_and_login(client)
    old_refresh = tokens["refresh_token"]
    client.post(f"{BASE}/refresh", json={"refresh_token": old_refresh})
    # Old token is now revoked
    resp = client.post(f"{BASE}/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 401


def test_refresh_with_access_token_rejected(client: TestClient):
    tokens = _register_and_login(client)
    resp = client.post(f"{BASE}/refresh", json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


def test_refresh_invalid_token(client: TestClient):
    resp = client.post(f"{BASE}/refresh", json={"refresh_token": "not.a.token"})
    assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────

def test_logout_success(client: TestClient):
    tokens = _register_and_login(client)
    resp = client.post(f"{BASE}/logout", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 204


def test_logout_revokes_refresh_token(client: TestClient):
    """After logout the refresh token must be rejected."""
    tokens = _register_and_login(client)
    client.post(f"{BASE}/logout", json={"refresh_token": tokens["refresh_token"]})
    resp = client.post(f"{BASE}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_logout_no_token_still_succeeds(client: TestClient):
    """Logout with no token is a no-op — always 204."""
    resp = client.post(f"{BASE}/logout")
    assert resp.status_code == 204


# ── /me ───────────────────────────────────────────────────────────────────────

def test_me_success(client: TestClient, auth_headers: dict):
    resp = client.get(f"{BASE}/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert "hashed_password" not in data


def test_me_no_auth(client: TestClient):
    # Clear accumulated session cookies so no cookie-based auth is present
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/me")
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)


def test_me_invalid_token(client: TestClient):
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        resp = client.get(f"{BASE}/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401
    finally:
        for k, v in saved.items():
            client.cookies.set(k, v)
