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

from app.routers import product, usage, auth, leads, companies, deals, gmail, calendar, calls, linkedin, dashboard, lead_gen, users
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

    # Start Gmail inbox poller
    from app.services.gmail_poller import start_poller
    try:
        start_poller()
    except Exception as e:
        logger.warning(f"Gmail poller failed to start: {e}")
    
    # Initialize Database Tables (Uncomment when models are ready)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ PostgreSQL & pgvector tables verified and created.")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        
    yield
    
    # --- SHUTDOWN ---
    logger.info("🛑 Shutting down AI Backend...")
    
    # Stop Gmail poller
    from app.services.gmail_poller import stop_poller
    stop_poller()

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
app.include_router(email_templates_router.router, prefix="/api/v1")
# app.include_router(agents.router, tags=["AI Agents"], prefix="/api/agents")
# app.include_router(webhooks.router, tags=["LiveKit Voice"], prefix="/api/webhooks")

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