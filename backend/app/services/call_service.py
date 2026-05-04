"""
Call pipeline service.

Shared intelligence (RAG fetch, gap extraction, product detection) comes from
sales_gap_service.py — same layer used by the email pipeline.
Call-specific logic (summary prompt, LiveKit integration, call lifecycle) lives here.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.call import Call, CallDirection, CallOutcome, CallStatus
from app.services.sales_gap_service import (
    detect_product,
    extract_structured_gaps,
    fetch_rag_context,
    sanitize_ai_response,
)

logger = logging.getLogger("rdl_app_logger")

_STRUCTURED_EXTRACT_PROMPT = """From this sales call transcript extract three fields.

Reply with JSON only — no markdown, no extra text:
{{"intent": "<ready_to_buy|exploring|not_interested>", "urgency": "<immediate|1-3_months|6+_months|unknown>", "product_interest": "<product name or null>"}}

Definitions:
- intent: ready_to_buy = strong purchase signals; exploring = just researching; not_interested = no interest shown
- urgency: immediate = within 2 weeks; 1-3_months = within a quarter; 6+_months = long horizon; unknown = not mentioned
- product_interest: the specific product name the customer asked about most (null if none)

Transcript:
{transcript}"""

_CALL_SUMMARY_PROMPT = """You are a sales assistant for RDL Technologies. A sales call just ended.
Based on the transcript and product knowledge below, write:
1. A 2-3 sentence summary of what was discussed and the customer's main interest.
2. Answer any product questions the customer asked using the knowledge base.
For questions not in the knowledge base, write "Our team will confirm this and follow up."

FORBIDDEN: never write [PLACEHOLDER], [DETAILS], or any word in square brackets.

Product Knowledge:
{rag_context}

---
Call Transcript:
{transcript}"""

_SENTIMENT_PROMPT = """Analyze the sentiment of this sales call transcript.
Reply with exactly ONE word: POSITIVE, NEUTRAL, or FRUSTRATED.

