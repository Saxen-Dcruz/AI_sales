"""
AI-generated personalized outreach messages and conversation continuation.
"""
import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lead_gen import CampaignContact, OutreachCampaign, OutreachMessage, OutreachThread, ProspectCompany, ProspectContact

logger = logging.getLogger("rdl_app_logger")

_INITIAL_OUTREACH_PROMPT = """You are a B2B sales representative for RDL Technologies.

Write a personalized cold outreach email to this prospect. Keep it concise (3-4 short paragraphs), professional, and focused on value — NOT a generic pitch.

Company: {company_name}
Industry: {industry}
Description: {company_description}
Contact Name: {contact_name}
Contact Role: {job_title}

Our Product Context:
{product_context}

Tone/Template Guidance:
{template_prompt}

Rules:
- Address them by first name
- Reference their specific industry/company naturally
- One clear call to action (schedule a call or reply)
- No buzzwords, no excessive compliments
- Sign off as "RDL Technologies Sales Team"
- Do NOT include a subject line in the body

Write only the email body."""

_REPLY_PROMPT = """You are continuing a B2B sales conversation for RDL Technologies on behalf of their sales team.

Context about our products:
{product_context}

Conversation history (oldest first):
{history}

The prospect just sent:
{new_message}

Write a helpful, professional reply that:
- Answers their questions using the product context
- Moves toward a meeting or next step
- Stays concise (2-3 paragraphs max)
- Signs off as "RDL Technologies Sales Team"

Write only the reply body."""

_SUMMARY_PROMPT = """Summarize this B2B sales email conversation in 2-3 sentences. Focus on: what the prospect is interested in, any questions asked, and the current status.

Conversation:
{history}

Return only the summary."""


def _build_llm(max_tokens: int = 512) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.3,
        max_output_tokens=max_tokens,
        google_api_key=settings.GOOGLE_API_KEY,
    )


def generate_initial_outreach(
    campaign: OutreachCampaign,
    contact: ProspectContact,
    company: ProspectCompany,
) -> str:
    """Generate a personalized first outreach email body."""
    prompt = _INITIAL_OUTREACH_PROMPT.format(
        company_name=company.name,
        industry=company.industry or "your industry",
        company_description=(company.description or "")[:300],
        contact_name=contact.name.split()[0] if contact.name else "there",
        job_title=contact.job_title or "professional",
        product_context=campaign.product_context or "RDL Technologies provides industrial IoT solutions including data loggers, PLCs, sensors, and SCADA software.",
        template_prompt=campaign.email_template_prompt or "Be direct, value-focused, and professional.",
    )
    try:
        llm = _build_llm(max_tokens=600)
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.error(f"[OUTREACH AI] Initial outreach generation failed: {e}")
        return f"Dear {contact.name.split()[0] if contact.name else 'there'},\n\nI'd love to connect about how RDL Technologies can help {company.name}. Would you be open to a quick call?\n\nBest regards,\nRDL Technologies Sales Team"


def generate_reply(
    db: Session,
    thread: OutreachThread,
    new_inbound_message: str,
    campaign: OutreachCampaign,
) -> str:
    """Generate an AI reply to an inbound message."""
    messages = db.query(OutreachMessage).filter(
        OutreachMessage.thread_id == thread.id
    ).order_by(OutreachMessage.created_at).all()

    history_lines = []
    for msg in messages:
        prefix = "US" if msg.direction == "outbound" else "PROSPECT"
        history_lines.append(f"{prefix}: {msg.content[:500]}")
    history = "\n\n".join(history_lines) or "(no prior messages)"

    prompt = _REPLY_PROMPT.format(
        product_context=campaign.product_context or "RDL Technologies provides industrial IoT solutions.",
        history=history,
        new_message=new_inbound_message,
    )
    try:
        llm = _build_llm(max_tokens=500)
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.error(f"[OUTREACH AI] Reply generation failed: {e}")
        return "Thank you for your reply. Our team will get back to you shortly.\n\nBest regards,\nRDL Technologies Sales Team"


def summarize_thread(db: Session, thread: OutreachThread) -> str:
    """Generate a short AI summary of the conversation thread."""
    messages = db.query(OutreachMessage).filter(
        OutreachMessage.thread_id == thread.id
    ).order_by(OutreachMessage.created_at).all()

    if not messages:
        return ""

    history = "\n".join(
        f"{'US' if m.direction == 'outbound' else 'PROSPECT'}: {m.content[:300]}"
        for m in messages
    )
    prompt = _SUMMARY_PROMPT.format(history=history)
    try:
        llm = _build_llm(max_tokens=150)
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        logger.error(f"[OUTREACH AI] Summary failed: {e}")
        return ""


def generate_drafts_for_campaign(db: Session, campaign_id: str) -> int:
    """Generate AI draft for all pending campaign contacts. Returns count."""
    from uuid import UUID
    contacts = db.query(CampaignContact).filter(
        CampaignContact.campaign_id == UUID(campaign_id),
        CampaignContact.status == "pending",
        CampaignContact.ai_draft.is_(None),
    ).all()

    campaign = db.query(OutreachCampaign).filter(OutreachCampaign.id == UUID(campaign_id)).first()
    if not campaign:
        return 0

    count = 0
    for cc in contacts:
        contact = cc.contact
        company = contact.company
        draft = generate_initial_outreach(campaign, contact, company)
        cc.ai_draft = draft
        count += 1

    db.commit()
    logger.info(f"[OUTREACH AI] Generated {count} drafts for campaign {campaign_id}")
    return count
