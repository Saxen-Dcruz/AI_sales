"""
Transaction Deal Service

When an inbound email or WhatsApp message is classified as Transactional
with type 'invoice', 'order', 'purchase_order', 'receipt', or 'payment',
this service extracts the deal value and reference, then:

  - Finds the lead linked to the message.
  - If there's an open Deal for that lead → updates deal_value + notes.
  - If none → creates a new Deal at the 'Proposal' stage.
  - If it's a receipt/payment confirmation → advances the deal to 'Closed Won'.

Called from email_nodes.node_archive and whatsapp_nodes.node_archive
for Transactional messages with a sales-relevant type.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.leads import Lead

logger = logging.getLogger("rdl_app_logger")

# These types indicate a completed purchase (→ Closed Won)
_PURCHASE_TYPES = {"receipt", "payment_confirmation", "payment", "paid"}

# These types indicate an active sales intent (→ Proposal stage)
_SALES_INTENT_TYPES = {
    "invoice", "order", "purchase_order", "po", "quotation",
    "quote", "pro_forma", "proforma", "estimate",
}


def _extract_amount(data: dict) -> Optional[float]:
    """Pull a numeric rupee/currency amount from the classifier's transactional_data."""
    for key in ("amount", "total", "grand_total", "value", "price",
                "subtotal", "net_amount", "invoice_amount"):
        raw = data.get(key)
        if raw is None:
            continue
        try:
            cleaned = re.sub(r"[^\d.]", "", str(raw))
            if cleaned:
                return float(cleaned)
        except (ValueError, TypeError):
            continue
    return None


def _extract_ref(data: dict) -> Optional[str]:
    for key in ("ref_number", "reference", "invoice_number", "invoice_no",
                "order_number", "order_id", "order_no", "po_number", "receipt_no"):
        val = data.get(key)
        if val:
            return str(val)
    return None


def process_transaction_for_deal(
    db: Session,
    lead_id: Optional[str],
    transactional_type: Optional[str],
    transactional_data: Optional[dict],
    owner_id: Optional[UUID],
    source_channel: str = "email",    # "email" | "whatsapp"
) -> Optional[Deal]:
    """
    Main entry point. Returns the created/updated Deal or None if not actionable.

    Args:
        db:                 active SQLAlchemy session (caller commits)
        lead_id:            UUID string of the matched lead
        transactional_type: classifier output (invoice, receipt, etc.)
        transactional_data: classifier-extracted {amount, ref_number, ...}
        owner_id:           RBAC owner UUID for new Deals
        source_channel:     "email" or "whatsapp" — for audit notes
    """
    if not transactional_type:
        return None

    ttype = transactional_type.lower().replace(" ", "_").replace("-", "_")
    is_purchase    = ttype in _PURCHASE_TYPES
    is_sales_intent = ttype in _SALES_INTENT_TYPES

    if not is_purchase and not is_sales_intent:
        return None

    if not lead_id:
        return None

    try:
        lead_uuid = UUID(lead_id)
    except (ValueError, TypeError):
        return None

    lead = db.query(Lead).filter(Lead.id == lead_uuid).first()
    if not lead:
        return None

    data   = transactional_data or {}
    amount = _extract_amount(data)
    ref    = _extract_ref(data)

    tag    = f"[{source_channel.upper()} {ttype}]{f' Ref: {ref}' if ref else ''}"

    # ── Find an existing open deal for this lead ───────────────────────────────
    existing = (
        db.query(Deal)
        .filter(
            Deal.lead_id == lead_uuid,
            Deal.stage.notin_(["Closed Won", "Closed Lost"]),
        )
        .order_by(Deal.created_at.desc())
        .first()
    )

    if existing:
        deal = existing

        # Update value only if the new amount is larger (guards against partial payment updates)
        if amount and (deal.deal_value is None or float(deal.deal_value) < amount):
            deal.deal_value = amount

        # Advance stage
        if is_purchase:
            deal.stage     = "Closed Won"
            deal.closed_at = datetime.now(timezone.utc)
            logger.info(f"[TRANSACTION] Deal {deal.id} → Closed Won via {tag}")
        elif is_sales_intent and deal.stage in ("Prospect", "New", "Qualified"):
            deal.stage = "Proposal"
            logger.info(f"[TRANSACTION] Deal {deal.id} → Proposal via {tag}")

        db.flush()
        return deal

    # ── No open deal → create one ─────────────────────────────────────────────
    stage = "Closed Won" if is_purchase else "Proposal"

    new_deal = Deal(
        lead_id      = lead_uuid,
        company_id   = getattr(lead, "company_id", None),
        deal_name    = f"{ttype.replace('_', ' ').title()} — {lead.name or lead.phone or str(lead_uuid)[:8]}",
        deal_value   = amount or 0,
        stage        = stage,
        win_probability = 80 if is_purchase else 40,
        owner_id     = owner_id,
        closed_at    = datetime.now(timezone.utc) if is_purchase else None,
    )
    db.add(new_deal)
    db.flush()
    logger.info(
        f"[TRANSACTION] Created Deal {new_deal.id} stage={stage} "
        f"value={amount} via {tag}"
    )
    return new_deal
