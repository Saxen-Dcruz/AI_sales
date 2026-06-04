"""
LangGraph email processing workflow.

Replaces the nested if/else chain in email_router_service.py with an
explicit directed graph: each decision is a named node, each branch is a
named edge. State is checkpointed to PostgreSQL at every node so every
email's path is fully observable in LangSmith.

Entry point: run_email_workflow(db, raw_message) -> Optional[Email]
"""
import logging
from typing import Optional, TypedDict
from datetime import datetime
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.communication import Email

logger = logging.getLogger("rdl_app_logger")

# ── State schema ──────────────────────────────────────────────────────────────

class EmailWorkflowState(TypedDict, total=False):
    # Input
    raw_message: dict
    auto_send_enabled: bool

    # Parse stage
    duplicate: bool
    gmail_message_id: str
    gmail_thread_id: Optional[str]
    rfc_message_id: Optional[str]   # RFC 2822 Message-ID — used for In-Reply-To threading
    rfc_references: Optional[str]   # RFC 2822 References chain — for full thread header
    sender_raw: str
    sender_email: str
    subject: str
    body: str
    effective_body: str
    received_at: datetime
    recipients: list
    body_html: Optional[str]
    thread_context: Optional[str]

    # Classification
    label: str
    classifier_confidence: str
    classifier_reasoning: str
    transactional_type: Optional[str]
    transactional_data: Optional[dict]
    competitor_mention: Optional[str]

    # Persistence
    email_id: Optional[str]

    # Lead
    lead_id: Optional[str]
    is_new_lead: bool

    # Classification availability — True when the LLM was quota/cap-limited
    llm_unavailable: bool

    # Product detection
    product_id: Optional[str]
    product_name: Optional[str]
    product_confidence: str        # "high" | "low" | "none" | "unavailable"

    # RAG + draft
    rag_context: Optional[str]
    draft: Optional[str]
    gaps: list

    # Result
    action: str
    error: Optional[str]


# ── Checkpointer factory ───────────────────────────────────────────────────────

_checkpointer = None