Transcript:
{transcript}"""


def _extract_structured_fields(transcript: str, client) -> dict:
    """Extract intent/urgency/product_interest from transcript via LLM."""
    import json, re
    prompt = _STRUCTURED_EXTRACT_PROMPT.format(transcript=transcript[:2000])
    try:
        from google.genai import types
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=80),
        )
        raw = resp.text.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip("`").strip()
        data = json.loads(raw)
        return {
            "intent":           data.get("intent") or "exploring",
            "urgency":          data.get("urgency") or "unknown",
            "product_interest": data.get("product_interest"),
        }
    except Exception as e:
        logger.warning(f"[CALL] Structured extraction failed: {e}")
        return {"intent": "exploring", "urgency": "unknown", "product_interest": None}


def _send_post_call_email(call, lead) -> None:
    """Auto-send a follow-up email after a call when intent is not_interested is false."""
    if not lead or not lead.email:
        return
    try:
        from app.services import gmail_service
        from app.database.core import SessionLocal
        from app.models.product import Product

        gmail_svc = gmail_service.get_gmail_service()
        product_name = call.product_interest or call.detected_product_name or "our products"
        datasheet_url = None

        if call.detected_product_id:
            with SessionLocal() as _db:
                import uuid as _uuid
                p = _db.query(Product).filter(Product.id == _uuid.UUID(call.detected_product_id)).first()
                if p:
                    datasheet_url = p.datasheet_link or p.product_link

        body_lines = [
            f"Dear {lead.name},",
            "",
            f"Thank you for speaking with us about {product_name}.",
            "",
            "As discussed, here are some resources that may help:",
        ]
        if datasheet_url:
            body_lines.append(f"  - Product information: {datasheet_url}")
        body_lines += [
            "",
            "We'd love to continue the conversation. Feel free to schedule a follow-up call at your convenience:",
            "  - Reply to this email with your preferred time",
            "  - Or let us know and we'll send a Google Meet link",
            "",
            "Best regards,",
            "RDL Technologies Sales Team",
        ]

        gmail_service.send_email(
            gmail_svc,
            to=lead.email,
            subject=f"Follow-up: {product_name} — RDL Technologies",
            body="\n".join(body_lines),
        )
        logger.info(f"[CALL] Post-call follow-up email sent to {lead.email}")
    except Exception as e:
        logger.warning(f"[CALL] Failed to send post-call email: {e}")


def _match_lead_by_phone(db: Session, phone_number: str):
    """Normalise and match a phone number against existing leads."""
    from app.models.leads import Lead
    norm = phone_number.strip().replace(" ", "").replace("-", "").replace("+", "")
    leads = db.query(Lead).filter(Lead.phone.isnot(None)).all()
    for lead in leads:
        if lead.phone:
            lnorm = lead.phone.strip().replace(" ", "").replace("-", "").replace("+", "")
            if lnorm == norm:
                return lead
    return None


def _upsert_lead_from_phone(db: Session, phone_number: str):
    """Return existing lead by phone or create a stub lead for the caller."""
    existing = _match_lead_by_phone(db, phone_number)
    if existing:
        return existing
    from app.models.leads import Lead
    lead = Lead(
        name=f"Caller {phone_number}",
        phone=phone_number,
        status="Uncontacted",
        interest_level="Warm",
        engagement_score=10,
    )
    db.add(lead)
    db.flush()
    logger.info(f"[CALL] Auto-created lead for caller: {phone_number}")
    return lead


def _generate_call_summary(transcript: str) -> tuple[str, str, object]:
    """
    Run RAG + generate call summary + sentiment via google.genai REST.
    Returns (summary_text, sentiment, genai_client) — client reused by structured extraction.
    """
    rag_context = fetch_rag_context(transcript)

    summary_prompt = _CALL_SUMMARY_PROMPT.format(
        rag_context=rag_context or "No specific product context retrieved.",
        transcript=transcript[:3000],
    )
    sentiment_prompt = _SENTIMENT_PROMPT.format(transcript=transcript[:1000])

    try:
        from google import genai
        from google.genai import types
        import google.auth

        _, project_id = google.auth.default()
        client = genai.Client(vertexai=True, project=project_id, location="us-central1")

        summary_resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=summary_prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        summary = sanitize_ai_response(summary_resp.text.strip())

        sentiment_resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=sentiment_prompt,
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=10),
        )
        sentiment = sentiment_resp.text.strip().upper()
        if sentiment not in ("POSITIVE", "NEUTRAL", "FRUSTRATED"):
            sentiment = "NEUTRAL"

        return summary, sentiment, client
    except Exception as e:
        logger.error(f"[CALL] Failed to generate summary: {e}", exc_info=True)
        return "", "NEUTRAL", None


# ── CRUD ──────────────────────────────────────────────────────────────────────

def create_call(
    db: Session,
    direction: CallDirection,
    phone_number: Optional[str] = None,
    lead_id: Optional[UUID] = None,
    livekit_room: Optional[str] = None,
    handled_by: Optional[str] = None,
) -> Call:
    # Phone-based lead matching — auto-create stub if no match found
    if phone_number and not lead_id:
        lead = _upsert_lead_from_phone(db, phone_number)
        lead_id = lead.id

    call = Call(
        direction=direction,
        status=CallStatus.NEW,
        phone_number=phone_number,
        lead_id=lead_id,
        livekit_room=livekit_room,
        handled_by=handled_by,
        started_at=datetime.now(timezone.utc),
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    logger.info(f"[CALL] Created {direction.value} call {call.id} | lead_id={lead_id}")
    return call


def get_call(db: Session, call_id: UUID) -> Optional[Call]:
    return db.query(Call).filter(Call.id == call_id).first()


def list_calls(
    db: Session,
    lead_id: Optional[UUID] = None,
    status: Optional[CallStatus] = None,
    direction: Optional[CallDirection] = None,
    outcome: Optional[CallOutcome] = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Call], int]:
    q = db.query(Call)
    if lead_id:
        q = q.filter(Call.lead_id == lead_id)
    if status:
        q = q.filter(Call.status == status)
    if direction:
        q = q.filter(Call.direction == direction)
    if outcome:
        q = q.filter(Call.outcome == outcome)
    total = q.count()
    items = q.order_by(Call.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return items, total


def update_call(db: Session, call: Call, **kwargs) -> Call:
    for k, v in kwargs.items():
        if v is not None and hasattr(call, k):
            setattr(call, k, v)
    if kwargs.get("status") == CallStatus.COMPLETED and not call.ended_at:
        call.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(call)
    return call


# ── Transcript processing ─────────────────────────────────────────────────────

def process_transcript(db: Session, call: Call, transcript: str) -> Call:
    """
    After a call ends and transcript is available:
    1. Detect product mentioned
    2. Generate AI summary + sentiment via RAG
    3. Extract structured gaps (questions not answered from knowledge base)
    4. Persist everything on the call row
    """
    call.transcript = transcript

    product_id, product_name, _confidence = detect_product(db, transcript)
    call.detected_product_id = product_id
    call.detected_product_name = product_name

    summary, sentiment, genai_client = _generate_call_summary(transcript)
    call.ai_summary = summary
    call.sentiment = sentiment

    # Structured extraction: intent / urgency / product_interest
    if genai_client:
        structured = _extract_structured_fields(transcript, genai_client)
        call.intent           = structured["intent"]
        call.urgency          = structured["urgency"]
        call.product_interest = structured["product_interest"] or product_name
    else:
        call.intent = "exploring"
        call.urgency = "unknown"
        call.product_interest = product_name

    gaps = extract_structured_gaps(transcript, summary, product_name, product_id)
    call.followup_gaps = gaps if gaps else None

    if call.status not in (CallStatus.COMPLETED, CallStatus.MISSED, CallStatus.FAILED):
        call.status = CallStatus.COMPLETED
    if not call.ended_at:
        call.ended_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(call)

    # Update lead score
    if call.lead_id:
        try:
            from app.services.lead_scoring_service import update_lead_score
            update_lead_score(db, call.lead_id)
        except Exception as e:
            logger.warning(f"[CALL] Lead score update failed: {e}")

    # Post-call follow-up email when customer showed interest
    if call.intent in ("ready_to_buy", "exploring") and call.lead_id:
        try:
            from app.models.leads import Lead
            lead = db.query(Lead).filter(Lead.id == call.lead_id).first()
            _send_post_call_email(call, lead)
        except Exception as e:
            logger.warning(f"[CALL] Post-call email failed: {e}")

    logger.info(
        f"[CALL] Processed transcript for {call.id} | "
        f"product={product_name} | intent={call.intent} | urgency={call.urgency} | "
        f"gaps={len(gaps)} | sentiment={sentiment}"
    )
    return call


# ── Analytics ────────────────────────────────────────────────────────────────

def get_call_analytics(db: Session) -> dict:
    """Aggregate call metrics across all calls."""
    from sqlalchemy import func as sqlfunc

    calls = db.query(Call).all()
    total = len(calls)

    by_direction: dict = {}
    by_status: dict = {}
    by_outcome: dict = {}
    by_sentiment: dict = {}
    by_intent: dict = {}
    total_duration = 0
    duration_count = 0

    for c in calls:
        by_direction[c.direction.value]           = by_direction.get(c.direction.value, 0) + 1
        by_status[c.status.value]                 = by_status.get(c.status.value, 0) + 1
        by_outcome[(c.outcome.value if c.outcome else "unknown")] = \
            by_outcome.get(c.outcome.value if c.outcome else "unknown", 0) + 1
        by_sentiment[(c.sentiment or "NEUTRAL")]  = by_sentiment.get(c.sentiment or "NEUTRAL", 0) + 1
        by_intent[(c.intent or "unknown")]        = by_intent.get(c.intent or "unknown", 0) + 1
        if c.duration_seconds:
            total_duration += c.duration_seconds
            duration_count += 1

    avg_secs = round(total_duration / duration_count, 1) if duration_count else 0.0
    return {
        "total_calls":         total,
        "by_direction":        by_direction,
        "by_status":           by_status,
        "by_outcome":          by_outcome,
        "by_sentiment":        by_sentiment,
        "by_intent":           by_intent,
        "avg_duration_seconds": avg_secs,
        "avg_duration_minutes": round(avg_secs / 60, 2),
    }


# ── Gap resolution ────────────────────────────────────────────────────────────

def resolve_gap(
    db: Session,
    call: Call,
    gap_index: int,
    answer: str,
    category: Optional[str],
    resolved_by: str,
) -> Call:
    gaps = list(call.followup_gaps or [])
    if gap_index < 0 or gap_index >= len(gaps):
        raise ValueError(f"gap_index {gap_index} out of range")
    gap = gaps[gap_index]
    if gap.get("resolved"):
        raise ValueError("Gap already resolved")

    product_id_str = gap.get("product_id")
    eff_category = category or gap.get("topic", "general")

    if product_id_str:
        from app.services import product_knowledge_service
        product_knowledge_service.add_entry(
            db=db,
            product_id=UUID(product_id_str),
            category=eff_category,
            content=f"Q: {gap['question']}\nA: {answer}",
            added_by=resolved_by,
        )
        product_knowledge_service.update_coverage_score(db, product_id_str)

    gaps[gap_index] = {**gap, "resolved": True, "answer": answer, "resolved_by": resolved_by}
    call.followup_gaps = gaps
    db.commit()
    db.refresh(call)
    return call
