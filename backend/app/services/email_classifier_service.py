import json
import logging
import re
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.core.config import settings
from app.models.communication import EmailLabel

logger = logging.getLogger("rdl_app_logger")

_SYSTEM_PROMPT = """You are an email classification assistant for RDL Technologies, a B2B electronics company.

Classify the incoming email into EXACTLY ONE of these labels and also detect competitor mentions.

- Sales: Inquiry about products, pricing, availability, purchase intent, RFQ, quotation request, partnership/reseller inquiry, demo request, OR any question about product specifications, features, technical parameters, memory, compatibility, or capabilities from someone who does NOT already own the product. When in doubt between Sales and Support, choose Sales.
- Support: Technical help, troubleshooting, or how-to questions ONLY from customers who clearly already own the product — look for phrases like "my device", "I purchased", "I own a", "not working", "stopped working", "error", "my unit". A plain spec question with no ownership context is Sales, not Support.
- Grievance: Complaints, dissatisfaction, escalations, returns, refund requests, threats of escalation, negative feedback
- Transactional: Invoices, receipts, order confirmations, shipping notifications, payment confirmations, account alerts, subscription renewals
- Promotional: Newsletters, marketing emails, advertisements, offers from other companies, event invitations
- Personal: Greetings, congratulations, wishes, informal messages with no business intent

REPLY HANDLING: If "ORIGINAL THREAD" context is provided, the incoming message is a reply in an ongoing conversation. Classify it based on the ORIGINAL thread's topic and intent — not just the reply text alone. A short confirmation reply ("ok", ".", "thanks", "sure") to a Sales inquiry is still Sales, not Personal.

AUTOMATED SENDER RULES — classify immediately without deviation:
- Sender contains "calendar-notification@google.com" → Transactional
- Sender contains "drive-shares-dm-noreply@google.com" → Transactional
- Sender contains "mailer-daemon@" → Transactional
- Sender contains "CloudPlatform-noreply@google.com" → Transactional
- Sender contains "no-reply@" or "noreply@" and body contains invoice/order/receipt keywords → Transactional
- Subject starts with "Notification:" and sender is Google Calendar → Transactional

For Transactional emails also identify the transactional_type:
- invoice, receipt, order_confirmation, shipping, payment, account, other

Respond ONLY with valid JSON in this exact format:
{
  "label": "<one of the labels above>",
  "confidence": "<high|medium|low>",
  "reasoning": "<one short sentence — your own words only, NO email content or quotes>",
  "transactional_type": "<only if label is Transactional, else null>",
  "transactional_data": {
    "amount": "<if present>",
    "reference_number": "<invoice/order/ref number if present>",
    "due_date": "<if present>",
    "vendor": "<sender company name if present>"
  },
  "competitor_mention": "<name of competitor brand or product if mentioned, else null>"
}

IMPORTANT: The reasoning field must be a plain sentence you write yourself. Never copy email subject text, body text, or any quoted content into the JSON — it will break JSON parsing."""


def _build_llm() -> ChatGoogleGenerativeAI:
    from google.api_core.exceptions import PermissionDenied, ResourceExhausted
    base_kwargs = dict(temperature=0.1, max_output_tokens=512, max_retries=0)
    primary_kwargs = {**base_kwargs, **({"google_api_key": settings.GOOGLE_API_KEY} if settings.GOOGLE_API_KEY else {})}
    primary = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", **primary_kwargs)
    # Fallback uses ADC (no api_key) — handles both quota exhaustion and blocked/invalid keys
    fallback = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", **base_kwargs)
    return primary.with_fallbacks([fallback], exceptions_to_handle=(ResourceExhausted, PermissionDenied))


@traceable(run_type="chain", name="classify_email")
def classify_email(
    subject: str,
    body: str,
    sender: str,
    thread_context: Optional[str] = None,
) -> dict:
    """
    Classify an email using Gemini. Returns dict with label, confidence, reasoning,
    transactional_type, transactional_data.
    Falls back to Unclassified on any error.
    thread_context: body of the original message in the thread (for reply emails).
    """
    safe_subject = subject.replace('"', "'")

    if thread_context:
        user_content = f"""From: {sender}
Subject: {safe_subject}

--- ORIGINAL THREAD ---
{thread_context[:1500]}

--- NEW REPLY ---
{body[:1500]}"""
    else:
        user_content = f"""From: {sender}
Subject: {safe_subject}

Body:
{body[:3000]}"""

    try:
        llm = _build_llm()
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ])
        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        # Extract first JSON object — handles trailing text after closing brace
        brace_start = raw.find("{")
        brace_end = raw.rfind("}")
        if brace_start != -1 and brace_end != -1:
            raw = raw[brace_start:brace_end + 1]
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: extract label and confidence via regex when JSON is malformed
            # (happens when Gemini embeds unescaped email content in reasoning)
            label_match = re.search(r'"label"\s*:\s*"([^"]+)"', raw)
            confidence_match = re.search(r'"confidence"\s*:\s*"([^"]+)"', raw)
            if not label_match:
                raise
            result = {
                "label": label_match.group(1),
                "confidence": confidence_match.group(1) if confidence_match else "low",
                "reasoning": "",
                "transactional_type": None,
                "transactional_data": None,
            }

        label_str = result.get("label", "Unclassified")
        try:
            label = EmailLabel(label_str)
        except ValueError:
            label = EmailLabel.UNCLASSIFIED

        return {
            "label": label,
            "confidence": result.get("confidence", "low"),
            "reasoning": result.get("reasoning", ""),
            "transactional_type": result.get("transactional_type"),
            "transactional_data": result.get("transactional_data"),
            "competitor_mention": result.get("competitor_mention"),
        }

    except Exception as e:
        logger.error(f"Email classification failed for subject='{subject}': {e}")
        return {
            "label": EmailLabel.UNCLASSIFIED,
            "confidence": "low",
            "reasoning": f"Classification error: {e}",
            "transactional_type": None,
            "transactional_data": None,
            "competitor_mention": None,
            "llm_unavailable": _is_llm_cap_error(e),
        }


def _is_llm_cap_error(exc: Exception) -> bool:
    """True if the failure is a transient quota/spend-cap/rate-limit error.

    These should defer the email for retry rather than mark it Unclassified —
    the content is fine, the model is just temporarily unavailable.
    """
    msg = str(exc).lower()
    markers = ("spend cap", "spending cap", "resource_exhausted", "resourceexhausted",
               "quota", "rate limit", "rate_limit", "429", "exceeded")
    return any(m in msg for m in markers)
