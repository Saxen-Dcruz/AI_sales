import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schema.linkedin import (
    DiscoveryJobRequest,
    LinkedInOutreachCreate,
    LinkedInOutreachListResponse,
    LinkedInOutreachOut,
    OutreachStatsResponse,
    ReplyUpdate,
)
from app.services import linkedin_outreach_service as svc

router = APIRouter(prefix="/linkedin", tags=["LinkedIn"])
logger = logging.getLogger("rdl_app_logger")


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=OutreachStatsResponse)
def outreach_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Outreach funnel: discovered → connection sent → connected → messaged → replied."""
    return svc.get_outreach_stats(db)


@router.get("/budget")
def daily_budget(_: User = Depends(get_current_user)):
    """Current daily/weekly LinkedIn outreach budget remaining."""
    return svc.get_daily_budget()


# ── Discovery ─────────────────────────────────────────────────────────────────

@router.post("/discover-companies", status_code=status.HTTP_202_ACCEPTED)
def discover_companies(
    payload: DiscoveryJobRequest,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_user),
):
    """
    Trigger background company URL discovery.

    Runs the multi-source search engine (DDGS + Google fallback) across the full
    city × industry matrix (or a subset if city_batch / industry_batch are provided).
    Results are saved to the companies table as they are scraped.

    This is a fire-and-forget job — check /linkedin/stats for progress.
    """
    def _run():
        from app.scripts.linkedin.sourcing import find_companies_at_scale
        from app.database.core import SessionLocal
        from app.models.company import Company

        with SessionLocal() as db:
            existing = {r[0] for r in db.query(Company.linkedin_url).all() if r[0]}

        urls = find_companies_at_scale(
            city_batch=payload.city_batch,
            industry_batch=payload.industry_batch,
            max_results_per_query=payload.max_results_per_query,
            delay_min=payload.delay_min,
            delay_max=payload.delay_max,
            existing_urls=existing,
        )
        logger.info(f"[LINKEDIN] Discovery finished — {len(urls)} new company URLs queued for scraping")

    background_tasks.add_task(_run)
    return {
        "message": "Company discovery started in background",
        "cities": len(payload.city_batch) if payload.city_batch else "all (200+)",
        "industries": len(payload.industry_batch) if payload.industry_batch else "all (80+)",
    }


# ── Outreach records ───────────────────────────────────────────────────────────

@router.post("/", response_model=LinkedInOutreachOut, status_code=status.HTTP_201_CREATED)
def add_outreach_record(
    payload: LinkedInOutreachCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Manually add a LinkedIn profile to the outreach pipeline."""
    return svc.upsert_outreach_record(
        db=db,
        linkedin_url=payload.linkedin_url,
        full_name=payload.full_name or "",
        headline=payload.headline or "",
        location=payload.location or "",
        company_name=payload.company_name or "",
        industry_tag=payload.industry_tag or "",
        city_tag=payload.city_tag or "",
        lead_id=payload.lead_id,
        company_id=payload.company_id,
    )


@router.get("/", response_model=LinkedInOutreachListResponse)
def list_outreach(
    connection_status: Optional[str] = Query(None),
    message_status: Optional[str] = Query(None),
    role_category: Optional[str] = Query(None),
    industry_tag: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List outreach records with filters."""
    items, total = svc.list_outreach(
        db, connection_status=connection_status, message_status=message_status,
        role_category=role_category, industry_tag=industry_tag, page=page, limit=limit,
    )
    return LinkedInOutreachListResponse(items=items, total=total, page=page, limit=limit)


@router.get("/{outreach_id}", response_model=LinkedInOutreachOut)
def get_outreach(
    outreach_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.models.linkedin import LinkedInOutreach
    record = db.query(LinkedInOutreach).filter(LinkedInOutreach.id == outreach_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


# ── Connection & message actions ───────────────────────────────────────────────

@router.post("/{outreach_id}/queue-connection")
def queue_connection(
    outreach_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Queue a connection request for this profile.
    Checks daily budget (15/day). Returns the generated connection note.
    The Playwright script reads 'pending' records and sends them.
    """
    result = svc.queue_connection_request(db, outreach_id)
    if not result["ok"]:
        reason = result["reason"]
        code = 404 if "not found" in reason.lower() or "already" in reason.lower() else 429
        raise HTTPException(status_code=code, detail=reason)
    return result


@router.post("/{outreach_id}/queue-message")
def queue_message(
    outreach_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Queue a follow-up message for a connected profile.
    Only valid when connection_status == 'connected'.
    Checks daily (40/day) and weekly (90/week) budgets.
    """
    result = svc.queue_follow_up_message(db, outreach_id)
    if not result["ok"]:
        raise HTTPException(status_code=429, detail=result["reason"])
    return result


@router.patch("/{outreach_id}/connected", response_model=LinkedInOutreachOut)
def mark_connected(
    outreach_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Mark a connection request as accepted (called by Playwright script or manually)."""
    record = svc.mark_connected(db, outreach_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.patch("/{outreach_id}/message-sent", response_model=LinkedInOutreachOut)
def mark_message_sent(
    outreach_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Mark a queued message as sent (called by Playwright script)."""
    record = svc.mark_message_sent(db, outreach_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


@router.patch("/{outreach_id}/reply", response_model=LinkedInOutreachOut)
def mark_reply(
    outreach_id: UUID,
    payload: ReplyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Record a reply received from the prospect."""
    record = svc.mark_reply_received(db, outreach_id, payload.reply_preview)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


# ── Template preview ───────────────────────────────────────────────────────────

@router.get("/templates/preview")
def preview_template(
    role_category: str = Query(..., description="c_suite | cto | cfo | procurement | operations | engineering | generic"),
    industry_tag: str = Query(..., description="pharma | petroleum | textile | food | chemical | automotive | electronics | metals | generic etc."),
    name: str = Query(default="Rahul"),
    company: str = Query(default="ABC Manufacturing"),
    _: User = Depends(get_current_user),
):
    """
    Preview the connection note and full message for a given role + industry.
    Useful for reviewing templates before running outreach.
    """
    from app.services.linkedin_templates import classify_industry, get_connection_note, get_full_message, get_template_key
    industry_bucket = classify_industry(industry_tag)
    template_key    = get_template_key(role_category, industry_bucket)
    return {
        "role_category":    role_category,
        "industry_bucket":  industry_bucket,
        "template_key":     template_key,
        "connection_note":  get_connection_note(name, company, role_category, industry_bucket),
        "full_message":     get_full_message(name, company, role_category, industry_bucket),
    }
