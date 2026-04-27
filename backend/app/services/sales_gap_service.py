"""
Channel-agnostic sales intelligence helpers.

Used by both the email pipeline (email_router_service.py) and the call pipeline
(call_service.py, when built). Nothing in here should import from Gmail, Calendar,
or any channel-specific module.
"""
import contextvars
import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger("rdl_app_logger")

# ── Response sanitisation ─────────────────────────────────────────────────────

_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


def sanitize_ai_response(text: str) -> str:
    """Replace any [PLACEHOLDER] brackets the LLM emitted with natural follow-up language."""
    brackets = _BRACKET_RE.findall(text)
    if brackets:
        logger.warning(f"[SALES GAP] LLM emitted {len(brackets)} bracket(s): {brackets} — sanitizing")
        text = _BRACKET_RE.sub("our team will confirm this and follow up with you shortly", text)
    return text


# ── Topic inference ───────────────────────────────────────────────────────────

_FOLLOWUP_MARKERS = [
    "will confirm", "will follow up", "will get back", "will share",
    "will provide", "will send", "our team will", "follow up with",
    "will be in touch", "reach out with", "will verify", "will check",
]

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "warranty":      ["warranty", "guarantee", "after-sales", "support period", "repair"],
    "pricing":       ["price", "pricing", "cost", "bulk", "discount", "oem", "quote", "rate"],
    "compatibility": ["compatible", "compatibility", "interface", "arduino", "esp32", "raspberry", "board", "platform"],
    "availability":  ["lead time", "availability", "delivery", "stock", "timeline", "ship"],
    "technical":     ["datasheet", "manual", "documentation", "spec", "technical", "accuracy", "isolation", "rating", "range"],
}


def infer_topic(text: str) -> str:
    """Classify text into a product knowledge category."""
    text_lower = text.lower()
    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return topic
    return "general"


# ── Structured gap extraction ─────────────────────────────────────────────────

def _extract_numbered_items(text: str) -> list[str]:
    """Pull numbered-list items (1. ... 2. ...) or question sentences from text."""
    items = re.split(r"\n\s*\d+[.)]\s+", text)
    if len(items) > 1:
        return [i.strip() for i in items[1:] if i.strip()]
    return [s.strip() for s in re.split(r"(?<=[?])\s+", text) if "?" in s and len(s.strip()) > 15]


def extract_structured_gaps(
    customer_text: str,
    ai_response: str,
    product_name: Optional[str],
    product_id: Optional[str],
) -> list[dict]:
    """
    Map each follow-up sentence in the AI response back to the customer's original
    question using positional matching, infer the knowledge category, and return
    structured gap dicts ready for the dashboard fill-in form.

    Works for any channel — pass email body or call transcript as customer_text,
    and email draft or call script as ai_response.
    """
    customer_items = _extract_numbered_items(customer_text)
    response_items = _extract_numbered_items(ai_response)
    gaps: list[dict] = []

    if customer_items and response_items:
        for q, a in zip(customer_items, response_items):
            if any(marker in a.lower() for marker in _FOLLOWUP_MARKERS):
                gaps.append({
                    "question": q.strip(),
                    "topic": infer_topic(q),
                    "product_name": product_name,
                    "product_id": product_id,
                    "resolved": False,
                    "answer": None,
                    "resolved_by": None,
                })
    else:
        # Fallback: scan follow-up sentences in the AI response directly
        for s in re.split(r"(?<=[.!?])\s+", ai_response):
            if s.strip() and any(marker in s.lower() for marker in _FOLLOWUP_MARKERS):
                gaps.append({
                    "question": s.strip(),
                    "topic": infer_topic(s),
                    "product_name": product_name,
                    "product_id": product_id,
                    "resolved": False,
                    "answer": None,
                    "resolved_by": None,
                })

    return gaps


# ── Product detection ─────────────────────────────────────────────────────────

def detect_product(db: Session, text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Return (product_id_str, product_name) for the first product name or order code
    found in text. Longest-name-first matching avoids partial substring false positives.
    """
    from app.models.product import Product
    products = db.query(Product).filter(Product.is_active == True).all()
    text_lower = text.lower()
    for p in sorted(products, key=lambda x: -len(x.name)):
        if p.name.lower() in text_lower or (p.order_code and p.order_code.lower() in text_lower):
            return str(p.id), p.name
    return None, None


# ── RAG context fetch (shared across channels) ────────────────────────────────

def fetch_rag_context(customer_text: str) -> str:
    """
    Run the RAG pipeline for a customer query and return the raw retrieved document
    chunks joined as a single string. Runs in an isolated thread to avoid gRPC
    channel corruption from concurrent LangChain calls.
    """
    import asyncio
    import uuid
    import concurrent.futures
    from app.agents.tools.rag_chain import RAGManager

    async def _query():
        question = customer_text[:1500] + "\n\nPlease include complete specifications and product details."
        # fetch_contexts_only skips the RAG answer LLM (~23s saved) — we only need
        # the raw retrieved chunks; the draft/call LLM does its own generation.
        return await RAGManager().fetch_contexts_only(question)

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_query())
        finally:
            loop.close()

    try:
        ctx = contextvars.copy_context()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(ctx.run, _run).result(timeout=90)
    except Exception as e:
        logger.error(f"[SALES GAP] RAG fetch failed: {e}", exc_info=True)
        return ""
