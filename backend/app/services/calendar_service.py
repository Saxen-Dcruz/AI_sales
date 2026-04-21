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
        gmail_svc = get_gmail_service()
        time_str = start_time.strftime("%A, %d %B %Y at %I:%M %p IST")
        duration_mins = int((end_time - start_time).total_seconds() / 60)
        meet_section = f"\nJoin Google Meet: {meet_link}" if meet_link else ""
        body = (
            f"Dear {to.split('@')[0].replace('.', ' ').title()},\n\n"
            f"We'd like to schedule a call with you.\n\n"
            f"Title: {title}\n"
            f"Date & Time: {time_str}\n"
            f"Duration: {duration_mins} minutes"
            f"{meet_section}\n\n"
            f"{description}\n\n"
            f"Please confirm your availability by accepting the calendar invite.\n\n"
            f"Best regards,\nRDL Technologies Sales Team"
        )
        send_email(gmail_svc, to=to, subject=f"Meeting Scheduled: {title}", body=body)
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


def next_available_slot(hours_from_now: int = 24) -> datetime:
    """Return a naive next-business-day slot: 24h from now, rounded to next 10:00 AM IST."""
    now = datetime.now(timezone.utc)
    candidate = now + timedelta(hours=hours_from_now)
    # Round to 10:00 AM IST (UTC+5:30 = UTC+5.5h) on that day
    from zoneinfo import ZoneInfo
    ist = ZoneInfo("Asia/Kolkata")
    local = candidate.astimezone(ist).replace(hour=10, minute=0, second=0, microsecond=0)
    # If already past 10 AM on that day, push to next day
    if local <= candidate.astimezone(ist):
        local = local + timedelta(days=1)
    return local.astimezone(timezone.utc)
