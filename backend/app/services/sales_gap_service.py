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
    """Pull list items or question sentences from text.

    Handles:
    - Numbered lists starting at BOL (1. / 1))
    - Bullet-point lists (- / *)
    - Fallback: sentence-split on ?
    """
    # Numbered list — must start at beginning of a line (MULTILINE so ^ matches BOL too)
    items = re.split(r"^\s*\d+[.)]\s+", text, flags=re.MULTILINE)
    if len(items) > 1:
        return [i.strip() for i in items[1:] if i.strip()]
    # Bullet-point list
    items = re.split(r"^\s*[-*]\s+", text, flags=re.MULTILINE)
    if len(items) > 1:
        return [i.strip() for i in items[1:] if i.strip()]
    # Fallback: split on sentence-ending question marks
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
        # Fallback: check if any follow-up exists in the AI response.
        # The question is the customer's original text (subject or body), NOT the draft sentence.
        has_followup = any(
            marker in ai_response.lower() for marker in _FOLLOWUP_MARKERS
        )
        if has_followup and customer_text.strip():
            # Use the customer's actual text (subject or body) as the question
            question = customer_text.strip()[:600]
            gaps.append({
                "question": question,
                "topic": infer_topic(question),
                "product_name": product_name,
                "product_id": product_id,
                "resolved": False,
                "answer": None,
                "resolved_by": None,
            })

    return gaps


# ── Product detection ─────────────────────────────────────────────────────────

_STOP_WORDS = {
    "and", "or", "the", "for", "with", "of", "in", "a", "an", "to", "at",
    "is", "are", "its", "by", "from", "this", "that", "how", "what", "much",
    "will", "can", "does", "do", "be", "has", "have", "get", "i", "we",
    # common 2-char words that are not product identifiers
    "it", "on", "up", "so", "as", "us", "me", "my", "no", "if", "ok",
}


def _product_keywords(name: str) -> list[str]:
    """
    Extract meaningful tokens from a product name or query text.
    Minimum length is 2 so short but meaningful identifiers like '4g', 'ai',
    'dc', 'ac' are kept. Common stop words are excluded.
    """
    return [
        w for w in re.split(r"\W+", name.lower())
        if len(w) >= 2 and w not in _STOP_WORDS
    ]


