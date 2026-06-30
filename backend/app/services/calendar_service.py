import logging
import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.models.calendar_event import CalendarEvent, EventStatus, EventTrigger
from app.services.gmail_service import send_email, get_gmail_service

logger = logging.getLogger("rdl_app_logger")

from app.core.config import settings as _cfg
CALENDAR_TOKEN_PATH = Path(_cfg.CALENDAR_TOKEN_PATH)
CALENDAR_ID = "primary"


def auto_log_completed_meetings(db) -> int:
    """
    Check for CalendarEvents whose end_time has passed and status=SCHEDULED.
    Auto-create a Call record for each completed Google Meet so it appears in the
    call log and can have a transcript/outcome added later.
    Returns number of meetings logged.
    """
    from app.models.call import Call, CallDirection, CallStatus
    from app.database.core import SessionLocal

    now = datetime.now(timezone.utc)
    events = (
        db.query(CalendarEvent)
        .filter(
            CalendarEvent.status == EventStatus.SCHEDULED,
            CalendarEvent.end_time < now,
        )
        .all()
    )
    logged = 0
    for event in events:
        # Mark event completed
        event.status = EventStatus.COMPLETED

        # Only create call if not already logged
        existing = db.query(Call).filter(
            Call.livekit_room == event.google_event_id
        ).first()
        if not existing:
            duration = int((event.end_time - event.start_time).total_seconds())
            call = Call(
                owner_id=event.owner_id,          # inherit from the calendar event (fixes NOT NULL bug)
                lead_id=event.lead_id,
                direction=CallDirection.OUTBOUND,
                status=CallStatus.COMPLETED,
                livekit_room=event.google_event_id,
                started_at=event.start_time,
                ended_at=event.end_time,
                duration_seconds=duration,
                notes=f"Google Meet — auto-logged from calendar event.\nMeet link: {event.meet_link or 'N/A'}",
            )
            db.add(call)
            logged += 1
            logger.info(f"[CALENDAR] Auto-logged meeting as call: {event.title}")

    db.commit()
    return logged


