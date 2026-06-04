import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

logger = logging.getLogger("rdl_app_logger")

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.communication import Email, EmailLabel, EmailStatus
from app.models.user import User
from app.schema.gmail import (
    ApproveDraftRequest,
    EmailListResponse,
    EmailOut,
    EmailSLAAnalytics,
    GapNotificationListResponse,
    GapNotificationOut,
    GapResolveRequest,
    GenerateDraftRequest,
    GenerateDraftResponse,
    ResolveEmailRequest,
    SendEmailRequest,
    SequenceCreate,
    SequenceOut,
)
from app.services import gmail_service, product_knowledge_service
from app.services import email_sequence_service
from app.services.workflows.email_workflow import run_email_workflow
from app.services.workflows.email_nodes import generate_sales_draft as _gen_draft

router = APIRouter(prefix="/gmail", tags=["Gmail"])


def _check_email_access(db: Session, email: Email, user: User) -> None:
    """RBAC: regular user can only access emails received by an account they own.
    Super-admin bypasses. Raises 404 (not 403) so existence is not leaked."""
    if user.is_superuser:
        return
    from app.models.email_account import EmailAccount
    if not email.account_id:
        raise HTTPException(status_code=404, detail="Email not found")
    acc = db.query(EmailAccount).filter(EmailAccount.id == email.account_id).first()
    if not acc or acc.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Email not found")


# ── Inbox sync ────────────────────────────────────────────────────────────────

def _get_active_accounts(db: Session):
    """Active email accounts to poll. Extracted for testability."""
    from app.models.email_account import EmailAccount
    return db.query(EmailAccount).filter(EmailAccount.is_active == True).all()