def _llm_identify_product(
    text: str, products: list
) -> tuple[Optional[str], Optional[str]]:
    """
    Last-resort fallback: ask Gemini which product from the catalog the customer is
    most likely asking about. Only called when keyword matching also fails.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.core.config import settings

        catalog_lines = "\n".join(
            f"- {p.name} (Order Code: {p.order_code or 'N/A'})"
            for p in products[:60]
        )
        from google.api_core.exceptions import PermissionDenied, ResourceExhausted
        _base = dict(temperature=0, max_output_tokens=80, max_retries=0)
        primary = ChatGoogleGenerativeAI(
            model="models/gemini-2.5-flash",
            **({"google_api_key": settings.GOOGLE_API_KEY} if settings.GOOGLE_API_KEY else {}),
            **_base,
        )
        fallback = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", **_base)
        llm = primary.with_fallbacks([fallback], exceptions_to_handle=(ResourceExhausted, PermissionDenied))
        response = llm.invoke([
            SystemMessage(content=(
                "You are a product identification assistant for RDL Technologies. "
                "Given a customer query and a product catalog, return ONLY the exact product name "
                "from the catalog that is the PRIMARY subject of the customer's inquiry. "
                "The product must be explicitly named or its order code must appear — "
                "do NOT match a product just because its interface type (RS232, USB, etc.) appears as a comparison. "
                "If the customer is asking about multiple different products, return the first one mentioned. "
                "If no product is clearly the subject, respond with exactly: NONE"
            )),
            HumanMessage(content=(
                f"Customer query: {text[:600]}\n\nProduct catalog:\n{catalog_lines}"
            )),
        ])
        matched_name = response.content.strip().strip('"').strip("'")
        if matched_name.upper() == "NONE":
            return None, None
        for p in products:
            if p.name.lower() == matched_name.lower():
                logger.info(f"[PRODUCT DETECT] LLM identified: {p.name!r}")
                return str(p.id), p.name
    except Exception as e:
        logger.warning(f"[PRODUCT DETECT] LLM identification failed: {e}")
    return None, None


def detect_product(
    db: Session, text: str
) -> tuple[Optional[str], Optional[str], str]:
    """
    Three-phase product detection. Returns (product_id, product_name, confidence).

    confidence values:
      "high"   — Phase 1 exact phrase / order-code match. Safe to auto-draft.
      "low"    — Phase 2 keyword overlap OR Phase 3 LLM. Uncertain — ask customer to confirm.
      "none"   — No match found at all. Ask customer to specify the product.

    The caller decides what to do based on confidence:
      high → run RAG and send/hold draft
      low  → send a clarification email with similar product links
      none → send a clarification email asking the customer to name the product
    """
    from app.models.product import Product
    products = db.query(Product).filter(Product.is_active == True).all()
    text_lower = text.lower()
    # Strip markdown/punctuation for cleaner Phase 1 matching
    text_clean = re.sub(r"[^a-z0-9 ]", " ", text_lower)

    # ── Phase 1: exact phrase / order-code match (HIGH confidence) ───────────
    # Check multiple matches — if >1 distinct product names match, return the
    # first but flag as multi-product so the caller can widen the RAG filter.
    phase1_matches = []
    for p in sorted(products, key=lambda x: -len(x.name)):
        if len(p.name) < 4:
            continue
        name_clean = re.sub(r"[^a-z0-9 ]", " ", p.name.lower())
        # Order code must have ≥3 alphanumeric chars to be valid for matching
        # (guards against placeholder values like "-" matching bullet points)
        code_alphanum = re.sub(r"[^a-z0-9]", "", (p.order_code or "").lower())
        code_match = len(code_alphanum) >= 3 and code_alphanum in text_clean
        if name_clean in text_clean or p.name.lower() in text_lower or code_match:
            phase1_matches.append(p)

    if phase1_matches:
        # Deduplicate by name (RDL838 and RDL891 share the same name)
        seen_names: set[str] = set()
        unique = []
        for p in phase1_matches:
            if p.name not in seen_names:
                seen_names.add(p.name)
                unique.append(p)

        if len(unique) == 1:
            logger.info(f"[PRODUCT DETECT] Exact match: {unique[0].name!r}")
            return str(unique[0].id), unique[0].name, "high"

        # Multiple distinct products — return first but log the ambiguity
        names = [p.name for p in unique]
        logger.info(f"[PRODUCT DETECT] Multi-product match: {names} — returning first")
        return str(unique[0].id), unique[0].name, "high"

    # ── Phase 2: keyword overlap (LOW confidence) ─────────────────────────────
    best: tuple[float, Optional[object]] = (0.0, None)
    text_kw_set = set(_product_keywords(text))
    for p in products:
        if len(p.name) < 4:
            continue
        prod_kw_set = set(_product_keywords(p.name))
        if not prod_kw_set:
            continue
        matched = len(prod_kw_set & text_kw_set)
        coverage = matched / len(prod_kw_set)
        if matched >= 2 and coverage >= 0.3 and coverage > best[0]:
            best = (coverage, p)

    if best[1]:
        p = best[1]
        logger.info(f"[PRODUCT DETECT] Keyword match ({best[0]:.0%}, LOW confidence): {p.name!r}")
        return str(p.id), p.name, "low"

    # ── Phase 3: LLM fallback (LOW confidence) ───────────────────────────────
    logger.info("[PRODUCT DETECT] No phrase/keyword match — trying LLM identification")
    pid, pname = _llm_identify_product(text, products)
    if pid:
        return pid, pname, "low"

    return None, None, "none"


def find_similar_products(db: Session, text: str, limit: int = 4) -> list[dict]:
    """
    Return up to `limit` products whose keywords best overlap with the query text.
    Each entry has: id, name, product_link, order_code, category.
    Used to build the clarification email when product confidence is low or none.
    """
    from app.models.product import Product
    products = db.query(Product).filter(Product.is_active == True).all()
    text_kw_set = set(_product_keywords(text))

    scored: list[tuple[float, object]] = []
    for p in products:
        if len(p.name) < 4:
            continue
        prod_kw_set = set(_product_keywords(p.name))
        if not prod_kw_set:
            continue
        matched = len(prod_kw_set & text_kw_set)
        if matched > 0:
            scored.append((matched / len(prod_kw_set), p))

    scored.sort(key=lambda x: -x[0])
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "order_code": p.order_code,
            "category": p.category,
            "product_link": getattr(p, "product_link", None),
        }
        for _, p in scored[:limit]
    ]


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
