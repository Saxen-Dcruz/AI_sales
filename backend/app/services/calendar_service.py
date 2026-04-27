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

CALENDAR_TOKEN_PATH = Path("calendar_token.json")
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
                lead_id=event.lead_id,
                direction=CallDirection.OUTBOUND,
                status=CallStatus.COMPLETED,
                livekit_room=event.google_event_id,   # reuse field as event reference
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
    duration_minutes: int = 30,
    trigger: EventTrigger = EventTrigger.MANUAL,
    lead_id: Optional[UUID] = None,
    deal_id: Optional[UUID] = None,
    send_invite_email: bool = True,
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
        _send_invite_email(attendee_email, title, start_time, end_time, meet_link, description)
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
) -> None:
    try:
        from zoneinfo import ZoneInfo
        ist = ZoneInfo("Asia/Kolkata")
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


def find_next_free_slot(duration_minutes: int = 30, hours_from_now: int = 24) -> datetime:
    """
    Find the next free slot on the primary Google Calendar.
    Checks 10 AM, 11 AM, 2 PM, 3 PM, 4 PM IST on weekdays for up to 14 days.
    Falls back to 10 AM next business day if the calendar API fails.
    """
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    # Mon–Sat, 9 AM–7 PM IST — hourly slots, prefer morning slots first
    PREFERRED_HOURS = [9, 10, 11, 14, 15, 16, 17, 18]

    try:
        cal_svc = get_calendar_service()
    except Exception:
        return next_available_slot(hours_from_now)

    # Load recurring blocked hours from DB
    blocked_windows: list[tuple[int, int, int]] = []  # (day_of_week, start_hour, end_hour)
    try:
        from app.database.core import SessionLocal
        from app.models.blocked_time import BlockedTime
        with SessionLocal() as _db:
            blocks = _db.query(BlockedTime).filter(BlockedTime.is_active == True).all()
            blocked_windows = [(b.day_of_week, b.start_hour, b.end_hour) for b in blocks]
    except Exception:
        pass

    now_ist = datetime.now(timezone.utc).astimezone(ist)
    earliest = now_ist + timedelta(hours=hours_from_now)
    start_date = earliest.date()

    for day_offset in range(21):
        check_date = start_date + timedelta(days=day_offset)
        if check_date.weekday() == 6:  # skip Sunday only — Mon-Sat are working days
            continue
        for hour in PREFERRED_HOURS:
            # Check recurring blocks
            if any(
                bday == check_date.weekday() and bstart <= hour < bend
                for bday, bstart, bend in blocked_windows
            ):
                continue
            slot_start = datetime(check_date.year, check_date.month, check_date.day,
                                  hour, 0, 0, tzinfo=ist)
            if slot_start <= earliest:
                continue
            slot_end = slot_start + timedelta(minutes=duration_minutes)
            if _is_slot_free(cal_svc, slot_start, slot_end):
                logger.info(f"[CALENDAR] Free slot found: {slot_start.isoformat()}")
                return slot_start.astimezone(timezone.utc)

    logger.warning("[CALENDAR] No free slot found in 14 days — using fallback")
    return next_available_slot(hours_from_now)


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

    logger.info(f"[CALENDAR] Rescheduled '{event.title}' → {new_start_time.isoformat()} | meet={event.meet_link}")
    return event
