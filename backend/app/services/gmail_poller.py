import asyncio
import logging

from sqlalchemy.orm import Session

from app.database.core import SessionLocal

logger = logging.getLogger("rdl_app_logger")

from app.services.workflows.email_workflow import run_email_workflow

POLL_INTERVAL_SECONDS = 120
HEARTBEAT_CYCLES = 5
# 180 cycles × 120 s = 6 hours between LinkedIn auto-searches
LINKEDIN_SEARCH_CYCLES = 180
_poller_task: asyncio.Task | None = None


async def _poll_loop() -> None:
    logger.info("[GMAIL POLLER] Started — polling every %ds", POLL_INTERVAL_SECONDS)
    cycle = 0
    while True:
        try:
            processed = await asyncio.to_thread(_run_poll_cycle)
            cycle += 1
            if processed == 0 and cycle % HEARTBEAT_CYCLES == 0:
                logger.info("[GMAIL POLLER] Alive — inbox empty (cycle %d)", cycle)

            # LinkedIn auto-search via Google CSE every 6 hours
            if cycle % LINKEDIN_SEARCH_CYCLES == 0:
                try:
                    from app.services.google_linkedin_service import run_auto_google_search
                    logger.info("[GMAIL POLLER] Running LinkedIn auto-search via Google (cycle %d)", cycle)
                    await asyncio.to_thread(run_auto_google_search)
                except Exception as e:
                    logger.warning(f"[GMAIL POLLER] LinkedIn auto-search failed: {e}")
        except Exception as e:
            logger.error(f"[GMAIL POLLER] Cycle error: {e}", exc_info=True)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def _run_poll_cycle() -> int:
    """Poll ALL active email accounts. Returns total messages processed."""
    db: Session = SessionLocal()
    try:
        # Auto-log completed Google Meet events
        try:
            from app.services.calendar_service import auto_log_completed_meetings
            auto_log_completed_meetings(db)
        except Exception as e:
            logger.warning(f"[GMAIL POLLER] Meeting auto-log failed: {e}")

        # Process drip sequence steps
        try:
            from app.services.email_sequence_service import process_due_steps
            sent = process_due_steps(db)
            if sent:
                logger.info(f"[GMAIL POLLER] Sent {sent} drip sequence step(s)")
        except Exception as e:
            logger.warning(f"[GMAIL POLLER] Drip sequence processing failed: {e}")

        from app.services.gmail_service import fetch_unread_messages, ensure_labels_exist
        from app.services.email_account_service import get_active_accounts, get_gmail_service_for_account
        from app.services.gmail_service import get_gmail_service as get_legacy_service

        total_processed = 0

        # ── Poll all DB-configured accounts ──────────────────────────────────
        from app.services.gmail_service import mark_as_read as _mark_as_read

        active_accounts = get_active_accounts(db)
        if active_accounts:
            for account in active_accounts:
                try:
                    svc = get_gmail_service_for_account(db, account)
                    ensure_labels_exist(svc, account_key=account.email_address)
                    messages = fetch_unread_messages(svc, max_results=20)
                    if messages:
                        logger.info(f"[GMAIL POLLER] [{account.email_address}] Fetched {len(messages)} message(s)")
                    for raw_msg in messages:
                        msg_id = raw_msg.get("id", "")
                        try:
                            from app.services import gmail_service as _gs
                            _parsed = _gs.parse_message(raw_msg)
                            sender = _gs.extract_email_address(_parsed.get("sender", ""))

                            # Skip emails sent by this account to avoid reply loops
                            if sender.lower() == account.email_address.lower():
                                _mark_as_read(svc, msg_id)
                                continue

                            # Check if this message belongs to an outreach thread first
                            from app.services.outreach_sender import process_inbound_reply
                            _is_outreach = process_inbound_reply(
                                db,
                                gmail_thread_id=_parsed.get("gmail_thread_id", ""),
                                from_email=sender,
                                body=_parsed.get("body_text", ""),
                                gmail_message_id=_parsed.get("gmail_message_id", ""),
                                auto_reply=True,
                            )
                            if _is_outreach:
                                _mark_as_read(svc, msg_id)
                                total_processed += 1
                                continue

                            result = run_email_workflow(db, raw_msg, account_id=str(account.id),
                                                        account_email=account.email_address)
                            if result:
                                logger.info(f"[GMAIL POLLER] [{account.email_address}] "
                                            f"Processed: {result.subject!r} → {result.label.value}")
                                total_processed += 1
                        except Exception as e:
                            logger.error(f"[GMAIL POLLER] [{account.email_address}] "
                                         f"Failed msg {msg_id}: {e}", exc_info=True)
                        finally:
                            # Always mark as read so the same message is never re-fetched
                            try:
                                _mark_as_read(svc, msg_id)
                            except Exception:
                                pass
                except Exception as e:
                    logger.error(f"[GMAIL POLLER] Account {account.email_address} failed: {e}", exc_info=True)
        else:
            # ── Legacy fallback: single gmail_token.json ──────────────────────
            try:
                svc = get_legacy_service()
                ensure_labels_exist(svc)
                messages = fetch_unread_messages(svc, max_results=20)
                if messages:
                    logger.info(f"[GMAIL POLLER] Fetched {len(messages)} unread message(s)")
                for raw_msg in messages:
                    msg_id = raw_msg.get("id", "")
                    try:
                        result = run_email_workflow(db, raw_msg)
                        if result:
                            logger.info(f"[GMAIL POLLER] Processed: {result.subject!r} → {result.label.value}")
                            total_processed += 1
                    except Exception as e:
                        logger.error(f"[GMAIL POLLER] Failed msg {msg_id}: {e}", exc_info=True)
                    finally:
                        try:
                            _mark_as_read(svc, msg_id)
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"[GMAIL POLLER] Legacy poll failed: {e}", exc_info=True)

        return total_processed
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
