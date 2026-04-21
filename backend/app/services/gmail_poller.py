import asyncio
import logging
from contextlib import asynccontextmanager

from sqlalchemy.orm import Session

from app.database.core import SessionLocal
from app.services.email_router_service import process_inbound_email

logger = logging.getLogger("rdl_app_logger")

POLL_INTERVAL_SECONDS = 120  # check inbox every 2 minutes
_poller_task: asyncio.Task | None = None


async def _poll_loop() -> None:
    logger.info("[GMAIL POLLER] Started — polling every %ds", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.to_thread(_run_poll_cycle)
        except Exception as e:
            logger.error(f"[GMAIL POLLER] Cycle error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def _run_poll_cycle() -> None:
    db: Session = SessionLocal()
    try:
        from app.services.gmail_service import fetch_unread_messages, get_gmail_service, ensure_labels_exist
        svc = get_gmail_service()
        ensure_labels_exist(svc)
        messages = fetch_unread_messages(svc, max_results=20)
        if messages:
            logger.info(f"[GMAIL POLLER] Fetched {len(messages)} unread messages")
        for raw_msg in messages:
            try:
                result = process_inbound_email(db, raw_msg)
                if result:
                    logger.info(f"[GMAIL POLLER] Processed: {result.subject} → {result.label.value}")
            except Exception as e:
                logger.error(f"[GMAIL POLLER] Failed to process message {raw_msg.get('id')}: {e}")
    finally:
        db.close()


def start_poller() -> None:
    global _poller_task
    _poller_task = asyncio.create_task(_poll_loop())
    logger.info("[GMAIL POLLER] Background task scheduled")


def stop_poller() -> None:
    global _poller_task
    if _poller_task and not _poller_task.done():
        _poller_task.cancel()
        logger.info("[GMAIL POLLER] Stopped")