@router.post("/sync", status_code=status.HTTP_200_OK)
def sync_inbox(
    max_results: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger inbox fetch and classification across all active accounts."""
    accounts = _get_active_accounts(db)
    processed = 0
    fetched = 0

    if accounts:
        for account in accounts:
            try:
                svc = gmail_service.get_gmail_service(account=account)
                gmail_service.ensure_labels_exist(svc, account_key=account.email_address)
                messages = gmail_service.fetch_unread_messages(svc, max_results=max_results)
                fetched += len(messages)
                for raw_msg in messages:
                    result = run_email_workflow(
                        db, raw_msg,
                        account_id=str(account.id),
                        account_email=account.email_address,
                    )
                    if result:
                        processed += 1
            except Exception as e:
                logger.error(f"[SYNC] Account {account.email_address} failed: {e}", exc_info=True)
    else:
        svc = gmail_service.get_gmail_service()
        gmail_service.ensure_labels_exist(svc)
        messages = gmail_service.fetch_unread_messages(svc, max_results=max_results)
        fetched = len(messages)
        for raw_msg in messages:
            result = run_email_workflow(db, raw_msg)
            if result:
                processed += 1

    return {"processed": processed, "fetched": fetched}


# ── Email list ────────────────────────────────────────────────────────────────

_NOISE_LABEL_VALUES = [
    EmailLabel.PROMOTIONAL, EmailLabel.PERSONAL,
    EmailLabel.TRANSACTIONAL, EmailLabel.UNCLASSIFIED,
]

@router.get("/", response_model=EmailListResponse)
def list_emails(
    label: Optional[EmailLabel] = Query(default=None),
    status: Optional[EmailStatus] = Query(default=None),
    needs_human: Optional[bool] = Query(default=None),
    lead_id: Optional[UUID] = Query(default=None),
    account_id: Optional[UUID] = Query(default=None),
    account_email: Optional[str] = Query(default=None),
    # business_only=true (default): show only Sales/Support/Grievance
    # business_only=false: show all including Promotional/Transactional
    business_only: bool = Query(default=True),
    owner_id: Optional[UUID] = Query(default=None, description="Super-admin: scope to one user"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # RBAC: emails are scoped via the EmailAccount.owner_id of the receiving account
    from app.models.email_account import EmailAccount
    if not current_user.is_superuser:
        _allowed_accts = [
            a.id for a in db.query(EmailAccount.id).filter(EmailAccount.owner_id == current_user.id).all()
        ]
    elif owner_id is not None:
        _allowed_accts = [
            a.id for a in db.query(EmailAccount.id).filter(EmailAccount.owner_id == owner_id).all()
        ]
    else:
        _allowed_accts = None  # super-admin, no scope filter

    q = db.query(Email)
    if _allowed_accts is not None:
        if not _allowed_accts:
            # User has no accounts → empty result
            return EmailListResponse(items=[], total=0, page=page, limit=limit)
        q = q.filter(Email.account_id.in_(_allowed_accts))
    if label:
        # Explicit label filter overrides business_only
        q = q.filter(Email.label == label)
    elif business_only:
        # Default inbox: only pipeline labels (Sales/Support/Grievance)
        q = q.filter(Email.label.notin_(_NOISE_LABEL_VALUES))
    else:
        # Other tab: only noise labels
        q = q.filter(Email.label.in_(_NOISE_LABEL_VALUES))
    if status:
        q = q.filter(Email.status == status)
    if needs_human is not None:
        q = q.filter(Email.needs_human == needs_human)
    if lead_id:
        q = q.filter(Email.lead_id == lead_id)
    if account_id:
        q = q.filter(Email.account_id == account_id)
    elif account_email:
        q = q.filter(Email.account_email == account_email)
    else:
        # Default: only emails from active accounts. Legacy (no account_id) and
        # orphaned (deleted account) emails are not shown in the "All" inbox.
        q = q.filter(Email.account_id.isnot(None))

    # ── Thread grouping (server-side) ──────────────────────────────────────────
    # Collapse each Gmail thread to a single row (its latest message) so threads
    # group correctly regardless of pagination. Emails with no thread_id are
    # treated as their own single-message thread (keyed by id).
    from sqlalchemy import func, Text, cast, case
    thread_key = func.coalesce(Email.gmail_thread_id, cast(Email.id, Text))
    rn = func.row_number().over(
        partition_by=thread_key, order_by=Email.received_at.desc()
    ).label("rn")
    sub = q.add_columns(rn).subquery()

    # "Unread" = the latest message in the thread still needs human attention
    # (new arrival, draft awaiting approval, or pending human reply). These sort
    # to the top; within each group, ordering is reverse-chronological.
    unread_statuses = (
        EmailStatus.NEW.value,
        EmailStatus.DRAFT_READY.value,
        EmailStatus.PENDING_HUMAN.value,
    )
    unread_priority = case((sub.c.status.in_(unread_statuses), 1), else_=0)

    latest_only = db.query(sub).filter(sub.c.rn == 1)
    total = latest_only.count()
    rows = (
        latest_only.order_by(unread_priority.desc(), sub.c.received_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    # Re-hydrate Email rows
    ids = [r.id for r in rows]
    if ids:
        email_rows = db.query(Email).filter(Email.id.in_(ids)).all()
        by_id = {e.id: e for e in email_rows}
        ordered = [by_id[i] for i in ids if i in by_id]
    else:
        ordered = []

    # thread_count = total messages in the FULL thread (unfiltered), so it matches
    # the conversation view (which fetches the whole thread regardless of label/account).
    thread_ids = [e.gmail_thread_id for e in ordered if e.gmail_thread_id]
    full_counts: dict[str, int] = {}
    if thread_ids:
        for tid, c in (
            db.query(Email.gmail_thread_id, func.count())
            .filter(Email.gmail_thread_id.in_(thread_ids))
            .group_by(Email.gmail_thread_id)
            .all()
        ):
            full_counts[tid] = c

    items = []
    for e in ordered:
        out = EmailOut.model_validate(e)
        out.thread_count = full_counts.get(e.gmail_thread_id, 1) if e.gmail_thread_id else 1
        items.append(out)
    return EmailListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/threads/{thread_id}", response_model=EmailListResponse)
def get_thread_messages(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all email messages belonging to a single Gmail thread, ordered chronologically.
    Used by the inbox UI to show the full conversation when a thread is selected.
    """
    items = (
        db.query(Email)
        .filter(Email.gmail_thread_id == thread_id)
        .order_by(Email.received_at.asc())
        .all()
    )
    return EmailListResponse(items=items, total=len(items), page=1, limit=len(items) or 1)


@router.get("/gaps", response_model=GapNotificationListResponse)
def list_rag_gaps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all draft-ready Sales emails where the RAG pipeline could not answer
    at least one customer question. Used by the dashboard to show the sales team
    what information needs to be manually filled in before sending.
    """
    rows = (
        db.query(Email)
        .filter(
            Email.label == EmailLabel.SALES,
            Email.followup_gaps.isnot(None),
            Email.status == EmailStatus.DRAFT_READY,
        )
        .order_by(Email.received_at.desc())
        .all()
    )
    items = [
        GapNotificationOut(
            email_id=r.id,
            gmail_draft_id=r.gmail_draft_id,
            customer_email=r.sender,
            subject=r.subject,
            received_at=r.received_at,
            gaps=r.followup_gaps or [],
        )
        for r in rows
    ]
    return GapNotificationListResponse(items=items, total=len(items))


_SINCE_HOURS = {
    "7h":   7,
    "24h":  24,
    "48h":  48,
    "7d":   168,   # 7 × 24
    "all":  None,
}


@router.post("/backfill-products", status_code=200)
def backfill_product_detection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run product detection on all Sales emails missing detected_product_name."""
    from app.services.sales_gap_service import detect_product
    rows = (
        db.query(Email)
        .filter(
            Email.label == EmailLabel.SALES,
            Email.detected_product_name.is_(None),
            Email.direction == "inbound",
        )
        .all()
    )
    updated = 0
    for e in rows:
        text = f"{e.subject or ''} {e.body_text or ''}"[:1000]
        try:
            product_id, product_name, _ = detect_product(db, text)
            if product_name:
                e.detected_product_id = product_id
                e.detected_product_name = product_name
                updated += 1
        except Exception:
            continue
    db.commit()
    return {"backfilled": updated, "total_checked": len(rows)}


@router.get("/analytics", response_model=EmailSLAAnalytics)
def get_email_analytics(
    since: str = "7d",
    account_id: Optional[UUID] = Query(default=None),
    account_email: Optional[str] = Query(default=None),
    owner_id: Optional[UUID] = Query(default=None, description="Super-admin: scope to one user"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Email pipeline analytics. since=7h|24h|48h|7d|all. account_id/account_email filters to a specific Gmail account."""
    from sqlalchemy import case, extract

    now = datetime.now(timezone.utc)
    hours = _SINCE_HOURS.get(since)
    if hours:
        if since == "7d":
            # Align to midnight 7 days ago so all emails land in a date bucket
            cutoff = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=6)
        else:
            cutoff = now - timedelta(hours=hours)
    else:
        cutoff = None

    # RBAC: scope emails to accounts owned by the requesting user
    from app.models.email_account import EmailAccount
    if not current_user.is_superuser:
        _allowed_accts = [
            a.id for a in db.query(EmailAccount.id).filter(EmailAccount.owner_id == current_user.id).all()
        ]
    elif owner_id is not None:
        _allowed_accts = [
            a.id for a in db.query(EmailAccount.id).filter(EmailAccount.owner_id == owner_id).all()
        ]
    else:
        _allowed_accts = None  # super-admin sees all accounts

    query = db.query(Email)
    if _allowed_accts is not None:
        query = query.filter(Email.account_id.in_(_allowed_accts))
    if cutoff:
        query = query.filter(Email.received_at >= cutoff)
    if account_id:
        # Specific account filter
        query = query.filter(Email.account_id == account_id)
    elif account_email:
        query = query.filter(Email.account_email == account_email)
    else:
        # "All accounts" default: ONLY emails linked to an active account.
        # Legacy emails (account_email IS NULL, pre-multi-account) are excluded
        # from dashboard metrics — they would inflate totals with unattributed data.
        # Orphaned emails (deleted account) are also excluded.
        query = query.filter(Email.account_id.isnot(None))
    all_emails = query.all()

    # ── Business pipeline labels (Sales + Support + Grievance) ────────────────
    # Promotional / Transactional / Personal / Unclassified are inbox noise and
    # must NOT pollute pipeline metrics (auto-sent rate, SLA, avg reply time).
    _PIPELINE_LABELS = {EmailLabel.SALES, EmailLabel.SUPPORT, EmailLabel.GRIEVANCE}
    _NOISE_LABELS = {EmailLabel.PROMOTIONAL, EmailLabel.PERSONAL, EmailLabel.TRANSACTIONAL}

    pipeline_emails = [e for e in all_emails if e.label in _PIPELINE_LABELS]
    sales    = [e for e in all_emails if e.label == EmailLabel.SALES]
    grievances = [e for e in all_emails if e.label == EmailLabel.GRIEVANCE]
    supports   = [e for e in all_emails if e.label == EmailLabel.SUPPORT]

    # Inbound business emails only (exclude outbound + noise from volume counts)
    inbound_pipeline = [e for e in pipeline_emails if e.direction == "inbound"]
    inbound_all = [e for e in all_emails if e.direction == "inbound"]
    outbound_all = [e for e in all_emails if e.direction == "outbound"]

    auto_sent = sum(1 for e in sales if e.status == EmailStatus.REPLIED and not e.needs_human)
    drafted   = sum(1 for e in sales if e.followup_gaps and e.status == EmailStatus.DRAFT_READY)
    pending   = sum(1 for e in all_emails if e.needs_human and e.status == EmailStatus.PENDING_HUMAN)
    # Auto-sent rate = auto-sent Sales / total Sales (only meaningful over Sales emails)
    auto_sent_rate = round(auto_sent / len(sales) * 100, 1) if sales else 0.0

    # Avg reply time — only for Sales emails that were actually replied to
    reply_minutes = []
    for e in sales:
        if e.status == EmailStatus.REPLIED and e.received_at and e.updated_at:
            diff = (e.updated_at - e.received_at).total_seconds() / 60
            if 0 < diff < 1440:
                reply_minutes.append(diff)
    avg_reply = round(sum(reply_minutes) / len(reply_minutes), 1) if reply_minutes else 0.0

    # SLA — 2 hour target, only measured on Sales emails whose window has closed
    sla_eligible = [
        e for e in sales
        if e.received_at and (now - e.received_at).total_seconds() > 7200
    ]
    sla_met = sum(
        1 for e in sla_eligible
        if e.status == EmailStatus.REPLIED and e.updated_at
        and (e.updated_at - e.received_at).total_seconds() <= 7200
    )
    sla_breached = len(sla_eligible) - sla_met

    competitor_mentions = sum(1 for e in all_emails if e.competitor_mention)

    # Grievance breakdown
    grv_resolved = sum(1 for e in grievances if e.resolved_at or e.status == EmailStatus.REPLIED)
    grv_pending  = len(grievances) - grv_resolved

    # Support breakdown
    sup_resolved = sum(1 for e in supports if e.resolved_at or e.status == EmailStatus.REPLIED)
    sup_pending  = len(supports) - sup_resolved

    # Time-series — buckets show INBOUND volume (all) + SLA on pipeline emails only
    def _make_bucket(label: str, bucket_emails: list) -> dict:
        sales_b = [e for e in bucket_emails if e.label == EmailLabel.SALES]
        eligible_b = [e for e in sales_b if e.received_at and (now - e.received_at).total_seconds() > 7200]
        met_b = sum(
            1 for e in eligible_b
            if e.status == EmailStatus.REPLIED and e.updated_at
            and (e.updated_at - e.received_at).total_seconds() <= 7200
        )
        return {
            "date":    label,
            "inbound":  sum(1 for e in bucket_emails if e.direction == "inbound"),
            "outbound": sum(1 for e in bucket_emails if e.direction == "outbound"),
            "sla_met":      met_b,
            "sla_breached": len(eligible_b) - met_b,
        }

    daily_stats = []
    if since == "7h":
        # 7 hourly buckets
        for i in range(6, -1, -1):
            t_end = now - timedelta(hours=i)
            t_start = t_end - timedelta(hours=1)
            bucket = [e for e in all_emails if e.received_at and t_start <= e.received_at.astimezone(timezone.utc) < t_end]
            daily_stats.append(_make_bucket(t_end.strftime("%H:%M"), bucket))
    elif since == "24h":
        # 12 two-hour buckets
        for i in range(11, -1, -1):
            t_end = now - timedelta(hours=i * 2)
            t_start = t_end - timedelta(hours=2)
            bucket = [e for e in all_emails if e.received_at and t_start <= e.received_at.astimezone(timezone.utc) < t_end]
            daily_stats.append(_make_bucket(t_end.strftime("%H:%M"), bucket))
    elif since == "48h":
        # 12 four-hour buckets
        for i in range(11, -1, -1):
            t_end = now - timedelta(hours=i * 4)
            t_start = t_end - timedelta(hours=4)
            bucket = [e for e in all_emails if e.received_at and t_start <= e.received_at.astimezone(timezone.utc) < t_end]
            daily_stats.append(_make_bucket(t_end.strftime("%d/%m %H:%M"), bucket))
    elif since == "7d":
        # Cutoff is midnight 6 days ago → exactly 7 calendar-day buckets, all emails land in one
        for i in range(6, -1, -1):
            day = (now - timedelta(days=i)).date()
            bucket = [e for e in all_emails if e.received_at and e.received_at.astimezone(timezone.utc).date() == day]
            daily_stats.append(_make_bucket(day.strftime("%d %b"), bucket))
    else:
        # "all" — span the full date range with weekly buckets so chart covers every email
        dated = [e for e in all_emails if e.received_at]
        if dated:
            first_dt = min(e.received_at.astimezone(timezone.utc) for e in dated)
            total_days = max((now - first_dt).days + 1, 1)
            if total_days <= 14:
                # Short history — daily buckets
                for i in range(total_days - 1, -1, -1):
                    day = (now - timedelta(days=i)).date()
                    bucket = [e for e in all_emails if e.received_at and e.received_at.astimezone(timezone.utc).date() == day]
                    daily_stats.append(_make_bucket(day.strftime("%d %b"), bucket))
            else:
                # Long history — weekly buckets covering everything
                num_weeks = (total_days + 6) // 7
                for i in range(num_weeks - 1, -1, -1):
                    t_end = now - timedelta(weeks=i)
                    t_start = t_end - timedelta(weeks=1)
                    bucket = [e for e in all_emails if e.received_at and t_start <= e.received_at.astimezone(timezone.utc) <= t_end]
                    daily_stats.append(_make_bucket(t_end.strftime("%d %b"), bucket))

    by_label = {}
    by_status = {}
    by_direction = {}
    by_account = {}
    total_attributed = 0
    total_legacy = 0

    for e in all_emails:
        lbl = e.label.value if e.label else "Unclassified"
        by_label[lbl] = by_label.get(lbl, 0) + 1

        st = e.status.value if e.status else "unknown"
        by_status[st] = by_status.get(st, 0) + 1

        d = e.direction or "unknown"
        by_direction[d] = by_direction.get(d, 0) + 1

        # Per-account breakdown — shows where each email came from
        if e.account_email:
            by_account[e.account_email] = by_account.get(e.account_email, 0) + 1
            total_attributed += 1
        else:
            by_account["(legacy / unattributed)"] = by_account.get("(legacy / unattributed)", 0) + 1
            total_legacy += 1

    # ── Product analytics ─────────────────────────────────────────────────────
    by_product: dict = {}
    product_converted: dict = {}  # product_name → replied count
    for e in sales:
        name = e.detected_product_name
        if name:
            by_product[name] = by_product.get(name, 0) + 1
            if e.status == EmailStatus.REPLIED:
                product_converted[name] = product_converted.get(name, 0) + 1

    top_products_purchased = sorted(
        [
            {
                "name": name,
                "inquiries": count,
                "converted": product_converted.get(name, 0),
                "conversion_pct": round(product_converted.get(name, 0) / count * 100, 1),
            }
            for name, count in by_product.items()
        ],
        key=lambda x: x["converted"],
        reverse=True,
    )[:15]

    # ── Revenue & order analytics (from transactional emails) ─────────────────
    revenue_total = 0.0
    order_count = 0
    po_count = 0
    for e in all_emails:
        if e.label != EmailLabel.TRANSACTIONAL:
            continue
        tdata = e.transactional_data or {}
        ttype = (e.transactional_type or "").lower()
        raw_amount = tdata.get("amount") or tdata.get("total") or tdata.get("value")
        if raw_amount:
            try:
                cleaned = str(raw_amount).replace(",", "").replace("₹", "").replace("Rs", "").strip()
                revenue_total += float("".join(c for c in cleaned if c.isdigit() or c == "."))
            except (ValueError, TypeError):
                pass
        if "order" in ttype or "invoice" in ttype or "receipt" in ttype:
            order_count += 1
        ref = (tdata.get("reference_number") or "").upper()
        if "PO" in ref or "P.O" in ref or "purchase" in ttype:
            po_count += 1

    # ── Conversion rate ───────────────────────────────────────────────────────
    conversion_rate_pct = round(
        sum(1 for e in sales if e.status == EmailStatus.REPLIED) / len(sales) * 100, 1
    ) if sales else 0.0

    # ── Lead pipeline (interest levels of leads linked to emails in period) ──
    lead_pipeline: dict = {}
    seen_lead_ids: set = set()
    for e in sales:
        if e.lead_id and e.lead_id not in seen_lead_ids:
            seen_lead_ids.add(e.lead_id)
    if seen_lead_ids:
        from app.models.leads import Lead
        leads = db.query(Lead).filter(Lead.id.in_(seen_lead_ids)).all()
        for lead in leads:
            lvl = lead.interest_level or "Unknown"
            lead_pipeline[lvl] = lead_pipeline.get(lvl, 0) + 1

    # ── Company / source segmentation ─────────────────────────────────────────
    _KNOWN_SOURCES = {
        "indiamart":        "IndiaMart",
        "tradeindia":       "TradeIndia",
        "justdial":         "JustDial",
        "exportersindia":   "ExportersIndia",
        "alibaba":          "Alibaba",
        "amazon":           "Amazon",
        "flipkart":         "Flipkart",
        "snapdeal":         "Snapdeal",
        "shopclues":        "ShopClues",
        "meesho":           "Meesho",
        "udaan":            "Udaan",
        "gmail":            "Direct (Gmail)",
        "yahoo":            "Direct (Yahoo)",
        "outlook":          "Direct (Outlook)",
        "hotmail":          "Direct (Hotmail)",
        "rediffmail":       "Direct (Rediff)",
    }
    def _source_from_sender(sender: str) -> str:
        import re as _re
        m = _re.search(r'[\w.+-]+@([\w.-]+)', sender or "")
        if not m:
            return "Unknown"
        domain = m.group(1).lower()
        for key, label in _KNOWN_SOURCES.items():
            if key in domain:
                return label
        # Use the second-level domain as the company name
        parts = domain.split(".")
        return parts[-2].capitalize() if len(parts) >= 2 else domain

    by_company_source: dict = {}
    for e in inbound_pipeline:
        src = _source_from_sender(e.sender)
        by_company_source[src] = by_company_source.get(src, 0) + 1

    # ── Product × source matrix ───────────────────────────────────────────────
    import re as _re
    def _company_from_sender(sender: str) -> str:
        """Extract display name; fall back to domain-based company."""
        name_part = _re.split(r'\s*<', sender or "")[0].strip().strip('"').strip("'")
        # Remove trailing punctuation/underscore junk
        name_part = _re.sub(r'[_@]+$', '', name_part).strip()
        if name_part and len(name_part) > 1:
            return name_part
        # Fall back to domain
        m = _re.search(r'@([\w.-]+)', sender or "")
        if m:
            parts = m.group(1).split(".")
            return parts[-2].capitalize() if len(parts) >= 2 else m.group(1)
        return "Unknown"

    # product × source
    _ps_inquiries: dict = {}   # (product, source) → count
    _ps_converted: dict = {}   # (product, source) → replied count
    # company details
    _company_data: dict = {}   # email_addr → {name, source, products: {product_name: count}}

    for e in sales:
        product = e.detected_product_name
        src = _source_from_sender(e.sender)
        company = _company_from_sender(e.sender)
        # extract plain email
        m = _re.search(r'<?([\w.+-]+@[\w.-]+)>?', e.sender or "")
        email_addr = m.group(1).lower() if m else e.sender or ""

        if product:
            key = (product, src)
            _ps_inquiries[key] = _ps_inquiries.get(key, 0) + 1
            if e.status == EmailStatus.REPLIED:
                _ps_converted[key] = _ps_converted.get(key, 0) + 1

        if email_addr not in _company_data:
            _company_data[email_addr] = {"name": company, "source": src, "email": email_addr, "products": {}, "total": 0}
        _company_data[email_addr]["total"] += 1
        if product:
            pd = _company_data[email_addr]["products"]
            pd[product] = pd.get(product, 0) + 1

    product_source_rows = sorted(
        [
            {
                "product": k[0],
                "source": k[1],
                "count": v,
                "converted": _ps_converted.get(k, 0),
            }
            for k, v in _ps_inquiries.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )[:50]

    product_company_rows = sorted(
        [
            {
                "company": v["name"],
                "source": v["source"],
                "email": v["email"],
                "total_emails": v["total"],
                "products": sorted(
                    [{"name": p, "count": c} for p, c in v["products"].items()],
                    key=lambda x: x["count"], reverse=True
                ),
            }
            for v in _company_data.values()
        ],
        key=lambda x: x["total_emails"],
        reverse=True,
    )[:40]

    # ── Total volume breakdown ─────────────────────────────────────────────────
    total_volume_breakdown = {
        "Total":      len(all_emails),
        "Inbound":    len(inbound_all),
        "Outbound":   len(outbound_all),
        "Sales":      len(sales),
        "Support":    len(supports),
        "Grievance":  len(grievances),
        "Replied":    sum(1 for e in pipeline_emails if e.status == EmailStatus.REPLIED),
        "Pending":    pending,
    }

    # ── by_owner: super-admin view — user email → their Gmail accounts + email count ──
    # Only populated for super-admin (reveals ownership; regular users don't need it)
    by_owner: dict = {}
    if current_user.is_superuser:
        from app.models.user import User as _User
        from app.models.email_account import EmailAccount as _EAcct
        # Build: account_id → owner user email
        acct_ids = {e.account_id for e in all_emails if e.account_id}
        if acct_ids:
            owner_rows = (
                db.query(_EAcct.id, _EAcct.email_address, _User.email)
                .join(_User, _EAcct.owner_id == _User.id)
                .filter(_EAcct.id.in_(acct_ids))
                .all()
            )
            acct_to_owner: dict = {}   # account_id → user_email
            acct_to_gmail: dict = {}   # account_id → gmail_address
            for acct_id, gmail_addr, user_email in owner_rows:
                acct_to_owner[acct_id] = user_email
                acct_to_gmail[acct_id] = gmail_addr
            # Aggregate per user
            for e in all_emails:
                if not e.account_id:
                    continue
                user_email = acct_to_owner.get(e.account_id, "unknown")
                gmail_addr = acct_to_gmail.get(e.account_id, e.account_email or "?")
                if user_email not in by_owner:
                    by_owner[user_email] = {"gmail_accounts": [], "email_count": 0}
                if gmail_addr not in by_owner[user_email]["gmail_accounts"]:
                    by_owner[user_email]["gmail_accounts"].append(gmail_addr)
                by_owner[user_email]["email_count"] += 1

    return EmailSLAAnalytics(
        total_emails=len(all_emails),
        total_inbound=len(inbound_all),
        total_outbound=len(outbound_all),
        total_attributed=total_attributed,
        total_legacy=total_legacy,
        total_sales_emails=len(sales),
        auto_sent=auto_sent,
        drafted_for_review=drafted,
        pending_human=pending,
        auto_sent_rate_pct=auto_sent_rate,
        avg_reply_minutes=avg_reply,
        sla_breached=sla_breached,
        sla_met=sla_met,
        competitor_mentions=competitor_mentions,
        daily_stats=daily_stats,
        grievance_total=len(grievances),
        grievance_resolved=grv_resolved,
        grievance_pending=grv_pending,
        support_total=len(supports),
        support_resolved=sup_resolved,
        support_pending=sup_pending,
        by_label={k: v for k, v in by_label.items()},
        by_status=by_status,
        by_direction=by_direction,
        by_account=by_account,
        by_owner=by_owner,
        by_product=by_product,
        top_products_purchased=top_products_purchased,
        revenue_total=round(revenue_total, 2),
        order_count=order_count,
        po_count=po_count,
        conversion_rate_pct=conversion_rate_pct,
        lead_pipeline=lead_pipeline,
        by_company_source=by_company_source,
        total_volume_breakdown=total_volume_breakdown,
        product_source_rows=product_source_rows,
        product_company_rows=product_company_rows,
    )


@router.post("/sequences", response_model=SequenceOut, status_code=status.HTTP_201_CREATED)
def create_sequence(
    payload: SequenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a drip email sequence for a lead. Steps are sent automatically at day_offset intervals."""
    steps = [s.model_dump() for s in payload.steps]
    seq = email_sequence_service.create_sequence(
        db=db,
        lead_id=payload.lead_id,
        name=payload.name,
        steps=steps,
        created_by=current_user.email,
    )
    return seq


@router.get("/sequences", response_model=list[SequenceOut])
def list_sequences(
    lead_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return email_sequence_service.list_sequences(db, lead_id=lead_id)


@router.post("/sequences/{sequence_id}/pause", status_code=status.HTTP_204_NO_CONTENT)
def pause_sequence(
    sequence_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    email_sequence_service.pause_sequence(db, sequence_id)


@router.post("/sequences/{sequence_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_sequence(
    sequence_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    email_sequence_service.cancel_sequence(db, sequence_id)


@router.post("/{email_id}/gaps/resolve", response_model=EmailOut)
def resolve_gap(
    email_id: UUID,
    payload: GapResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sales person fills in the answer for a specific RAG gap.
    The answer is embedded into the RAG vector store immediately so future
    emails about the same product get a complete answer.
    The gap is marked resolved in the email record.
    """
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    _check_email_access(db, email, current_user)

    gaps: list[dict] = list(email.followup_gaps or [])
    if payload.gap_index < 0 or payload.gap_index >= len(gaps):
        raise HTTPException(status_code=400, detail=f"gap_index {payload.gap_index} out of range (0–{len(gaps)-1})")

    gap = gaps[payload.gap_index]
    if gap.get("resolved"):
        raise HTTPException(status_code=400, detail="Gap already resolved")

    # Embed the answer into the product knowledge base
    # payload.product_id overrides the gap's stored product_id (user may reassign)
    product_id_str = payload.product_id or gap.get("product_id")
    category = payload.category or gap.get("topic", "general")

    if product_id_str:
        try:
            from uuid import UUID as _UUID
            from app.database.core import SessionLocal
            # Use a SEPARATE session for knowledge embedding so internal commits
            # inside add_entry/update_coverage_score don't expire the email ORM
            # object in the route's session and corrupt the transaction state.
            kb_db = SessionLocal()
            try:
                product_knowledge_service.add_entry(
                    db=kb_db,
                    product_id=_UUID(product_id_str),
                    category=category,
                    content=f"Q: {gap['question']}\nA: {payload.answer}",
                    added_by=current_user.email,
                )
                product_knowledge_service.update_coverage_score(kb_db, product_id_str)
            finally:
                kb_db.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to embed knowledge: {e}")

    # Mark gap resolved
    gaps[payload.gap_index] = {
        **gap,
        "resolved": True,
        "answer": payload.answer,
        "resolved_by": current_user.email,
    }
    email.followup_gaps = gaps
    db.commit()
    db.refresh(email)

    # If all gaps are now resolved, regenerate the draft with the new knowledge
    all_resolved = all(g.get("resolved") for g in gaps)
    if all_resolved and email.gmail_draft_id:
        from app.services.workflows.email_workflow import resume_after_gaps_resolved
        resume_after_gaps_resolved(db, str(email_id))
        # Always re-read from DB — resume may have updated the draft_id / status
        db.expire(email)
        email = db.query(Email).filter(Email.id == email_id).first()

    return email


@router.get("/{email_id}", response_model=EmailOut)
def get_email(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    _check_email_access(db, email, current_user)
    return email


# ── Human-in-the-loop ─────────────────────────────────────────────────────────

@router.post("/{email_id}/resolve", response_model=EmailOut)
def resolve_email(
    email_id: UUID,
    payload: ResolveEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a Support/Grievance email as handled by a human."""
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    _check_email_access(db, email, current_user)
    email.needs_human = False
    email.resolved_by = payload.resolved_by or current_user.email
    email.resolved_at = datetime.now(timezone.utc)
    email.status = EmailStatus.REPLIED
    db.commit()
    db.refresh(email)

    # Send resolution confirmation to the customer
    try:
        sender_email_addr = gmail_service.extract_email_address(email.sender)
        display_name = email.sender.split("<")[0].strip() or sender_email_addr.split("@")[0]
        first_name = display_name.split()[0].title() if display_name else "Customer"
        resolution_subject = email.subject if email.subject.startswith("Re:") else f"Re: {email.subject}"
        resolution_body = (
            f"Dear {first_name},\n\n"
            "Thank you for your patience. Your query has been reviewed and addressed by our team.\n\n"
        )
        if payload.note:
            resolution_body += f"{payload.note}\n\n"
        resolution_body += (
            "If you have any further questions, please don't hesitate to reach out.\n\n"
            "Best regards,\nRDL Technologies Support Team"
        )
        # Reply from the account that received the email
        if email.account_id:
            from app.services.email_account_service import get_account as _get_acct
            _acct = _get_acct(db, email.account_id)
            gmail_svc = gmail_service.get_gmail_service(account=_acct) if _acct else gmail_service.get_gmail_service()
        else:
            gmail_svc = gmail_service.get_gmail_service()
        gmail_service.send_email(
            gmail_svc,
            to=sender_email_addr,
            subject=resolution_subject,
            body=resolution_body,
            thread_id=email.gmail_thread_id,
        )
    except Exception as e:
        logger.warning(f"[GMAIL] Failed to send resolution confirmation: {e}")

    return email


# ── Sales draft approval ──────────────────────────────────────────────────────

@router.post("/{email_id}/approve-draft", response_model=EmailOut)
def approve_draft(
    email_id: UUID,
    payload: ApproveDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approve the AI draft for a Sales email.
    - If edit_body is provided, replaces the draft content before sending.
    - Sends the Gmail draft and marks email as replied.
    """
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    _check_email_access(db, email, current_user)
    if email.status != EmailStatus.DRAFT_READY:
        raise HTTPException(status_code=400, detail="Email has no pending draft to approve")
    if not email.gmail_draft_id:
        raise HTTPException(status_code=400, detail="No Gmail draft ID on record")

    # Use the account that received the email for all send operations
    if email.account_id:
        from app.services.email_account_service import get_account as _get_acct
        _acct = _get_acct(db, email.account_id)
        svc = gmail_service.get_gmail_service(account=_acct) if _acct else gmail_service.get_gmail_service()
    else:
        svc = gmail_service.get_gmail_service()

    if payload.edit_body:
        # Delete old draft, create new one with edited body, then send
        try:
            svc.users().drafts().delete(userId="me", id=email.gmail_draft_id).execute()
        except Exception:
            pass
        sender_email = gmail_service.extract_email_address(email.sender)
        reply_subject = email.subject if (email.subject or "").startswith("Re:") else f"Re: {email.subject}"
        new_draft = gmail_service.create_draft(
            svc,
            to=sender_email,
            subject=reply_subject,
            body=payload.edit_body,
            thread_id=email.gmail_thread_id,
        )
        email.ai_draft = payload.edit_body
        email.gmail_draft_id = new_draft["id"]
        db.flush()

    try:
        gmail_service.send_draft(svc, email.gmail_draft_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send draft: {e}")

    email.status = EmailStatus.REPLIED
    email.resolved_by = current_user.email
    email.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(email)
    return email


@router.post("/{email_id}/discard-draft", response_model=EmailOut)
def discard_draft(
    email_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Discard the AI draft — human will reply manually. Flags for human handling."""
    email = db.query(Email).filter(Email.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    _check_email_access(db, email, current_user)

    if email.gmail_draft_id:
        try:
            svc = gmail_service.get_gmail_service()
            svc.users().drafts().delete(userId="me", id=email.gmail_draft_id).execute()
        except Exception:
            pass

    email.gmail_draft_id = None
    email.ai_draft = None
    email.needs_human = True
    email.status = EmailStatus.PENDING_HUMAN
    db.commit()
    db.refresh(email)
    return email


# ── Outbound send ─────────────────────────────────────────────────────────────

@router.post("/generate-draft", response_model=GenerateDraftResponse)
def generate_draft(
    payload: GenerateDraftRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Generate an AI draft reply using the RAG pipeline.
    Returns the draft text only — does NOT send or save anything.
    The caller edits the draft in the UI, then calls /send when ready.
    """
    draft = _gen_draft(
        sender=payload.to,
        subject=payload.subject,
        body=payload.body,
    )
    if not draft:
        raise HTTPException(status_code=503, detail="AI draft generation failed — check Vertex AI connectivity")
    return GenerateDraftResponse(draft=draft)


@router.post("/send", status_code=status.HTTP_201_CREATED, response_model=EmailOut)
def send_email(
    payload: SendEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send an outbound email and record it.

    For a threaded manual reply, pass `account_id` (send from the receiving account)
    and `reply_to_email_id` (the inbound email being answered) so the reply lands in
    the same Gmail thread with correct In-Reply-To/References headers and is attributed
    to the right account in the inbox.
    """
    from app.models.email_account import EmailAccount

    # Resolve the inbound email being replied to (for threading + account inheritance)
    original = None
    if payload.reply_to_email_id:
        original = db.query(Email).filter(Email.id == payload.reply_to_email_id).first()

    # Pick the sending account: explicit account_id → original's account → legacy token
    account = None
    account_id = payload.account_id or (original.account_id if original else None)
    if account_id:
        account = db.query(EmailAccount).filter(EmailAccount.id == account_id).first()

    svc = gmail_service.get_gmail_service(account=account) if account else gmail_service.get_gmail_service()
    try:
        sent = gmail_service.send_email(
            svc,
            to=payload.to,
            subject=payload.subject,
            body=payload.body,
            thread_id=payload.thread_id or (original.gmail_thread_id if original else None),
            reply_to_message_id=(original.rfc_message_id if original else None),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")

    email_row = Email(
        gmail_message_id=sent["id"],
        gmail_thread_id=sent.get("threadId"),
        direction="outbound",
        sender=account.email_address if account else current_user.email,
        recipients=[payload.to],
        subject=payload.subject,
        body_text=payload.body,
        received_at=datetime.now(timezone.utc),
        label=(original.label if original else EmailLabel.SALES),
        status=EmailStatus.REPLIED,
        account_id=account.id if account else (original.account_id if original else None),
        account_email=account.email_address if account else (original.account_email if original else None),
        lead_id=(original.lead_id if original else None),
    )
    db.add(email_row)

    # Mark the original inbound as replied so it no longer shows as pending.
    if original and original.status != EmailStatus.REPLIED:
        original.status = EmailStatus.REPLIED
        original.needs_human = False

    db.commit()
    db.refresh(email_row)
    return email_row
