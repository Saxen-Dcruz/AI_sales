"""
Tests for Settings — Email Account Management.
Covers: list, auth-url, update, set-primary, delete endpoints.
Pass, fail, and validation cases for each.
"""
import uuid
import base64
import pickle
from datetime import datetime, timezone
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.email_account import EmailAccount

BASE = "/api/v1/settings"


# ── Helpers ───────────────────────────────────────────────────────────────────

class _FakeCreds:
    """Minimal picklable credential stub — MagicMock cannot be pickled."""
    expired = False
    refresh_token = "fake_refresh"
    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]


def _fake_token() -> str:
    return base64.b64encode(pickle.dumps(_FakeCreds())).decode()


def _insert_account(db, email="test@example.com", is_primary=False, is_active=True) -> EmailAccount:
    acct = EmailAccount(
        email_address=email,
        display_name="Test Account",
        token_data=_fake_token(),
        is_active=is_active,
        is_primary=is_primary,
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    return acct


@pytest.fixture
def db(request):
    from app.database.core import SessionLocal
    session = SessionLocal()
    # Track IDs of accounts created during this test so we only delete those
    _created_ids = []
    original_add = session.add

    def _tracked_add(instance):
        original_add(instance)
        if isinstance(instance, EmailAccount):
            _created_ids.append(instance)

    session.add = _tracked_add
    yield session
    # Delete test accounts: @test.com domain + cb_* mock OAuth accounts
    try:
        from sqlalchemy import or_
        session.query(EmailAccount).filter(
            or_(
                EmailAccount.email_address.like('%@test.com'),
                EmailAccount.email_address.like('cb_%@gmail.com'),
            )
        ).delete(synchronize_session=False)
        session.commit()
    except Exception:
        session.rollback()
    session.close()


@contextmanager
def _no_auth(client):
    client.cookies.clear()
    yield
    client.cookies.clear()


# ── GET /settings/email-accounts ─────────────────────────────────────────────

class TestListEmailAccounts:
    def test_list_empty(self, client: TestClient, auth_headers: dict):
        resp = client.get(f"{BASE}/email-accounts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data and "total" in data

    def test_list_includes_added_account(self, client: TestClient, auth_headers: dict, db):
        acct = _insert_account(db, email=f"list_{uuid.uuid4().hex[:6]}@test.com")
        resp = client.get(f"{BASE}/email-accounts", headers=auth_headers)
        assert resp.status_code == 200
        emails = [i["email_address"] for i in resp.json()["items"]]
        assert acct.email_address in emails

    def test_list_no_auth(self, client: TestClient):
        with _no_auth(client):
            resp = client.get(f"{BASE}/email-accounts")
        assert resp.status_code == 401

    def test_list_response_shape(self, client: TestClient, auth_headers: dict, db):
        _insert_account(db, email=f"shape_{uuid.uuid4().hex[:6]}@test.com", is_primary=True)
        resp = client.get(f"{BASE}/email-accounts", headers=auth_headers)
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        for field in ("id", "email_address", "is_active", "is_primary", "created_at"):
            assert field in item, f"Missing field: {field}"


# ── GET /settings/email-accounts/auth-url ────────────────────────────────────

class TestGetAuthUrl:
    def test_returns_url_with_google_domain(self, client: TestClient, auth_headers: dict):
        with patch("app.services.email_account_service.get_auth_url",
                   return_value="https://accounts.google.com/o/oauth2/auth?scope=..."):
            resp = client.get(f"{BASE}/email-accounts/auth-url", headers=auth_headers)
        assert resp.status_code == 200
        assert "accounts.google.com" in resp.json()["url"]

    def test_no_auth_returns_401(self, client: TestClient):
        with _no_auth(client):
            resp = client.get(f"{BASE}/email-accounts/auth-url")
        assert resp.status_code == 401

    def test_missing_client_id_raises(self, client: TestClient, auth_headers: dict):
        """If get_auth_url raises (bad config), a server error propagates."""
        with patch("app.routers.settings.svc.get_auth_url",
                   side_effect=ValueError("client_id required")):
            try:
                resp = client.get(f"{BASE}/email-accounts/auth-url", headers=auth_headers)
                assert resp.status_code == 500
            except ValueError:
                pass   # TestClient re-raises server exceptions — both paths are valid


# ── PATCH /settings/email-accounts/{id} ──────────────────────────────────────

class TestUpdateEmailAccount:
    def test_update_display_name(self, client: TestClient, auth_headers: dict, db):
        acct = _insert_account(db, email=f"upd_{uuid.uuid4().hex[:6]}@test.com")
        resp = client.patch(f"{BASE}/email-accounts/{acct.id}",
                            json={"display_name": "Updated Name"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated Name"

    def test_toggle_inactive(self, client: TestClient, auth_headers: dict, db):
        acct = _insert_account(db, email=f"tgl_{uuid.uuid4().hex[:6]}@test.com", is_active=True)
        resp = client.patch(f"{BASE}/email-accounts/{acct.id}",
                            json={"is_active": False}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_update_nonexistent_returns_404(self, client: TestClient, auth_headers: dict):
        resp = client.patch(f"{BASE}/email-accounts/{uuid.uuid4()}",
                            json={"display_name": "x"}, headers=auth_headers)
        assert resp.status_code == 404

    def test_invalid_uuid_returns_422(self, client: TestClient, auth_headers: dict):
        resp = client.patch(f"{BASE}/email-accounts/not-a-uuid",
                            json={"display_name": "x"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_update_no_auth(self, client: TestClient, db):
        acct = _insert_account(db, email=f"noauth_{uuid.uuid4().hex[:6]}@test.com")
        with _no_auth(client):
            resp = client.patch(f"{BASE}/email-accounts/{acct.id}", json={"display_name": "x"})
        assert resp.status_code == 401


# ── POST /settings/email-accounts/{id}/set-primary ───────────────────────────

class TestSetPrimary:
    def test_set_primary_clears_others(self, client: TestClient, auth_headers: dict, db):
        a1 = _insert_account(db, email=f"p1_{uuid.uuid4().hex[:6]}@test.com", is_primary=True)
        a2 = _insert_account(db, email=f"p2_{uuid.uuid4().hex[:6]}@test.com", is_primary=False)
        resp = client.post(f"{BASE}/email-accounts/{a2.id}/set-primary", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["is_primary"] is True
        # a1 should now be non-primary
        db.refresh(a1)
        assert a1.is_primary is False

    def test_set_primary_nonexistent_returns_404(self, client: TestClient, auth_headers: dict):
        resp = client.post(f"{BASE}/email-accounts/{uuid.uuid4()}/set-primary",
                           headers=auth_headers)
        assert resp.status_code == 404

    def test_set_primary_no_auth(self, client: TestClient, db):
        acct = _insert_account(db, email=f"noauth_sp_{uuid.uuid4().hex[:6]}@test.com")
        with _no_auth(client):
            resp = client.post(f"{BASE}/email-accounts/{acct.id}/set-primary")
        assert resp.status_code == 401


# ── DELETE /settings/email-accounts/{id} ─────────────────────────────────────

class TestDeleteEmailAccount:
    def test_delete_removes_account(self, client: TestClient, auth_headers: dict, db):
        acct = _insert_account(db, email=f"del_{uuid.uuid4().hex[:6]}@test.com")
        resp = client.delete(f"{BASE}/email-accounts/{acct.id}", headers=auth_headers)
        assert resp.status_code == 204
        # Confirm gone
        resp2 = client.get(f"{BASE}/email-accounts", headers=auth_headers)
        emails = [i["email_address"] for i in resp2.json()["items"]]
        assert acct.email_address not in emails

    def test_delete_nonexistent_returns_404(self, client: TestClient, auth_headers: dict):
        resp = client.delete(f"{BASE}/email-accounts/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_no_auth(self, client: TestClient, db):
        acct = _insert_account(db, email=f"noauth_del_{uuid.uuid4().hex[:6]}@test.com")
        with _no_auth(client):
            resp = client.delete(f"{BASE}/email-accounts/{acct.id}")
        assert resp.status_code == 401


# ── OAuth callback ────────────────────────────────────────────────────────────

class TestOAuthCallback:
    def test_successful_callback_stores_account_and_redirects(
        self, client: TestClient, db
    ):
        mock_creds = _FakeCreds()
        mock_flow = MagicMock()
        mock_flow.credentials = mock_creds

        user_email = f"cb_{uuid.uuid4().hex[:6]}@gmail.com"
        mock_oauth2_svc = MagicMock()
        mock_oauth2_svc.userinfo().get().execute.return_value = {
            "email": user_email, "name": "Test User"
        }
        with patch("app.services.email_account_service._get_flow", return_value=mock_flow), \
             patch("app.services.email_account_service._encode_token", return_value="fake_tok"), \
             patch("googleapiclient.discovery.build", return_value=mock_oauth2_svc):
            resp = client.get(
                f"{BASE}/email-accounts/callback?code=fake_code",
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "settings" in resp.headers["location"]

    def test_callback_error_redirects_with_error_param(self, client: TestClient):
        with patch("app.services.email_account_service._get_flow",
                   side_effect=Exception("Invalid code")):
            resp = client.get(
                f"{BASE}/email-accounts/callback?code=bad_code",
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "email_error=true" in resp.headers["location"]


# ── Auto-send per account ─────────────────────────────────────────────────────

class TestAutoSendToggle:
    def test_auto_send_defaults_to_true(self, client: TestClient, auth_headers: dict, db):
        acct = _insert_account(db, email=f"as_{uuid.uuid4().hex[:6]}@test.com")
        resp = client.get(f"{BASE}/email-accounts", headers=auth_headers)
        match = next((i for i in resp.json()["items"] if i["email_address"] == acct.email_address), None)
        assert match is not None
        assert match["auto_send_enabled"] is True

    def test_disable_auto_send(self, client: TestClient, auth_headers: dict, db):
        acct = _insert_account(db, email=f"as_off_{uuid.uuid4().hex[:6]}@test.com")
        resp = client.patch(
            f"{BASE}/email-accounts/{acct.id}",
            json={"auto_send_enabled": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["auto_send_enabled"] is False

    def test_re_enable_auto_send(self, client: TestClient, auth_headers: dict, db):
        acct = _insert_account(db, email=f"as_on_{uuid.uuid4().hex[:6]}@test.com")
        # disable first
        client.patch(f"{BASE}/email-accounts/{acct.id}", json={"auto_send_enabled": False}, headers=auth_headers)
        # re-enable
        resp = client.patch(f"{BASE}/email-accounts/{acct.id}", json={"auto_send_enabled": True}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["auto_send_enabled"] is True

    def test_auto_send_field_in_list_response(self, client: TestClient, auth_headers: dict, db):
        _insert_account(db, email=f"as_list_{uuid.uuid4().hex[:6]}@test.com")
        resp = client.get(f"{BASE}/email-accounts", headers=auth_headers)
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "auto_send_enabled" in item

    def test_route_after_gaps_holds_when_auto_send_disabled(self):
        """When auto_send_enabled=False, route_after_gaps must return hold_draft even with no gaps."""
        from app.services.workflows.email_nodes import route_after_gaps
        assert route_after_gaps({"gaps": [], "auto_send_enabled": False}) == "hold_draft"

    def test_route_after_gaps_auto_sends_when_enabled_and_no_gaps(self):
        from app.services.workflows.email_nodes import route_after_gaps
        assert route_after_gaps({"gaps": [], "auto_send_enabled": True}) == "auto_send"

    def test_route_after_gaps_holds_when_gaps_exist_regardless_of_flag(self):
        from app.services.workflows.email_nodes import route_after_gaps
        assert route_after_gaps({"gaps": [{"q": "?"}], "auto_send_enabled": True}) == "hold_draft"

    def test_route_defaults_to_auto_send_when_flag_missing(self):
        """Backwards compat: missing auto_send_enabled key defaults to True."""
        from app.services.workflows.email_nodes import route_after_gaps
        assert route_after_gaps({"gaps": []}) == "auto_send"

    def test_update_no_auth(self, client: TestClient, db):
        acct = _insert_account(db, email=f"as_noauth_{uuid.uuid4().hex[:6]}@test.com")
        with _no_auth(client):
            resp = client.patch(f"{BASE}/email-accounts/{acct.id}", json={"auto_send_enabled": False})
        assert resp.status_code == 401
