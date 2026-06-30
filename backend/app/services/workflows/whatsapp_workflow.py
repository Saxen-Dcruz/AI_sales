"""
LangGraph WhatsApp processing workflow.

Mirrors the email workflow structure but uses WhatsApp-specific nodes
for send/persist operations. Reuses the same classifier + RAG + gap pipeline.

Entry point: run_whatsapp_workflow(db, raw_message, account) -> Optional[WhatsAppMessage]
"""
import logging
from typing import Optional
from typing import TypedDict
from datetime import datetime

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.models.whatsapp_account import WhatsAppAccount
from app.models.whatsapp_message import WhatsAppMessage

logger = logging.getLogger("rdl_app_logger")


# ── State schema ───────────────────────────────────────────────────────────────

class WAWorkflowState(TypedDict, total=False):
    raw_message:          dict
    auto_send:            bool

    # parse
    duplicate:            bool
    wa_message_id:        str
    from_number:          str
    to_number:            str
    body:                 str
    effective_body:       str
    media_url:            Optional[str]
    received_at:          datetime
    message_type:         str
    # Phase 2C: interactive reply fields
    button_reply_id:      Optional[str]
    button_reply_title:   Optional[str]
    list_reply_id:        Optional[str]
    list_reply_title:     Optional[str]
    is_interactive:       bool
    interactive_handled:  bool

    # classify
    label:                str
    classifier_confidence: str
    classifier_reasoning:  str
    competitor_mention:    Optional[str]
    llm_unavailable:       bool

    # persist
    message_id:            Optional[str]

    # lead
    lead_id:               Optional[str]
    is_new_lead:           bool

    # product
    product_id:            Optional[str]
    product_name:          Optional[str]
    product_confidence:    str

    # rag + draft
    rag_context:           Optional[str]
    draft:                 Optional[str]
    gaps:                  list

    # result
    action:                str
    error:                 Optional[str]


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_whatsapp_graph():
    from app.services.workflows.whatsapp_nodes import (
        node_parse, node_classify, node_persist,
        node_upsert_lead, node_detect_product,
        node_fetch_rag, node_generate_draft, node_extract_gaps,
        node_auto_send, node_hold_draft, node_send_clarification,
        node_flag_human, node_archive,
        node_update_lead_score, node_commit,
        # Phase 2C + 4
        node_handle_interactive_reply,
        node_send_qualification_buttons,
        route_after_parse, route_after_classify,
        route_after_confidence,
    )

    def route_gaps(state: dict) -> str:
        if state.get("auto_send") and not state.get("gaps"):
            return "auto_send"
        return "hold_draft"

    g = StateGraph(WAWorkflowState)

    g.add_node("parse",                    node_parse)
    g.add_node("handle_interactive",       node_handle_interactive_reply)   # Phase 2C
    g.add_node("classify",                 node_classify)
    g.add_node("persist",                  node_persist)
    g.add_node("upsert_lead",              node_upsert_lead)
    g.add_node("detect_product",           node_detect_product)
    g.add_node("fetch_rag",                node_fetch_rag)
    g.add_node("generate_draft",           node_generate_draft)
    g.add_node("extract_gaps",             node_extract_gaps)
    g.add_node("auto_send",                node_auto_send)
    g.add_node("qualification_buttons",    node_send_qualification_buttons) # Phase 4
    g.add_node("hold_draft",               node_hold_draft)
    g.add_node("send_clarification",       node_send_clarification)
    g.add_node("flag_human",               node_flag_human)
    g.add_node("archive",                  node_archive)
    g.add_node("update_lead_score",        node_update_lead_score)
    g.add_node("commit",                   node_commit)

    # Start
    g.add_edge(START, "parse")
    g.add_conditional_edges("parse", route_after_parse, {
        "end_duplicate":    END,
        "handle_interactive": "handle_interactive",   # Phase 2C
        "classify":         "classify",
    })

    # Phase 2C: interactive reply either handled (→ END) or falls through to classify
    g.add_conditional_edges("handle_interactive",
        lambda s: "end_handled" if s.get("interactive_handled") else "classify",
        {"end_handled": END, "classify": "classify"},
    )

    g.add_conditional_edges("classify",
        lambda s: "defer" if s.get("llm_unavailable") else "persist",
        {"defer": END, "persist": "persist"},
    )
    g.add_conditional_edges("persist", route_after_classify, {
        "sales_branch":   "upsert_lead",
        "support_branch": "flag_human",
        "archive_branch": "archive",
    })

    # Support / Grievance
    g.add_edge("flag_human", "commit")
    g.add_edge("archive", "commit")

    # Sales branch
    g.add_edge("upsert_lead", "detect_product")
    g.add_conditional_edges("detect_product", route_after_confidence, {
        "high":  "fetch_rag",
        "low":   "send_clarification",
        "defer": "hold_draft",
    })
    g.add_edge("send_clarification", "update_lead_score")
    g.add_edge("fetch_rag", "generate_draft")
    g.add_edge("generate_draft", "extract_gaps")
    g.add_conditional_edges("extract_gaps", route_gaps, {
        "auto_send":  "auto_send",
        "hold_draft": "hold_draft",
    })
    # Phase 4: after auto_send, optionally send qualification buttons
    g.add_edge("auto_send",            "qualification_buttons")
    g.add_edge("qualification_buttons","update_lead_score")
    g.add_edge("hold_draft",           "update_lead_score")
    g.add_edge("update_lead_score",    "commit")
    g.add_edge("commit", END)

    return g.compile()


_wa_graph = None


def get_wa_graph():
    global _wa_graph
    if _wa_graph is None:
        _wa_graph = build_whatsapp_graph()
    return _wa_graph


# ── Entry point ────────────────────────────────────────────────────────────────

def run_whatsapp_workflow(
    db: Session,
    raw_message: dict,
    account: Optional[WhatsAppAccount] = None,
) -> Optional[WhatsAppMessage]:
    """
    Process an inbound WhatsApp message through the full AI pipeline.
    Returns the persisted WhatsAppMessage row or None for duplicates/failures.
    """
    graph = get_wa_graph()

    auto_send = account.auto_send if account else False

    initial_state: WAWorkflowState = {
        "raw_message": raw_message,
        "auto_send":   auto_send,
        "gaps":        [],
        "action":      "",
    }

    config = {
        "configurable": {
            "db":      db,
            "account": account,
        }
    }

    try:
        final = graph.invoke(initial_state, config)
    except Exception as e:
        logger.error(f"[WA WORKFLOW] uncaught error: {e}", exc_info=True)
        db.rollback()
        return None

    if final.get("duplicate"):
        return None

    msg_id = final.get("message_id")
    if not msg_id:
        return None

    from uuid import UUID
    return db.query(WhatsAppMessage).filter(
        WhatsAppMessage.id == UUID(msg_id)
    ).first()
