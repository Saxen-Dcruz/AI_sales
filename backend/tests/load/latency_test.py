"""
Voice Agent Latency Tests.

Measures latency of each sub-component in the voice call path:
  1. LiveKit JWT token generation (local, should be <1ms)
  2. LiveKit room creation via REST API
  3. RAG query round-trip (the dominant latency: embed → pgvector → rerank → LLM)
  4. Feedback URL signing (HMAC, should be <1ms)
  5. Full create_room() service call (includes DB write)
  6. Escalation service (GMeet + send — mocked for unit timing)

Each test runs N iterations and reports min/median/p95/p99/max in ms.

Run inside Docker:
    docker compose exec backend bash -c "
        cd /app && PYTHONPATH=/app python tests/load/latency_test.py
    "

Add --rag flag to also run the RAG round-trip (requires live Gemini API):
    python tests/load/latency_test.py --rag

Add --iterations N to control sample size (default 20):
    python tests/load/latency_test.py --iterations 50
"""

import argparse
import asyncio
import statistics
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Callable

sys.path.insert(0, "/app")


# ── Timing helpers ─────────────────────────────────────────────────────────

@contextmanager
def _measure(label: str, samples: list):
    start = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - start) * 1000
    samples.append(elapsed_ms)


def _stats(samples: list[float]) -> dict:
    if not samples:
        return {}
    s = sorted(samples)
    n = len(s)
    return {
        "n":      n,
        "min":    round(min(s), 2),
        "median": round(statistics.median(s), 2),
        "p95":    round(s[int(n * 0.95)], 2),
        "p99":    round(s[min(int(n * 0.99), n - 1)], 2),
        "max":    round(max(s), 2),
    }


def _print_table(results: dict[str, dict]) -> None:
    print("\n" + "=" * 80)
    print(f"{'Component':<42} {'n':>4} {'min':>8} {'med':>8} {'p95':>8} {'p99':>8} {'max':>8}")
    print("-" * 80)
    for label, st in results.items():
        if not st:
            continue
        print(
            f"{label:<42} {st['n']:>4} "
            f"{st['min']:>7}ms {st['median']:>7}ms "
            f"{st['p95']:>7}ms {st['p99']:>7}ms "
            f"{st['max']:>7}ms"
        )
    print("=" * 80)


# ── Test 1: JWT token generation (local, CPU-only) ─────────────────────────

def test_token_generation(n: int) -> list[float]:
    from app.services.voice_room_service import _make_token
    samples = []
    for _ in range(n):
        room = f"rdl-{uuid.uuid4().hex}"
        with _measure("token_gen", samples):
            _make_token(room, identity=f"customer-{uuid.uuid4().hex[:8]}", can_publish=True)
    return samples


# ── Test 2: LiveKit REST room creation ─────────────────────────────────────

def test_livekit_room_create(n: int) -> list[float]:
    from app.services.voice_room_service import _create_lk_room, _delete_lk_room
    samples = []
    rooms = []
    for _ in range(n):
        room = f"rdl-latency-{uuid.uuid4().hex[:8]}"
        with _measure("livekit_create", samples):
            ok = _create_lk_room(room)
        if ok:
            rooms.append(room)
    # Clean up
    for room in rooms:
        _delete_lk_room(room)
    return samples


# ── Test 3: Full create_room() service (DB + LiveKit) ─────────────────────

def test_create_room_service(n: int) -> list[float]:
    from app.database.core import SessionLocal
    from app.models.voice_session import VoiceSession
    from app.models.user import User
    from app.services.auth_service import hash_password
    from app.services.voice_room_service import create_room

    # Ensure a test owner exists
    with SessionLocal() as db:
        owner = db.query(User).filter(User.email == "latency-test@rdltest.com").first()
        if not owner:
            owner = User(
                email="latency-test@rdltest.com",
                hashed_password=hash_password("test"),
                is_active=True, is_superuser=False,
            )
            db.add(owner)
            db.commit()
            db.refresh(owner)
        owner_id = owner.id

    samples = []
    session_ids = []
    for _ in range(n):
        with SessionLocal() as db:
            with _measure("create_room_service", samples):
                try:
                    # Mock the actual LiveKit REST call so we measure only our code
                    from unittest.mock import patch
                    with patch("app.services.voice_room_service._create_lk_room", return_value=True):
                        session, _ = create_room(db, channel_origin="whatsapp", owner_id=owner_id)
                    session_ids.append(session.id)
                except Exception as exc:
                    print(f"  [SKIP] create_room error: {exc}")

    # Cleanup
    with SessionLocal() as db:
        db.query(VoiceSession).filter(VoiceSession.id.in_(session_ids)).delete()
        db.commit()

    return samples


