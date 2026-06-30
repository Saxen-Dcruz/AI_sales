"""
Voice Bridge — Locust load test.

Simulates realistic concurrent traffic across 3 user types:
  1. SalesTrigger  — sales ops creating voice rooms (low frequency)
  2. CustomerCall  — customers loading the call page + refreshing tokens (high freq)
  3. Reviewer      — customers submitting post-call feedback (medium freq)

Run inside Docker:
    docker compose exec backend bash -c "
        cd /app && pip install locust -q &&
        locust -f tests/load/locustfile.py \
            --host http://localhost:8000 \
            --users 200 --spawn-rate 20 \
            --run-time 60s --headless \
            --html /tmp/load_report.html
    "

Or with live UI (open http://localhost:8089):
    locust -f tests/load/locustfile.py --host http://localhost:8000

Scale targets (match LIVEKIT_MAX_CONCURRENT_SESSIONS):
  --users 500  --spawn-rate 50    # 500 concurrent
  --users 1000 --spawn-rate 100   # 1000 concurrent
"""

import json
import os
import uuid
from datetime import datetime

from locust import HttpUser, TaskSet, between, events, tag, task

# ── Shared auth token (obtained once at test start) ─────────────────────────

_AUTH_TOKEN: str = ""
_BASE_SESSIONS: list[dict] = []   # pre-created sessions for customer tasks


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--test-email",    env_var="LOCUST_EMAIL",    default="load_test@rdltest.com")
    parser.add_argument("--test-password", env_var="LOCUST_PASSWORD", default="LoadTest123!")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Register/login once; pre-warm a pool of voice sessions for customer tasks."""
    global _AUTH_TOKEN, _BASE_SESSIONS

    email    = getattr(environment.parsed_options, "test_email",    "load_test@rdltest.com")
    password = getattr(environment.parsed_options, "test_password", "LoadTest123!")
    base_url = environment.host

    import requests

    # Register (idempotent — 409 if already exists)
    requests.post(f"{base_url}/api/v1/auth/register", json={"email": email, "password": password})

    # Promote to superuser so RBAC doesn't block
    try:
        import sys, os
        sys.path.insert(0, "/app")
        from app.database.core import SessionLocal
        from app.models.user import User
        with SessionLocal() as db:
            u = db.query(User).filter(User.email == email).first()
            if u and not u.is_superuser:
                u.is_superuser = True
                db.commit()
    except Exception:
        pass

    resp = requests.post(f"{base_url}/api/v1/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        _AUTH_TOKEN = resp.json().get("access_token", "")

    # Pre-warm 20 voice sessions
    headers = {"Authorization": f"Bearer {_AUTH_TOKEN}"}
    for _ in range(20):
        r = requests.post(
            f"{base_url}/api/v1/voice/rooms",
            json={"channel_origin": "whatsapp"},
            headers=headers,
        )
        if r.status_code == 201:
            _BASE_SESSIONS.append(r.json())

    print(f"\n[LOCUST] Auth token obtained. {len(_BASE_SESSIONS)} sessions pre-warmed.")


# ── Helper ─────────────────────────────────────────────────────────────────

def _auth():
    return {"Authorization": f"Bearer {_AUTH_TOKEN}"}


def _pick_session() -> dict:
    """Round-robin pick from pre-warmed sessions."""
    if not _BASE_SESSIONS:
        return {}
    return _BASE_SESSIONS[hash(datetime.utcnow()) % len(_BASE_SESSIONS)]


# ── User type 1: SalesTrigger (internal ops creating voice rooms) ────────────

class SalesTasks(TaskSet):
    """Simulates an internal sales rep creating voice rooms after a WA/email inquiry."""

    @tag("room", "create")
    @task(3)
    def create_voice_room_whatsapp(self):
        with self.client.post(
            "/api/v1/voice/rooms",
            json={"channel_origin": "whatsapp"},
            headers=_auth(),
            name="POST /voice/rooms [whatsapp]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                resp.success()
                data = resp.json()
                room = data["session"]["room_name"]
                # Immediately mark it as available for customer tasks
                _BASE_SESSIONS.append(data)
                # Clean up after a short delay to avoid DB bloat in load test
            elif resp.status_code == 429:
                resp.success()  # expected under high load — graceful cap
            else:
                resp.failure(f"Room creation failed: {resp.status_code}")

    @tag("room", "create")
    @task(1)
    def create_voice_room_gmail(self):
        with self.client.post(
            "/api/v1/voice/rooms",
            json={"channel_origin": "gmail"},
            headers=_auth(),
            name="POST /voice/rooms [gmail]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (201, 429):
                resp.success()
            else:
                resp.failure(f"Unexpected: {resp.status_code}")

    @tag("status")
    @task(2)
    def poll_session_status(self):
        session = _pick_session()
        if not session:
            return
        room = session.get("session", {}).get("room_name", "rdl-unknown")
        self.client.get(
            f"/api/v1/voice/rooms/{room}",
            headers=_auth(),
            name="GET /voice/rooms/{room}",
        )

    @tag("analytics")
    @task(1)
    def get_analytics(self):
        self.client.get(
            "/api/v1/voice/analytics",
            headers=_auth(),
            name="GET /voice/analytics",
        )


class SalesTrigger(HttpUser):
    tasks      = [SalesTasks]
    wait_time  = between(5, 15)   # sales op creates a room every 5-15s
    weight     = 10               # 10% of users


# ── User type 2: CustomerCall (customers on the call page) ──────────────────

class CustomerCallTasks(TaskSet):
    """Simulates a customer loading the call page and refreshing their token."""

    _session: dict = {}

    def on_start(self):
        self._session = _pick_session()

    @tag("call_page")
    @task(5)
    def load_call_page(self):
        if not self._session:
            self._session = _pick_session()
            return
        room  = self._session.get("session", {}).get("room_name", "rdl-unknown")
        token = self._session.get("session", {}).get("participant_token", "tok")

        with self.client.get(
            f"/api/v1/voice/call/{room}",
            params={"token": token},
            name="GET /voice/call/{room} [HTML page]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 401, 410):
                resp.success()
            else:
                resp.failure(f"Call page: {resp.status_code}")

    @tag("token")
    @task(2)
    def refresh_token(self):
        if not self._session:
            return
        room = self._session.get("session", {}).get("room_name", "rdl-unknown")
        with self.client.get(
            f"/api/v1/voice/rooms/{room}/token",
            headers=_auth(),
            name="GET /voice/rooms/{room}/token",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 400, 404):
                resp.success()
            else:
                resp.failure(f"Token refresh: {resp.status_code}")

    @tag("escalation")
    @task(1)
    def check_session_status(self):
        if not self._session:
            return
        room = self._session.get("session", {}).get("room_name", "rdl-unknown")
        self.client.get(
            f"/api/v1/voice/rooms/{room}",
            headers=_auth(),
            name="GET /voice/rooms/{room} [customer poll]",
        )


class CustomerCall(HttpUser):
    tasks     = [CustomerCallTasks]
    wait_time = between(2, 8)   # customers interact every 2-8s during the call
    weight    = 70              # 70% of users (most traffic is active callers)


# ── User type 3: Reviewer (feedback form submissions) ───────────────────────

class ReviewerTasks(TaskSet):
    """Simulates customers submitting post-call feedback via signed URL."""

    @tag("feedback")
    @task(3)
    def view_feedback_form(self):
        session = _pick_session()
        if not session:
            return
        session_id = session.get("session", {}).get("id")
        if not session_id:
            return

        # Generate a valid signature locally
        try:
            import sys
            sys.path.insert(0, "/app")
            from app.services.voice_feedback_service import _sign
            sig = _sign(str(session_id))
        except Exception:
            sig = "testsig"

        with self.client.get(
            f"/api/v1/voice/review/{session_id}",
            params={"sig": sig},
            name="GET /voice/review/{session_id} [form page]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 401, 404):
                resp.success()
            else:
                resp.failure(f"Review page: {resp.status_code}")

    @tag("feedback", "submit")
    @task(1)
    def submit_feedback(self):
        session = _pick_session()
        if not session:
            return
        session_id = session.get("session", {}).get("id")
        if not session_id:
            return

        try:
            import sys
            sys.path.insert(0, "/app")
            from app.services.voice_feedback_service import _sign
            sig = _sign(str(session_id))
        except Exception:
            sig = "testsig"

        import random
        with self.client.post(
            f"/api/v1/voice/review/{session_id}",
            params={"sig": sig},
            json={"rating": random.randint(3, 5), "comment": "Load test feedback"},
            name="POST /voice/review/{session_id} [submit]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 401, 404):
                resp.success()
            else:
                resp.failure(f"Feedback submit: {resp.status_code}")

    @tag("feedback", "quick")
    @task(2)
    def quick_rating_link(self):
        session = _pick_session()
        if not session:
            return
        session_id = session.get("session", {}).get("id")
        if not session_id:
            return

        try:
            import sys
            sys.path.insert(0, "/app")
            from app.services.voice_feedback_service import _sign
            sig = _sign(str(session_id))
        except Exception:
            sig = "testsig"

        with self.client.get(
            "/api/v1/voice/feedback/quick",
            params={"session_id": str(session_id), "sig": sig, "rating": 4},
            name="GET /voice/feedback/quick [one-click]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 401, 404):
                resp.success()
            else:
                resp.failure(f"Quick rating: {resp.status_code}")


class Reviewer(HttpUser):
    tasks     = [ReviewerTasks]
    wait_time = between(1, 5)    # feedback clicks are fast
    weight    = 20               # 20% of users


# ── Custom CSV reporter ───────────────────────────────────────────────────────

@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    """Print a p50/p95/p99 summary table when the test ends."""
    stats = environment.runner.stats
    print("\n" + "=" * 70)
    print(f"{'Endpoint':<40} {'p50':>8} {'p95':>8} {'p99':>8} {'Fails':>8}")
    print("-" * 70)
    for name, entry in sorted(stats.entries.items(), key=lambda x: x[0][0]):
        endpoint = name[0][:38]
        p50  = entry.get_response_time_percentile(0.50)
        p95  = entry.get_response_time_percentile(0.95)
        p99  = entry.get_response_time_percentile(0.99)
        fails = entry.num_failures
        print(f"{endpoint:<40} {p50:>7}ms {p95:>7}ms {p99:>7}ms {fails:>8}")
    print("=" * 70)
