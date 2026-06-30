import logging
import asyncio
import json
import os

# Ensure GOOGLE_APPLICATION_CREDENTIALS is set from settings before any Google client is imported
from app.core.config import settings
if settings.GOOGLE_APPLICATION_CREDENTIALS:
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", settings.GOOGLE_APPLICATION_CREDENTIALS)

from app.database.core import engine, Base
from fastapi import Request
import redis.asyncio as redis
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.routers import product, usage, auth, leads, companies, deals, gmail, calendar, calls, linkedin, dashboard, lead_gen, users, whatsapp, voice
from app.routers import settings as settings_router
from app.routers import linkedin_accounts as linkedin_accounts_router
from app.routers import email_templates as email_templates_router


import app.models.user
import app.models.email_account
import app.models.refresh_token
import app.models.product
import app.models.campaign
import app.models.company
import app.models.leads
import app.models.deal
import app.models.communication
import app.models.usage
import app.models.calendar_event
import app.models.product_knowledge
import app.models.call
import app.models.blocked_time
import app.models.operator_availability
import app.models.email_sequence
import app.models.linkedin
import app.models.linkedin_b2b
import app.models.lead_gen
import app.models.whatsapp_account
import app.models.whatsapp_message
import app.models.whatsapp_template
import app.models.voice_session
import app.models.email_template


# Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --- Placeholders for future modules ---
# from app.core.config import settings
# from app.core.socket_manager import manager
# from app.database.core import engine, Base
# from app.api import auth, agents, webhooks

# Initialize Logger
logger = logging.getLogger("rdl_sales_logger")

# Initialize Rate Limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize Redis Client (Connects to your rdl_redis container)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
r_client = redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}/0", decode_responses=True)

# ─────────────────────────────────────────────────────────────
# 1. THE REDIS LISTENER (For Real-Time AI & Call Monitoring)
# ─────────────────────────────────────────────────────────────
async def global_redis_listener():
    """
    Listens for live updates from LiveKit or the LangGraph AI Agents.
    Broadcasts these events to the React frontend via WebSockets.
    """
    logger.info("🔌 Redis Listener: Connecting...")
    pubsub = r_client.pubsub()
    await pubsub.subscribe("live_call_events")
    logger.info("✅ Redis Listener: Subscribed to 'live_call_events'")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                raw_data = message["data"]
                logger.info(f"📥 [REDIS-LISTENER] Received: {raw_data}")

                try:
                    data_json = json.loads(raw_data)
                    # Once we build the socket manager, we will uncomment this to send data to React:
                    # await manager.broadcast(data_json)
                except json.JSONDecodeError:
                    logger.error(f"❌ Redis Listener: Could not parse JSON: {raw_data}")
                    
    except asyncio.CancelledError:
        logger.info("🔌 Redis Listener: Task cancelled.")
    except Exception as e:
        logger.error(f"❌ Redis Listener Error: {e}")