def get_checkpointer():
    """Return a singleton PostgresSaver instance, creating tables on first call."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        import psycopg

        conn_str = (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
        # Open a persistent connection — stored at module level so it stays alive
        _conn = psycopg.connect(conn_str, autocommit=True)
        _checkpointer = PostgresSaver(_conn)
        _checkpointer.setup()
        logger.info("[EMAIL WORKFLOW] PostgreSQL checkpointer ready")
    except Exception as e:
        logger.warning(f"[EMAIL WORKFLOW] PostgreSQL checkpointer unavailable: {e} — running without checkpointing")
        _checkpointer = None

    return _checkpointer


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_email_graph():
    from app.services.workflows.email_nodes import (
        node_parse, node_fetch_thread_context, node_classify,
        node_persist, node_upsert_lead, node_detect_product,
        node_fetch_rag, node_generate_draft, node_extract_gaps,
        node_auto_send, node_hold_draft, node_send_clarification,
        node_flag_human, node_defer_human, node_archive, node_apply_gmail_label,
        node_update_lead_score, node_start_drip,
        node_try_schedule_meeting, node_commit,
        route_after_parse, route_after_classify,
        route_after_confidence, route_after_gaps,
    )

    g = StateGraph(EmailWorkflowState)

    # ── Add nodes ──
    g.add_node("parse", node_parse)
    g.add_node("fetch_thread_context", node_fetch_thread_context)
    g.add_node("classify", node_classify)
    g.add_node("persist", node_persist)

    # Sales branch
    g.add_node("upsert_lead", node_upsert_lead)
    g.add_node("detect_product", node_detect_product)
    g.add_node("fetch_rag", node_fetch_rag)
    g.add_node("generate_draft", node_generate_draft)
    g.add_node("extract_gaps", node_extract_gaps)
    g.add_node("auto_send", node_auto_send)
    g.add_node("hold_draft", node_hold_draft)
    g.add_node("send_clarification", node_send_clarification)
    g.add_node("try_schedule_meeting", node_try_schedule_meeting)
    g.add_node("update_lead_score", node_update_lead_score)
    g.add_node("start_drip", node_start_drip)

    # Support/Grievance branch
    g.add_node("flag_human", node_flag_human)
    g.add_node("defer_human", node_defer_human)

    # Archive branch
    g.add_node("archive", node_archive)

    # Shared finalization
    g.add_node("apply_gmail_label", node_apply_gmail_label)
    g.add_node("commit", node_commit)

    # ── Edges: common prefix ──
    g.add_edge(START, "parse")
    g.add_conditional_edges(
        "parse",
        route_after_parse,
        {"end_duplicate": END, "fetch_thread_context": "fetch_thread_context"},
    )
    g.add_edge("fetch_thread_context", "classify")
    g.add_conditional_edges(
        "classify",
        lambda s: "defer" if s.get("llm_unavailable") else "persist",
        {"defer": END, "persist": "persist"},
    )
    g.add_conditional_edges(
        "persist",
        lambda s: "end_duplicate" if s.get("duplicate") else route_after_classify(s),
        {
            "end_duplicate": END,
            "sales_branch": "upsert_lead",
            "support_branch": "flag_human",
            "archive_branch": "archive",
        },
    )

    # ── Sales branch ──
    g.add_edge("upsert_lead", "detect_product")
    g.add_conditional_edges(
        "detect_product",
        route_after_confidence,
        {
            "rag_branch": "fetch_rag",
            "clarification_branch": "send_clarification",
            "defer_human": "defer_human",
        },
    )

    # RAG → draft → gaps → decide
    g.add_edge("fetch_rag", "generate_draft")
    g.add_edge("generate_draft", "extract_gaps")
    g.add_conditional_edges(
        "extract_gaps",
        route_after_gaps,
        {"auto_send": "auto_send", "hold_draft": "hold_draft"},
    )

    # Both send outcomes → schedule check → score → drip → label → commit
    g.add_edge("auto_send", "try_schedule_meeting")
    g.add_edge("hold_draft", "try_schedule_meeting")
    g.add_edge("send_clarification", "try_schedule_meeting")
    g.add_edge("try_schedule_meeting", "update_lead_score")
    g.add_edge("update_lead_score", "start_drip")
    g.add_edge("start_drip", "apply_gmail_label")

    # ── Support/Grievance branch ──
    g.add_edge("flag_human", "apply_gmail_label")
    g.add_edge("defer_human", "commit")

    # ── Archive branch ──
    g.add_edge("archive", "apply_gmail_label")

    # ── Finalize ──
    g.add_edge("apply_gmail_label", "commit")
    g.add_edge("commit", END)

    checkpointer = get_checkpointer()
    return g.compile(checkpointer=checkpointer)


# Singleton compiled graph
_email_graph = None


def _get_graph():
    global _email_graph
    if _email_graph is None:
        _email_graph = build_email_graph()
    return _email_graph


# ── Public entry points ───────────────────────────────────────────────────────

def run_email_workflow(
    db: Session,
    raw_message: dict,
    account_id: Optional[str] = None,
    account_email: Optional[str] = None,
) -> Optional[Email]:
    """
    Process one inbound Gmail message through the LangGraph workflow.
    account_id / account_email: which EmailAccount this message came from.
    Returns the persisted Email row, or None if skipped (duplicate/untracked label).
    """
    from app.services import gmail_service as gs

    # Use account-specific service when account is provided
    auto_send_enabled = True
    if account_id:
        from app.services.email_account_service import get_account
        account = get_account(db, UUID(account_id))
        gmail_svc = gs.get_gmail_service(account=account) if account else gs.get_gmail_service()
        if account:
            auto_send_enabled = account.auto_send_enabled
    else:
        gmail_svc = gs.get_gmail_service()

    graph = _get_graph()

    parsed_id = raw_message.get("id", "unknown")
    config: RunnableConfig = {
        "configurable": {
            "thread_id": f"email_{parsed_id}",
            "db": db,
            "gmail_svc": gmail_svc,
            "account_id": account_id,
            "account_email": account_email,
        }
    }

    try:
        final_state = graph.invoke(
            {"raw_message": raw_message, "auto_send_enabled": auto_send_enabled},
            config=config,
        )
    except Exception as e:
        logger.error(f"[EMAIL WORKFLOW] Graph invocation failed for {parsed_id}: {e}", exc_info=True)
        return None

    email_id = final_state.get("email_id")
    if not email_id:
        return None

    try:
        return db.query(Email).filter(Email.id == UUID(email_id)).first()
    except Exception:
        return None


def resume_after_gaps_resolved(db: Session, email_id: str) -> bool:
    """
    Called when the last knowledge gap is resolved.

    Flow:
    1. Re-run RAG with the original email body (KB now contains the gap answers)
    2. Generate a brand-new complete draft with no "will confirm" placeholders
    3. Delete the old stale Gmail draft; save the new one
    4. Extract gaps from the new draft (should be zero now)
    5. If no new gaps → set status=draft_ready (human reviews then approves)
       Auto-send is NOT triggered here — user must explicitly approve the regenerated draft.

    Returns True when the new draft is saved successfully.
    """
    from app.models.communication import EmailStatus
    from app.services import gmail_service as gs
    from app.services.email_account_service import get_account
    from app.services.workflows.email_nodes import (
        fetch_rag_context, generate_sales_draft,
    )
    from app.services.sales_gap_service import extract_structured_gaps

    email = db.query(Email).filter(Email.id == UUID(email_id)).first()
    if not email:
        logger.warning(f"[EMAIL WORKFLOW] Resume: email {email_id} not found")
        return False

    gaps = email.followup_gaps or []
    if any(not g.get("resolved") for g in gaps):
        return False  # still unresolved gaps

    # Nothing to regenerate if there was never a draft to begin with
    if not email.gmail_draft_id:
        logger.warning(f"[EMAIL WORKFLOW] Resume: no draft_id on email {email_id} — skipping")
        return False

    # ── Get the Gmail service for this account ────────────────────────────────
    if email.account_id:
        acct = get_account(db, email.account_id)
        gmail_svc = gs.get_gmail_service(account=acct) if acct else gs.get_gmail_service()
    else:
        gmail_svc = gs.get_gmail_service()

    old_draft_id = email.gmail_draft_id  # keep a reference so we can fall back on failure

    try:
        # ── Re-run RAG with the original email body ───────────────────────────
        # Do this BEFORE touching Gmail so a spend-cap / LLM failure leaves the
        # original draft intact and the user can still approve manually.
        rag_context = fetch_rag_context(email.body_text or "") or ""
        logger.info(
            f"[EMAIL WORKFLOW] Resume: re-ran RAG for email {email_id} — "
            f"{len(rag_context)} chars of context"
        )

        # ── Generate new complete draft ───────────────────────────────────────
        new_draft_text = generate_sales_draft(
            sender=email.sender or "",
            subject=email.subject or "",
            body=email.body_text or "",
            rag_context=rag_context,
        )

        if not new_draft_text or not new_draft_text.strip():
            logger.warning(f"[EMAIL WORKFLOW] Resume: empty draft for {email_id} — keeping original draft")
            return False

        # ── Save the NEW Gmail draft first, THEN delete the old one ──────────
        # Reversing the order prevents losing the draft if save fails mid-way.
        reply_subject = (
            email.subject if (email.subject or "").startswith("Re:")
            else f"Re: {email.subject}"
        )
        sender_addr = gs.extract_email_address(email.sender or "")
        new_gmail_draft = gs.create_draft(
            gmail_svc,
            to=sender_addr,
            subject=reply_subject,
            body=new_draft_text,
            thread_id=email.gmail_thread_id,
        )

        # New draft saved → now safe to remove the old one
        if old_draft_id:
            try:
                gmail_svc.users().drafts().delete(
                    userId="me", id=old_draft_id
                ).execute()
            except Exception:
                pass  # already deleted or not found — not fatal

        # ── Check if any new gaps remain in the regenerated draft ─────────────
        new_gaps = extract_structured_gaps(
            customer_text=email.body_text or "",
            ai_response=new_draft_text,
            product_name=None,
            product_id=None,
            db=db,
        )

        email.ai_draft = new_draft_text
        email.gmail_draft_id = new_gmail_draft["id"]
        email.followup_gaps = new_gaps or []
        email.needs_human = bool(new_gaps)
        email.status = EmailStatus.DRAFT_READY
        db.commit()

        if new_gaps:
            logger.info(
                f"[EMAIL WORKFLOW] Resume: regenerated draft still has {len(new_gaps)} gaps "
                f"for email {email_id} — held for review"
            )
        else:
            logger.info(
                f"[EMAIL WORKFLOW] Resume: complete draft ready for {email_id} "
                f"— held for human approval"
            )
        return True

    except Exception as e:
        logger.error(f"[EMAIL WORKFLOW] Resume regeneration failed for {email_id}: {e}", exc_info=True)
        # DO NOT rollback — the gap.resolved flag was committed by the router
        # before calling us, and we must not lose that. The original draft_id
        # is still valid (we only delete after a successful new save), so the
        # user can still approve the old draft manually.
        return False
