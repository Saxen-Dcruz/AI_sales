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

    # Parse stage
    duplicate: bool
    gmail_message_id: str
    gmail_thread_id: Optional[str]
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

    # Product detection
    product_id: Optional[str]
    product_name: Optional[str]
    product_confidence: str        # "high" | "low" | "none"

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
        node_flag_human, node_archive, node_apply_gmail_label,
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
    g.add_edge("classify", "persist")
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
        {"rag_branch": "fetch_rag", "clarification_branch": "send_clarification"},
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

def run_email_workflow(db: Session, raw_message: dict) -> Optional[Email]:
    """
    Process one inbound Gmail message through the LangGraph workflow.
    Returns the persisted Email row, or None if skipped (duplicate/untracked label).
    """
    from app.services import gmail_service as gs

    gmail_svc = gs.get_gmail_service()
    graph = _get_graph()

    # thread_id = gmail_message_id scopes the checkpoint to this specific email
    # so we can resume it later (e.g. after gap fill)
    parsed_id = raw_message.get("id", "unknown")
    config: RunnableConfig = {
        "configurable": {
            "thread_id": f"email_{parsed_id}",
            "db": db,
            "gmail_svc": gmail_svc,
        }
    }

    try:
        final_state = graph.invoke({"raw_message": raw_message}, config=config)
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
    Resume the workflow for an email after all its gaps have been filled.
    Called by the gap-resolve endpoint once all gaps are resolved.
    Re-evaluates the draft and auto-sends if no more gaps remain.
    Returns True if the email was successfully sent.
    """
    email = db.query(Email).filter(Email.id == UUID(email_id)).first()
    if not email:
        logger.warning(f"[EMAIL WORKFLOW] Resume: email {email_id} not found")
        return False

    gaps = email.followup_gaps or []
    if any(not g.get("resolved") for g in gaps):
        # Still unresolved gaps — do nothing
        return False

    if not email.gmail_draft_id:
        logger.warning(f"[EMAIL WORKFLOW] Resume: no draft_id on email {email_id}")
        return False

    try:
        from app.services import gmail_service as gs
        gmail_svc = gs.get_gmail_service()
        gs.send_draft(gmail_svc, email.gmail_draft_id)
        email.gmail_draft_id = None
        email.needs_human = False
        from app.models.communication import EmailStatus
        email.status = EmailStatus.REPLIED
        db.commit()
        logger.info(f"[EMAIL WORKFLOW] All gaps resolved — auto-sent draft for email {email_id}")
        return True
    except Exception as e:
        logger.error(f"[EMAIL WORKFLOW] Resume send failed for {email_id}: {e}")
        db.rollback()
        return False