# ─────────────────────────────────────────────────────────────
# 2. LIFESPAN (Startup & Shutdown)
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    logger.info("🚀 RDL AI Sales Backend starting up...")
    
    # Start the background Redis listener
    redis_task = asyncio.create_task(global_redis_listener())

    # Initialize Database Tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ PostgreSQL & pgvector tables verified and created.")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")

    # ── Gmail push notifications via Pub/Sub ──────────────────────────────────
    # Register users.watch() for every active Gmail account so Google pushes
    # new-email notifications to POST /api/v1/gmail/webhook instead of polling.
    # Renewal loop runs every 6 hours to renew watches expiring within 25 hours.
    from app.core.config import settings as _cfg
    if _cfg.GMAIL_PUBSUB_TOPIC:
        from app.database.core import SessionLocal
        from app.services.gmail_webhook_service import register_all_watches, renew_expiring_watches

        async def _watch_renewal_loop():
            import asyncio as _asyncio
            from app.database.core import SessionLocal as _SL
            # Initial registration
            with _SL() as db:
                register_all_watches(db)
            # Renew every 6 hours
            while True:
                await _asyncio.sleep(6 * 3600)
                with _SL() as db:
                    renew_expiring_watches(db)

        watch_task = asyncio.create_task(_watch_renewal_loop())
        logger.info(f"[GMAIL WEBHOOK] Pub/Sub mode active — topic={_cfg.GMAIL_PUBSUB_TOPIC}")
    else:
        watch_task = None
        logger.info("[GMAIL WEBHOOK] GMAIL_PUBSUB_TOPIC not set — Gmail push notifications disabled")
        logger.info("[GMAIL WEBHOOK] Use POST /gmail/sync to process emails manually")

    # ── WhatsApp Phase 2B: 24h window re-engagement (every 30 min) ───────────
    async def _wa_reengagement_loop():
        import asyncio as _asyncio
        from app.database.core import SessionLocal as _SL
        from app.services.whatsapp_template_service import send_expiring_window_templates
        while True:
            await _asyncio.sleep(30 * 60)   # check every 30 minutes
            with _SL() as db:
                try:
                    n = send_expiring_window_templates(db)
                    if n:
                        logger.info(f"[WA 24H] Sent {n} re-engagement template(s)")
                except Exception as exc:
                    logger.warning(f"[WA 24H] Re-engagement check failed: {exc}")

    _wa_reeng_task = asyncio.create_task(_wa_reengagement_loop())
    logger.info("[WA 24H] Re-engagement loop started (every 30 min)")

    # ── Voice Bridge: session cleanup + Redis event listener ─────────────────
    async def _voice_cleanup_loop():
        import asyncio as _asyncio
        from app.database.core import SessionLocal as _SL
        from app.services.voice_room_service import expire_stale_sessions
        while True:
            await _asyncio.sleep(5 * 60)  # every 5 minutes
            with _SL() as db:
                try:
                    n = expire_stale_sessions(db)
                    if n:
                        logger.info(f"[VOICE] Expired {n} stale pending sessions")
                except Exception as exc:
                    logger.warning(f"[VOICE] Cleanup loop error: {exc}")

    async def _voice_redis_listener():
        """Listens for voice escalation events published by the AI agent."""
        import asyncio as _asyncio
        import redis.asyncio as _redis
        _r = _redis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}/0", decode_responses=True)
        pubsub = _r.pubsub()
        await pubsub.subscribe("voice:escalate_request", "voice:unanswered")
        logger.info("[VOICE REDIS] Subscribed to voice events")
        try:
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                try:
                    payload = json.loads(msg["data"])
                    channel = msg["channel"]

                    if channel == "voice:escalate_request":
                        session_id = payload.get("session_id")
                        if session_id:
                            from app.database.core import SessionLocal as _SL
                            from app.models.voice_session import VoiceSession as _VS
                            from app.services.escalation_service import offer_escalation_options
                            from app.models.voice_session import EscalationType
                            with _SL() as db:
                                s = db.query(_VS).filter(_VS.id == session_id).first()
                                if s:
                                    offer_escalation_options(db, s, escalation_type=EscalationType.GMEET)
                                    logger.info(f"[VOICE REDIS] Escalated session {session_id}")

                    elif channel == "voice:unanswered":
                        session_id = payload.get("session_id")
                        unanswered = int(payload.get("unanswered_count", 0))
                        if session_id:
                            from app.database.core import SessionLocal as _SL
                            from app.models.voice_session import VoiceSession as _VS
                            from app.services.escalation_service import check_and_auto_escalate
                            with _SL() as db:
                                s = db.query(_VS).filter(_VS.id == session_id).first()
                                if s:
                                    s.unanswered_count = unanswered
                                    db.flush()
                                    check_and_auto_escalate(db, s)

                except Exception as exc:
                    logger.warning(f"[VOICE REDIS] Event handling error: {exc}")
        except asyncio.CancelledError:
            pass
        finally:
            await _r.aclose()

    _voice_cleanup_task = asyncio.create_task(_voice_cleanup_loop())
    _voice_redis_task   = asyncio.create_task(_voice_redis_listener())
    logger.info("[VOICE] Session cleanup loop + Redis listener started")

    yield

    # --- SHUTDOWN ---
    logger.info("🛑 Shutting down AI Backend...")

    if watch_task:
        watch_task.cancel()
        try:
            await watch_task
        except asyncio.CancelledError:
            pass

    _wa_reeng_task.cancel()
    try:
        await _wa_reeng_task
    except asyncio.CancelledError:
        pass

    _voice_cleanup_task.cancel()
    _voice_redis_task.cancel()
    for t in (_voice_cleanup_task, _voice_redis_task):
        try:
            await t
        except asyncio.CancelledError:
            pass

    # Cancel Listener safely
    redis_task.cancel()
    try:
        await redis_task
    except asyncio.CancelledError:
        pass
        
    # Close Redis Connection
    await r_client.close()

# ─────────────────────────────────────────────────────────────
# APP INITIALIZATION
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="RDL AI Sales Gateway",
    version="1.0.0",
    lifespan=lifespan
)

# Attach Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security & Compression Middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000) # Compresses JSON responses > 1KB
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# ROUTERS (To be enabled later)
# ─────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(product.router, prefix="/api/v1")
app.include_router(leads.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(deals.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")
app.include_router(gmail.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")
app.include_router(calls.router,    prefix="/api/v1")
app.include_router(linkedin.router,   prefix="/api/v1")
app.include_router(dashboard.router,  prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(lead_gen.router, prefix="/api/v1")
app.include_router(linkedin_accounts_router.router, prefix="/api/v1")
app.include_router(whatsapp.router, prefix="/api/v1")
app.include_router(voice.router,   prefix="/api/v1")
app.include_router(email_templates_router.router, prefix="/api/v1")
# app.include_router(agents.router, tags=["AI Agents"], prefix="/api/agents")

# ─────────────────────────────────────────────────────────────
# HEALTH CHECKS
# ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health_check():
    return {"status": "UP", "redis_listener": "running"}

@app.get("/")
@limiter.limit("5/minute")
def root(request: Request): # Add the type hint
    return {"message": "Welcome to the RDL AI Sales API", "docs_url": "/docs"}
# Start Prometheus metrics
Instrumentator().instrument(app).expose(app)