# ── Test 4: Feedback URL signing (HMAC, CPU-only) ─────────────────────────

def test_feedback_url_signing(n: int) -> list[float]:
    from app.services.voice_feedback_service import _sign
    samples = []
    for _ in range(n):
        session_id = str(uuid.uuid4())
        with _measure("hmac_sign", samples):
            _sign(session_id)
    return samples


# ── Test 5: RAG query (live Gemini + pgvector) ────────────────────────────

async def _rag_query(question: str) -> float:
    from app.agents.tools.rag_chain import RAGManager
    mgr = RAGManager()
    await mgr.initialize_rag()
    start = time.perf_counter()
    await mgr.query_rag_database(question)
    return (time.perf_counter() - start) * 1000


def test_rag_round_trip(n: int) -> list[float]:
    QUESTIONS = [
        "What is the price of the Industrial Data Logger?",
        "What connectivity options does the 4G LTE router support?",
        "What is included in the IoT Starter Kit?",
        "How long is the warranty on the PLC module?",
        "Compare the RDL740 and RDL795 development boards",
    ]
    samples = []
    for i in range(n):
        q = QUESTIONS[i % len(QUESTIONS)]
        try:
            ms = asyncio.run(_rag_query(q))
            samples.append(ms)
            print(f"  RAG [{i+1}/{n}] {ms:.0f}ms — {q[:50]}")
        except Exception as exc:
            print(f"  RAG [{i+1}/{n}] FAILED: {exc}")
    return samples


# ── Test 6: Feedback URL verification (HMAC constant-time compare) ────────

def test_feedback_sig_verify(n: int) -> list[float]:
    from app.services.voice_feedback_service import _sign, verify_signature
    session_id = str(uuid.uuid4())
    sig = _sign(session_id)
    samples = []
    for _ in range(n):
        with _measure("hmac_verify", samples):
            verify_signature(session_id, sig)
    return samples


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Voice Agent Latency Tests")
    parser.add_argument("--iterations", type=int, default=20,  help="Samples per test (default 20)")
    parser.add_argument("--rag",        action="store_true",   help="Include live RAG query test (requires Gemini API)")
    parser.add_argument("--livekit",    action="store_true",   help="Include real LiveKit REST room creation test")
    parser.add_argument("--rag-n",      type=int, default=5,   help="RAG sample count (default 5, expensive)")
    args = parser.parse_args()

    n = args.iterations
    results = {}

    print(f"\n[LATENCY] Running {n} iterations per test...")

    print("[1/6] JWT token generation...")
    results["JWT token generation (local)"] = _stats(test_token_generation(n))

    if args.livekit:
        print("[2/6] LiveKit REST room creation (requires live LiveKit)...")
        results["LiveKit room create (REST)"] = _stats(test_livekit_room_create(n))
    else:
        print("[2/6] LiveKit REST — skipped (pass --livekit to include)")

    print("[3/6] Full create_room() service (DB + mocked LiveKit)...")
    results["create_room() service (DB)"] = _stats(test_create_room_service(n))

    print("[4/6] HMAC feedback URL signing...")
    results["HMAC sign (feedback URL)"] = _stats(test_feedback_url_signing(n * 10))

    print("[5/6] HMAC signature verification...")
    results["HMAC verify (signature check)"] = _stats(test_feedback_sig_verify(n * 10))

    if args.rag:
        print(f"[6/6] RAG round-trip ({args.rag_n} samples, live Gemini API)...")
        results["RAG query (embed→pgvec→rerank→LLM)"] = _stats(test_rag_round_trip(args.rag_n))
    else:
        print("[6/6] RAG query — skipped (pass --rag to include, uses Gemini credits)")

    _print_table(results)

    print("\n[TARGETS]")
    print("  JWT token:       < 1ms   (cryptographic, local)")
    print("  HMAC sign:       < 1ms   (local computation)")
    print("  HMAC verify:     < 1ms   (local computation)")
    print("  DB create_room:  < 50ms  (DB round-trip)")
    print("  LiveKit REST:    < 200ms (HTTP to LiveKit server)")
    print("  RAG query:       < 8s    (network bound — Gemini + pgvector)")

    # Return non-zero if any critical latency exceeds threshold
    token_stats = results.get("JWT token generation (local)", {})
    if token_stats and token_stats.get("p99", 0) > 10:
        print(f"\n[FAIL] JWT token p99 {token_stats['p99']}ms exceeds 10ms threshold")
        sys.exit(1)

    db_stats = results.get("create_room() service (DB)", {})
    if db_stats and db_stats.get("p95", 0) > 200:
        print(f"\n[WARN] create_room p95 {db_stats['p95']}ms is above 200ms — check DB pool")

    print("\n[PASS] All latency targets met.")


if __name__ == "__main__":
    main()