def _load_credentials():
    if not CALENDAR_TOKEN_PATH.exists():
        raise FileNotFoundError(f"Calendar token not found at {CALENDAR_TOKEN_PATH}. Run app/scripts/google_auth.py first.")
    with open(CALENDAR_TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(CALENDAR_TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return creds


def get_calendar_service():
    return build("calendar", "v3", credentials=_load_credentials(), cache_discovery=False)


# ── Event creation ────────────────────────────────────────────────────────────

def create_meeting(
    db: Session,
    attendee_email: str,
    title: str,
    description: str,
    start_time: datetime,
    owner_id: UUID,
    duration_minutes: int = 30,
    trigger: EventTrigger = EventTrigger.MANUAL,
    lead_id: Optional[UUID] = None,
    deal_id: Optional[UUID] = None,
    send_invite_email: bool = True,
    gmail_svc=None,
) -> CalendarEvent:
    """
    Create a Google Calendar event with a GMeet link.
    Persists to DB, optionally sends an email invite to the attendee.
    """
    end_time = start_time + timedelta(minutes=duration_minutes)

    event_body = {
        "summary": title,
        "description": f"{description}\n\nLead ID: {lead_id}\nDeal ID: {deal_id}",
        "start": {"dateTime": start_time.isoformat(), "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "Asia/Kolkata"},
        "attendees": [{"email": attendee_email}],
        "conferenceData": {
            "createRequest": {
                "requestId": f"rdl-{lead_id or 'manual'}-{int(start_time.timestamp())}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 60},
                {"method": "popup", "minutes": 15},
            ],
        },
    }

    cal_svc = get_calendar_service()
    created = cal_svc.events().insert(
        calendarId=CALENDAR_ID,
        body=event_body,
        conferenceDataVersion=1,
        sendUpdates="all",  # Google sends calendar invite to attendees automatically
    ).execute()

    meet_link = _extract_meet_link(created)
    calendar_link = created.get("htmlLink")

    event_row = CalendarEvent(
        google_event_id=created["id"],
        owner_id=owner_id,
        lead_id=lead_id,
        deal_id=deal_id,
        title=title,
        description=description,
        attendee_email=attendee_email,
        start_time=start_time,
        end_time=end_time,
        meet_link=meet_link,
        calendar_link=calendar_link,
        trigger=trigger,
        status=EventStatus.SCHEDULED,
        invite_email_sent=False,
    )

    db.add(event_row)
    db.flush()

    if send_invite_email:
        _send_invite_email(attendee_email, title, start_time, end_time, meet_link, description, gmail_svc=gmail_svc)
        event_row.invite_email_sent = True

    db.commit()
    db.refresh(event_row)

    logger.info(f"[CALENDAR] Event created: '{title}' @ {start_time.isoformat()} → {attendee_email} | meet={meet_link}")
    return event_row


def _extract_meet_link(event: dict) -> Optional[str]:
    conf = event.get("conferenceData", {})
    for ep in conf.get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            return ep.get("uri")
    return None


def _send_invite_email(
    to: str,
    title: str,
    start_time: datetime,
    end_time: datetime,
    meet_link: Optional[str],
    description: str,
    gmail_svc=None,
) -> None:
    try:
        from zoneinfo import ZoneInfo
        ist = ZoneInfo("Asia/Kolkata")
        if gmail_svc is None:
            gmail_svc = get_gmail_service()
        time_str = start_time.astimezone(ist).strftime("%A, %d %B %Y at %I:%M %p IST")
        duration_mins = int((end_time - start_time).total_seconds() / 60)

        body = (
            f"Dear {to.split('@')[0].replace('.', ' ').title()},\n\n"
            f"Thank you for your interest in RDL Technologies. "
            f"We are pleased to confirm your meeting with our sales team.\n\n"
            f"**Meeting Details**\n\n"
            f"Title    : {title}\n"
            f"Date     : {time_str}\n"
            f"Duration : {duration_mins} minutes\n"
        )
        if meet_link:
            body += f"Join     : {meet_link}\n"
        body += (
            f"\nA Google Calendar invite has been sent to this email address. "
            f"Please accept the invite to add this meeting to your calendar.\n\n"
            f"If the time does not work for you, please reply to this email and we will reschedule.\n\n"
            f"Looking forward to speaking with you.\n\n"
            f"Best regards,\n"
            f"RDL Technologies Sales Team\n"
            f"developer20@rdltech.in"
        )
        send_email(gmail_svc, to=to, subject=f"Meeting Confirmed: {title}", body=body)
        logger.info(f"[CALENDAR] Invite email sent to {to}")
    except Exception as e:
        logger.error(f"[CALENDAR] Failed to send invite email to {to}: {e}")


# ── Event management ──────────────────────────────────────────────────────────

def cancel_event(db: Session, event: CalendarEvent) -> CalendarEvent:
    cal_svc = get_calendar_service()
    try:
        cal_svc.events().delete(
            calendarId=CALENDAR_ID,
            id=event.google_event_id,
            sendUpdates="all",
        ).execute()
    except Exception as e:
        logger.warning(f"[CALENDAR] Google cancel failed for {event.google_event_id}: {e}")
    event.status = EventStatus.CANCELLED
    db.commit()
    db.refresh(event)
    return event


def _is_slot_free(cal_svc, start: datetime, end: datetime) -> bool:
    """Return True if the primary calendar has no events in [start, end]."""
    try:
        result = cal_svc.freebusy().query(body={
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": "primary"}],
        }).execute()
        busy = result.get("calendars", {}).get("primary", {}).get("busy", [])
        return len(busy) == 0
    except Exception as e:
        logger.warning(f"[CALENDAR] freebusy check failed: {e} — assuming free")
        return True


def _fetch_day_busy_periods(
    cal_svc, day_start: datetime, day_end: datetime
) -> list[tuple[datetime, datetime]]:
    """
    One freebusy API call for an entire day window.
    Returns parsed list of (busy_start, busy_end) datetimes.
    Callers check individual slots locally — avoids N calls per day.
    """
    try:
        result = cal_svc.freebusy().query(body={
            "timeMin": day_start.isoformat(),
            "timeMax": day_end.isoformat(),
            "items": [{"id": "primary"}],
        }).execute()
        busy = result.get("calendars", {}).get("primary", {}).get("busy", [])
        return [
            (datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"]))
            for b in busy
        ]
    except Exception as e:
        logger.warning(f"[CALENDAR] freebusy day query failed: {e} — assuming free")
        return []


def _range_overlaps_busy(
    busy_periods: list[tuple[datetime, datetime]], start: datetime, end: datetime
) -> bool:
    return any(b_start < end and b_end > start for b_start, b_end in busy_periods)


def find_next_free_slot(duration_minutes: int = 30, hours_from_now: int = 24) -> datetime:
    """Return the single next free slot (thin wrapper over find_free_slots)."""
    slots = find_free_slots(count=1, duration_minutes=duration_minutes, hours_from_now=hours_from_now)
    return slots[0] if slots else next_available_slot(hours_from_now)


def find_free_slots(count: int = 3, duration_minutes: int = 30, hours_from_now: int = 24) -> list[datetime]:
    """
    Find up to `count` free meeting slots using the operator's configured availability.

    Algorithm:
    1. Load operator's per-day working hours from DB (OperatorAvailability).
    2. Load scheduling config: buffer_minutes, slot_duration_minutes.
    3. For each working day, generate candidate slots every `duration_minutes` within
       the operator's working window.
    4. Check (slot_start - buffer, slot_end + buffer) is free on Google Calendar so
       no back-to-back meetings are booked.
    5. Also skip any recurring blocks (lunch breaks, etc.) from BlockedTime table.
    Returns up to `count` slots (UTC). Falls back to next_available_slot() if the
    calendar API is unavailable.
    """
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    found: list[datetime] = []

    # ── Load config from DB ───────────────────────────────────────────────────
    buffer_minutes = 15
    avail_by_day: dict[int, dict] = {}
    blocked_windows: list[tuple[int, int, int]] = []

    try:
        from app.database.core import SessionLocal
        from app.models.operator_availability import OperatorAvailability, SchedulingConfig
        from app.models.blocked_time import BlockedTime
        with SessionLocal() as _db:
            cfg = _db.query(SchedulingConfig).filter(SchedulingConfig.id == 1).first()
            if cfg:
                buffer_minutes = cfg.buffer_minutes
                duration_minutes = cfg.slot_duration_minutes  # use configured default

            rows = _db.query(OperatorAvailability).all()
            for r in rows:
                avail_by_day[r.day_of_week] = {
                    "available": r.is_available,
                    "start": (r.start_hour, r.start_minute),
                    "end": (r.end_hour, r.end_minute),
                }

            blocks = _db.query(BlockedTime).filter(BlockedTime.is_active == True).all()
            blocked_windows = [(b.day_of_week, b.start_hour, b.end_hour) for b in blocks]
    except Exception as e:
        logger.warning(f"[CALENDAR] Could not load availability config: {e}")

    # Fallback defaults if nothing in DB
    if not avail_by_day:
        for d in range(6):   # Mon–Sat default
            avail_by_day[d] = {"available": True, "start": (9, 0), "end": (18, 0)}
        avail_by_day[6] = {"available": False, "start": (9, 0), "end": (18, 0)}

    try:
        cal_svc = get_calendar_service()
    except Exception:
        return [next_available_slot(hours_from_now)]

    now_ist = datetime.now(timezone.utc).astimezone(ist)
    earliest = now_ist + timedelta(hours=hours_from_now)
    start_date = earliest.date()

    for day_offset in range(28):  # look up to 4 weeks ahead
        check_date = start_date + timedelta(days=day_offset)
        dow = check_date.weekday()  # 0=Mon … 6=Sun

        day_cfg = avail_by_day.get(dow, {})
        if not day_cfg.get("available", False):
            continue

        sh, sm = day_cfg["start"]
        eh, em = day_cfg["end"]

        slot_start = datetime(check_date.year, check_date.month, check_date.day,
                              sh, sm, 0, tzinfo=ist)
        day_end = datetime(check_date.year, check_date.month, check_date.day,
                           eh, em, 0, tzinfo=ist)

        # One freebusy call for the entire day window (+ buffer padding) instead of
        # one call per slot — reduces up to 16 API calls/day to 1.
        fetch_start = slot_start - timedelta(minutes=buffer_minutes)
        fetch_end = day_end + timedelta(minutes=buffer_minutes)
        busy_periods = _fetch_day_busy_periods(cal_svc, fetch_start, fetch_end)

        while True:
            slot_end = slot_start + timedelta(minutes=duration_minutes)
            if slot_end > day_end:
                break

            if slot_start <= earliest:
                slot_start = slot_start + timedelta(minutes=duration_minutes)
                continue

            if any(
                bday == dow and bstart <= slot_start.hour < bend
                for bday, bstart, bend in blocked_windows
            ):
                slot_start = slot_start + timedelta(minutes=duration_minutes)
                continue

            check_start = slot_start - timedelta(minutes=buffer_minutes)
            check_end = slot_end + timedelta(minutes=buffer_minutes)

            if not _range_overlaps_busy(busy_periods, check_start, check_end):
                logger.info(
                    f"[CALENDAR] Free slot found: {slot_start.isoformat()} "
                    f"(buffer={buffer_minutes}min)"
                )
                found.append(slot_start.astimezone(timezone.utc))
                if len(found) >= count:
                    return found

            slot_start = slot_start + timedelta(minutes=duration_minutes)

    if found:
        return found
    logger.warning("[CALENDAR] No free slot found in 28 days — using fallback")
    return [next_available_slot(hours_from_now)]


def next_available_slot(hours_from_now: int = 24) -> datetime:
    """Fallback: next 10 AM IST on a Mon–Sat working day without checking the calendar."""
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    candidate = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).astimezone(ist)
    local = candidate.replace(hour=10, minute=0, second=0, microsecond=0)
    if local <= candidate:
        local = local + timedelta(days=1)
    # Skip Sunday
    while local.weekday() == 6:
        local = local + timedelta(days=1)
    return local.astimezone(timezone.utc)


def reschedule_event(
    db: Session,
    event: CalendarEvent,
    new_start_time: Optional[datetime] = None,
) -> CalendarEvent:
    """
    Reschedule an existing calendar event.
    If new_start_time is None, finds the next free slot automatically.
    Patches Google Calendar (sendUpdates='all' notifies all attendees),
    updates the DB row with the new time and any new meet_link.
    """
    duration_minutes = int((event.end_time - event.start_time).total_seconds() / 60)

    if new_start_time is None:
        new_start_time = find_next_free_slot(duration_minutes=duration_minutes)

    new_end_time = new_start_time + timedelta(minutes=duration_minutes)

    cal_svc = get_calendar_service()
    updated = cal_svc.events().patch(
        calendarId=CALENDAR_ID,
        eventId=event.google_event_id,
        body={
            "start": {"dateTime": new_start_time.isoformat(), "timeZone": "Asia/Kolkata"},
            "end":   {"dateTime": new_end_time.isoformat(),   "timeZone": "Asia/Kolkata"},
        },
        sendUpdates="all",
    ).execute()

    event.start_time = new_start_time
    event.end_time = new_end_time
    new_meet = _extract_meet_link(updated)
    if new_meet:
        event.meet_link = new_meet
    event.calendar_link = updated.get("htmlLink", event.calendar_link)
    event.status = EventStatus.SCHEDULED

    db.commit()
    db.refresh(event)

    # Send rescheduled invite email (Google Calendar also sends update automatically via sendUpdates='all')
    if event.attendee_email:
        _send_invite_email(
            to=event.attendee_email,
            title=f"[Rescheduled] {event.title}",
            start_time=new_start_time,
            end_time=new_end_time,
            meet_link=event.meet_link,
            description=event.description or "",
        )

    logger.info(f"[CALENDAR] Rescheduled '{event.title}' → {new_start_time.isoformat()} | meet={event.meet_link}")
    return event
