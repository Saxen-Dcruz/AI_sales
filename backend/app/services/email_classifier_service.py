import json
import logging
import re
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings
from app.models.communication import EmailLabel

logger = logging.getLogger("rdl_app_logger")

_SYSTEM_PROMPT = """You are an email classification assistant for RDL Technologies, a B2B electronics company.

Classify the incoming email into EXACTLY ONE of these labels:

- Sales: Inquiry about products, pricing, availability, purchase intent, RFQ, quotation request, partnership/reseller inquiry, demo request
- Support: Technical help, troubleshooting, how-to questions, product usage issues from existing customers
- Grievance: Complaints, dissatisfaction, escalations, returns, refund requests, threats of escalation, negative feedback
- Transactional: Invoices, receipts, order confirmations, shipping notifications, payment confirmations, account alerts, subscription renewals
- Promotional: Newsletters, marketing emails, advertisements, offers from other companies, event invitations
- Personal: Greetings, congratulations, wishes, informal messages with no business intent

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
  }
}

IMPORTANT: The reasoning field must be a plain sentence you write yourself. Never copy email subject text, body text, or any quoted content into the JSON — it will break JSON parsing."""


def _build_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="models/gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.1,
        max_output_tokens=512,
    )


def classify_email(
    subject: str,
    body: str,
    sender: str,
) -> dict:
    """
    Classify an email using Gemini. Returns dict with label, confidence, reasoning,
    transactional_type, transactional_data.
    Falls back to Unclassified on any error.
    """
    # Sanitize subject — remove double quotes that break Gemini's JSON output
    safe_subject = subject.replace('"', "'")
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
        }

    except Exception as e:
        logger.error(f"Email classification failed for subject='{subject}': {e}")
        return {
            "label": EmailLabel.UNCLASSIFIED,
            "confidence": "low",
            "reasoning": f"Classification error: {e}",
            "transactional_type": None,
            "transactional_data": None,
        }
