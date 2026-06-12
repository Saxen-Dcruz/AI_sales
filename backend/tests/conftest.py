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

# Stable test account UUID used by _insert_email so analytics tests can filter
# emails by account_id IS NOT NULL without needing a real EmailAccount FK row.
# We use a fake token and skip FK enforcement at the application level.
TEST_ACCOUNT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_ACCOUNT_EMAIL = "test-account@rdltest.com"

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


class _FakeCredsForTest:
    """Module-level so it can be pickled by conftest fixtures."""
    expired = False
    refresh_token = "test_refresh"
    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]


@pytest.fixture(scope="session", autouse=True)
def test_email_account():
    """
    Ensure the shared test EmailAccount row exists for the duration of the test session.
    _insert_email uses TEST_ACCOUNT_ID so analytics endpoints (which now filter by
    account_id IS NOT NULL) can see test emails.

    Also seeds a stable owner user for the test account — required since
    EmailAccount.owner_id is NOT NULL (migration 022) — and installs a
    before_insert event listener on the 5 RBAC-owned models so legacy tests
    that don't pass owner_id keep working (event auto-fills to the test owner).
    """
    import base64, pickle
    from sqlalchemy import event
    from app.models.email_account import EmailAccount
    from app.models.leads import Lead
    from app.models.deal import Deal
    from app.models.call import Call
    from app.models.calendar_event import CalendarEvent
    from app.models.user import User
    from app.services.auth_service import hash_password

    fake_token = base64.b64encode(pickle.dumps(_FakeCredsForTest())).decode()
    test_owner_email = "test-owner@rdltest.com"

    with SessionLocal() as db:
        owner = db.query(User).filter(User.email == test_owner_email).first()
        if not owner:
            owner = User(
                email=test_owner_email,
                hashed_password=hash_password("test"),
                is_active=True,
                is_superuser=False,
            )
            db.add(owner)
            db.commit()
            db.refresh(owner)
        owner_id = owner.id

        existing = db.query(EmailAccount).filter(
            EmailAccount.id == TEST_ACCOUNT_ID
        ).first()
        if not existing:
            acct = EmailAccount(
                id=TEST_ACCOUNT_ID,
                owner_id=owner_id,
                email_address=TEST_ACCOUNT_EMAIL,
                display_name="Test Account",
                token_data=fake_token,
                is_active=False,   # inactive so poller ignores it
                is_primary=False,
            )
            db.add(acct)
            db.commit()

    # before_insert listener: legacy tests construct entities without owner_id;
    # auto-fill it to the test owner so the NOT NULL constraint doesn't fail.
    # Real (non-test) code paths always set owner_id explicitly, so this only
    # affects test fixture inserts.
    owned_models = (EmailAccount, Lead, Deal, Call, CalendarEvent)

    def _fill_owner(_mapper, _connection, target):
        if getattr(target, "owner_id", None) is None:
            target.owner_id = owner_id

    for m in owned_models:
        event.listen(m, "before_insert", _fill_owner)

    yield

    for m in owned_models:
        event.remove(m, "before_insert", _fill_owner)
    # Clean up after session
    with SessionLocal() as db:
        db.query(EmailAccount).filter(EmailAccount.id == TEST_ACCOUNT_ID).delete()
        db.commit()


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(client: TestClient) -> dict:
    """Register a test super-admin once per session and return bearer headers.

    The user is promoted to is_superuser=True directly in the DB so that all
    legacy tests (which create entities owned by the test-owner fixture) can
    still access them via assert_can_access() without needing per-test rewrites.
    """
    email = _unique_email()
    client.post(f"{AUTH_BASE}/register", json={"email": email, "password": TEST_PASSWORD})
    # Promote to super-admin so RBAC scoping bypasses for existing tests
    with SessionLocal() as db:
        from app.models.user import User
        u = db.query(User).filter(User.email == email).first()
        if u:
            u.is_superuser = True
            db.commit()
    resp = client.post(f"{AUTH_BASE}/login", json={"email": email, "password": TEST_PASSWORD})
    assert resp.status_code == 200, f"Test user login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
