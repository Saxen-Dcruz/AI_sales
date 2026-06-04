"""Tests for the user-management router (/api/v1/users)."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database.core import SessionLocal
from app.models.user import User
from app.services.auth_service import hash_password

BASE = "/api/v1/users"
AUTH = "/api/v1/auth"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}@rdltest.com"


@pytest.fixture(autouse=True)
def _clear_session_cookies(client: TestClient):
    """The TestClient is session-scoped and login sets HttpOnly cookies. Those
    cookies take precedence over Bearer headers in get_current_user, so without
    clearing them every fixture login would override every prior test's auth.
    Clear before AND after each test for isolation."""
    client.cookies.clear()
    yield
    client.cookies.clear()


def _login_clean(client: TestClient, email: str, pwd: str) -> str:
    """Login and immediately clear cookies — return only the access token so the
    test must authenticate via the Bearer header it sets explicitly."""
    resp = client.post(f"{AUTH}/login", json={"email": email, "password": pwd})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    client.cookies.clear()
    return token


@pytest.fixture
def admin_headers(client: TestClient) -> dict:
    """Create an ad-hoc super-admin user, log in, return bearer headers + email."""
    email = _unique("usrtest_admin")
    pwd = "AdminPass123!"
    with SessionLocal() as db:
        db.add(User(
            email=email,
            hashed_password=hash_password(pwd),
            is_superuser=True,
            is_active=True,
        ))
        db.commit()
    return {
        "Authorization": f"Bearer {_login_clean(client, email, pwd)}",
        "_email": email,
    }


@pytest.fixture
def regular_headers(client: TestClient) -> dict:
    """Create an ad-hoc non-admin user, log in, return bearer headers."""
    email = _unique("usrtest_reg")
    pwd = "UserPass123!"
    with SessionLocal() as db:
        db.add(User(
            email=email,
            hashed_password=hash_password(pwd),
            is_superuser=False,
            is_active=True,
        ))
        db.commit()
    return {
        "Authorization": f"Bearer {_login_clean(client, email, pwd)}",
        "_email": email,
        "_password": pwd,
    }


# ── GET /users (list, admin-only) ────────────────────────────────────────────

def test_list_users_as_admin_returns_array(client: TestClient, admin_headers):
    resp = client.get(BASE, headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_users_as_regular_user_is_403(client: TestClient, regular_headers):
    h = {k: v for k, v in regular_headers.items() if not k.startswith("_")}
    resp = client.get(BASE, headers=h)
    assert resp.status_code == 403


def test_list_users_no_auth_is_401(client: TestClient):
    resp = client.get(BASE)
    assert resp.status_code == 401


# ── POST /users (create, admin-only) ─────────────────────────────────────────

def test_admin_creates_regular_user(client: TestClient, admin_headers):
    email = _unique("created")
    resp = client.post(
        BASE,
        headers=admin_headers,
        json={"email": email, "password": "Created@123", "is_superuser": False},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == email
    assert body["is_superuser"] is False
    assert body["is_active"] is True

    # Created user can actually log in with that password
    login = client.post(f"{AUTH}/login", json={"email": email, "password": "Created@123"})
    assert login.status_code == 200


def test_admin_creates_super_admin(client: TestClient, admin_headers):
    email = _unique("created_admin")
    resp = client.post(
        BASE,
        headers=admin_headers,
        json={"email": email, "password": "Created@123", "is_superuser": True},
    )
    assert resp.status_code == 201
    assert resp.json()["is_superuser"] is True


def test_create_duplicate_email_is_409(client: TestClient, admin_headers, regular_headers):
    email = regular_headers["_email"]
    resp = client.post(
        BASE,
        headers=admin_headers,
        json={"email": email, "password": "Created@123"},
    )
    assert resp.status_code == 409


def test_create_short_password_is_422(client: TestClient, admin_headers):
    resp = client.post(
        BASE,
        headers=admin_headers,
        json={"email": _unique("short"), "password": "12345"},  # < 6 chars
    )
    assert resp.status_code == 422


def test_create_as_regular_user_is_403(client: TestClient, regular_headers):
    h = {k: v for k, v in regular_headers.items() if not k.startswith("_")}
    resp = client.post(
        BASE,
        headers=h,
        json={"email": _unique("regtry"), "password": "Created@123"},
    )
    assert resp.status_code == 403


# ── PATCH /users/{id} (update, admin-only) ───────────────────────────────────

def test_admin_updates_is_active(client: TestClient, admin_headers, regular_headers):
    # find the regular user id
    users = client.get(BASE, headers=admin_headers).json()
    reg = next(u for u in users if u["email"] == regular_headers["_email"])

    resp = client.patch(
        f"{BASE}/{reg['id']}", headers=admin_headers, json={"is_active": False}
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_admin_resets_user_password(client: TestClient, admin_headers, regular_headers):
    users = client.get(BASE, headers=admin_headers).json()
    reg = next(u for u in users if u["email"] == regular_headers["_email"])

    resp = client.patch(
        f"{BASE}/{reg['id']}", headers=admin_headers, json={"password": "Forced@123"}
    )
    assert resp.status_code == 200

    # User can log in with the new password; the old one no longer works
    new_login = client.post(
        f"{AUTH}/login", json={"email": regular_headers["_email"], "password": "Forced@123"}
    )
    assert new_login.status_code == 200
    old_login = client.post(
        f"{AUTH}/login",
        json={"email": regular_headers["_email"], "password": regular_headers["_password"]},
    )
    assert old_login.status_code == 401


def test_admin_cannot_self_demote(client: TestClient, admin_headers):
    """Last-admin guardrail — must not be able to demote yourself."""
    users = client.get(BASE, headers=admin_headers).json()
    me = next(u for u in users if u["email"] == admin_headers["_email"])

    resp = client.patch(
        f"{BASE}/{me['id']}", headers=admin_headers, json={"is_superuser": False}
    )
    assert resp.status_code == 400


def test_update_unknown_user_is_404(client: TestClient, admin_headers):
    resp = client.patch(
        f"{BASE}/{uuid.uuid4()}", headers=admin_headers, json={"is_active": False}
    )
    assert resp.status_code == 404


def test_update_as_regular_user_is_403(client: TestClient, regular_headers):
    h = {k: v for k, v in regular_headers.items() if not k.startswith("_")}
    resp = client.patch(f"{BASE}/{uuid.uuid4()}", headers=h, json={"is_active": False})
    assert resp.status_code == 403


# ── DELETE /users/{id} (soft-deactivate, admin-only) ─────────────────────────

def test_admin_deactivates_user(client: TestClient, admin_headers, regular_headers):
    users = client.get(BASE, headers=admin_headers).json()
    reg = next(u for u in users if u["email"] == regular_headers["_email"])

    resp = client.delete(f"{BASE}/{reg['id']}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Deactivated user can no longer log in (auth router rejects with 401 or 403
    # depending on whether the user record itself or the active flag fails first).
    login = client.post(
        f"{AUTH}/login",
        json={"email": regular_headers["_email"], "password": regular_headers["_password"]},
    )
    assert login.status_code in (401, 403)


def test_admin_cannot_self_deactivate(client: TestClient, admin_headers):
    users = client.get(BASE, headers=admin_headers).json()
    me = next(u for u in users if u["email"] == admin_headers["_email"])

    resp = client.delete(f"{BASE}/{me['id']}", headers=admin_headers)
    assert resp.status_code == 400


# ── PATCH /users/me/password (self-service) ──────────────────────────────────

def test_user_changes_own_password(client: TestClient, regular_headers):
    h = {k: v for k, v in regular_headers.items() if not k.startswith("_")}
    resp = client.patch(
        f"{BASE}/me/password",
        headers=h,
        json={
            "current_password": regular_headers["_password"],
            "new_password": "Brand@New123",
        },
    )
    assert resp.status_code == 200

    # New password works
    login = client.post(
        f"{AUTH}/login",
        json={"email": regular_headers["_email"], "password": "Brand@New123"},
    )
    assert login.status_code == 200


def test_change_password_wrong_current_is_400(client: TestClient, regular_headers):
    h = {k: v for k, v in regular_headers.items() if not k.startswith("_")}
    resp = client.patch(
        f"{BASE}/me/password",
        headers=h,
        json={"current_password": "TotallyWrong!", "new_password": "Anything@123"},
    )
    assert resp.status_code == 400


def test_change_password_too_short_is_422(client: TestClient, regular_headers):
    h = {k: v for k, v in regular_headers.items() if not k.startswith("_")}
    resp = client.patch(
        f"{BASE}/me/password",
        headers=h,
        json={"current_password": regular_headers["_password"], "new_password": "abc"},
    )
    assert resp.status_code == 422


def test_change_password_no_auth_is_401(client: TestClient):
    resp = client.patch(
        f"{BASE}/me/password",
        json={"current_password": "x", "new_password": "y" * 6},
    )
    assert resp.status_code == 401
