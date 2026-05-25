import asyncio
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_user, get_db
from app.models.lead_gen import (
    CampaignContact, OutreachCampaign, OutreachMessage, OutreachThread,
    ProspectCompany, ProspectContact,
)
from app.models.user import User
from app.schema.lead_gen import (
    AddContactsToCampaignRequest, ApproveOutreachRequest, CampaignContactOut,
    DiscoverySearchRequest, DiscoverySearchResponse, LeadGenAnalyticsOut,
    OutreachCampaignCreate, OutreachCampaignOut, OutreachCampaignUpdate,
    OutreachThreadOut, ProspectCompanyOut, ProspectContactOut, SetInterestRequest,
)

router = APIRouter(prefix="/lead-gen", tags=["Lead Generation"])


# ── Discovery ──────────────────────────────────────────────────────────────────

@router.post("/discovery/search", response_model=DiscoverySearchResponse)
def discovery_search(
    payload: DiscoverySearchRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.services.discovery_service import run_discovery
    return run_discovery(db, payload)


@router.get("/discovery/companies")
def list_companies(
    industry: Optional[str] = Query(default=None),
    location: Optional[str] = Query(default=None),
    score_min: Optional[int] = Query(default=None),
    interest_level: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(ProspectCompany)
    if industry:
        q = q.filter(ProspectCompany.industry.ilike(f"%{industry}%"))
    if location:
        q = q.filter(ProspectCompany.location.ilike(f"%{location}%"))
    if score_min is not None:
        q = q.filter(ProspectCompany.ai_score >= score_min)
    if interest_level:
        q = q.filter(ProspectCompany.interest_level == interest_level)
    if search:
        q = q.filter(ProspectCompany.name.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(ProspectCompany.ai_score.desc().nullslast(), ProspectCompany.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": [ProspectCompanyOut.model_validate(c) for c in items], "total": total, "page": page, "limit": limit}


@router.get("/discovery/contacts")
def list_contacts(
    company_id: Optional[UUID] = Query(default=None),
    campaign_id: Optional[UUID] = Query(default=None),
    job_title: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(ProspectContact).options(joinedload(ProspectContact.company))
    if company_id:
        q = q.filter(ProspectContact.company_id == company_id)
    if job_title:
        q = q.filter(ProspectContact.job_title.ilike(f"%{job_title}%"))
    if search:
        q = q.filter(ProspectContact.name.ilike(f"%{search}%") | ProspectContact.email.ilike(f"%{search}%"))
    if campaign_id:
        existing = db.query(CampaignContact.contact_id).filter(CampaignContact.campaign_id == campaign_id)
        q = q.filter(ProspectContact.id.notin_(existing))
    total = q.count()
    items = q.order_by(ProspectContact.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": [ProspectContactOut.model_validate(c) for c in items], "total": total, "page": page, "limit": limit}


@router.post("/discovery/linkedin-scrape", status_code=status.HTTP_202_ACCEPTED)
def linkedin_scrape(
    keyword: str = Query(..., description="Industry keyword, e.g. 'logistics'"),
    location: str = Query(default="India"),
    target_roles: str = Query(default="Manager,Director,CEO,Operations,Procurement", description="Comma-separated roles"),
    max_companies: int = Query(default=10, ge=1, le=30),
    max_people: int = Query(default=5, ge=1, le=10),
    background_tasks: BackgroundTasks = ...,
    _: User = Depends(get_current_user),
):
    """Search LinkedIn directly using saved session. Runs as a background job."""
    from app.services.linkedin_scraper_service import run_linkedin_scrape
    roles = [r.strip() for r in target_roles.split(",") if r.strip()]

    def _run():
        asyncio.run(run_linkedin_scrape(
            keyword=keyword,
            location=location,
            target_roles=roles,
            max_results=max_people * len(roles),
        ))

    background_tasks.add_task(_run)
    return {"message": "LinkedIn scrape started", "keyword": keyword, "location": location, "target_roles": roles}


@router.post("/discovery/score")
def score_companies(
    company_ids: Optional[list[UUID]] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.services.ai_lead_scorer import batch_score_companies
    updated = batch_score_companies(db, company_ids)
    return {"scored": updated}


# ── Campaigns ──────────────────────────────────────────────────────────────────

@router.get("/campaigns")
def list_campaigns(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(OutreachCampaign)
    if status:
        q = q.filter(OutreachCampaign.status == status)
    campaigns = q.order_by(OutreachCampaign.created_at.desc()).all()
    result = []
    for c in campaigns:
        contacts = db.query(CampaignContact).filter(CampaignContact.campaign_id == c.id)
        sent = contacts.filter(CampaignContact.status.in_(["sent", "replied", "interested", "not_interested"])).count()
        replied = contacts.filter(CampaignContact.status.in_(["replied", "interested"])).count()
        out = OutreachCampaignOut.model_validate(c)
        out.contact_count = contacts.count()
        out.sent_count = sent
        out.replied_count = replied
        result.append(out)
    return result


@router.post("/campaigns", response_model=OutreachCampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: OutreachCampaignCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    campaign = OutreachCampaign(**payload.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    out = OutreachCampaignOut.model_validate(campaign)
    out.contact_count = 0
    out.sent_count = 0
    out.replied_count = 0
    return out


@router.get("/campaigns/{campaign_id}", response_model=OutreachCampaignOut)
def get_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    contacts = db.query(CampaignContact).filter(CampaignContact.campaign_id == c.id)
    out = OutreachCampaignOut.model_validate(c)
    out.contact_count = contacts.count()
    out.sent_count = contacts.filter(CampaignContact.status.in_(["sent","replied","interested","not_interested"])).count()
    out.replied_count = contacts.filter(CampaignContact.status.in_(["replied","interested"])).count()
    return out


@router.patch("/campaigns/{campaign_id}", response_model=OutreachCampaignOut)
def update_campaign(
    campaign_id: UUID,
    payload: OutreachCampaignUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    out = OutreachCampaignOut.model_validate(c)
    contacts = db.query(CampaignContact).filter(CampaignContact.campaign_id == c.id)
    out.contact_count = contacts.count()
    out.sent_count = contacts.filter(CampaignContact.status.in_(["sent","replied","interested","not_interested"])).count()
    out.replied_count = contacts.filter(CampaignContact.status.in_(["replied","interested"])).count()
    return out


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(c)
    db.commit()


@router.post("/campaigns/{campaign_id}/add-contacts")
def add_contacts_to_campaign(
    campaign_id: UUID,
    payload: AddContactsToCampaignRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    c = db.query(OutreachCampaign).filter(OutreachCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    added = 0
    for contact_id in payload.contact_ids:
        exists = db.query(CampaignContact).filter(
            CampaignContact.campaign_id == campaign_id,
            CampaignContact.contact_id == contact_id,
        ).first()
        if not exists:
            db.add(CampaignContact(campaign_id=campaign_id, contact_id=contact_id))
            added += 1
    db.commit()
    return {"added": added}


@router.post("/campaigns/{campaign_id}/generate-drafts")
def generate_drafts(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.services.outreach_ai_service import generate_drafts_for_campaign
    count = generate_drafts_for_campaign(db, str(campaign_id))
    return {"drafts_generated": count}


# ── Outreach Queue & Actions ───────────────────────────────────────────────────

@router.get("/outreach/queue")
def get_outreach_queue(
    campaign_id: Optional[UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(CampaignContact).options(
        joinedload(CampaignContact.contact).joinedload(ProspectContact.company),
        joinedload(CampaignContact.campaign),
    )
    if campaign_id:
        q = q.filter(CampaignContact.campaign_id == campaign_id)
    if status_filter:
        q = q.filter(CampaignContact.status == status_filter)
    total = q.count()
    items = q.order_by(CampaignContact.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "items": [CampaignContactOut.model_validate(cc) for cc in items],
        "total": total, "page": page, "limit": limit,
    }


@router.post("/outreach/{cc_id}/approve")
def approve_outreach(
    cc_id: UUID,
    payload: ApproveOutreachRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cc = db.query(CampaignContact).filter(CampaignContact.id == cc_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Campaign contact not found")
    if payload.edit_body:
        cc.ai_draft = payload.edit_body
    cc.status = "approved"
    db.commit()
    return {"status": "approved"}


@router.post("/outreach/{cc_id}/send")
def send_outreach(
    cc_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from app.services.outreach_sender import send_outreach_message
    cc = db.query(CampaignContact).filter(CampaignContact.id == cc_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Campaign contact not found")
    if not cc.ai_draft:
        raise HTTPException(status_code=400, detail="No draft available. Generate drafts first.")
    try:
        msg = send_outreach_message(db, cc_id, cc.ai_draft)
        return {"sent": True, "message_id": str(msg.id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outreach/{cc_id}/reject")
def reject_outreach(
    cc_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cc = db.query(CampaignContact).filter(CampaignContact.id == cc_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Not found")
    cc.status = "not_interested"
    db.commit()
    return {"status": "not_interested"}


@router.patch("/outreach/{cc_id}/interest")
def set_interest(
    cc_id: UUID,
    payload: SetInterestRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if payload.status not in ("interested", "not_interested"):
        raise HTTPException(status_code=400, detail="status must be 'interested' or 'not_interested'")
    cc = db.query(CampaignContact).filter(CampaignContact.id == cc_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Not found")
    cc.status = payload.status
    db.commit()
    return {"status": payload.status}


@router.get("/outreach/{cc_id}/thread", response_model=OutreachThreadOut)
def get_thread(
    cc_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    thread = db.query(OutreachThread).filter(
        OutreachThread.campaign_contact_id == cc_id
    ).options(joinedload(OutreachThread.messages)).first()
    if not thread:
        raise HTTPException(status_code=404, detail="No thread yet for this contact")
    return OutreachThreadOut.model_validate(thread)


@router.post("/outreach/{cc_id}/reply")
def send_manual_reply(
    cc_id: UUID,
    payload: ApproveOutreachRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Send a manual reply in an existing thread."""
    from app.services.outreach_sender import send_outreach_message
    if not payload.edit_body:
        raise HTTPException(status_code=400, detail="edit_body is required")
    cc = db.query(CampaignContact).filter(CampaignContact.id == cc_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        msg = send_outreach_message(db, cc_id, payload.edit_body)
        return {"sent": True, "message_id": str(msg.id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outreach/{cc_id}/generate-reply")
def generate_ai_reply(
    cc_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Generate an AI reply draft for the latest inbound message."""
    from app.services.outreach_ai_service import generate_reply
    cc = db.query(CampaignContact).options(joinedload(CampaignContact.campaign)).filter(CampaignContact.id == cc_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Not found")
    thread = db.query(OutreachThread).filter(OutreachThread.campaign_contact_id == cc_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="No thread found")
    last_inbound = db.query(OutreachMessage).filter(
        OutreachMessage.thread_id == thread.id,
        OutreachMessage.direction == "inbound",
    ).order_by(OutreachMessage.created_at.desc()).first()
    if not last_inbound:
        raise HTTPException(status_code=400, detail="No inbound message to reply to")
    reply = generate_reply(db, thread, last_inbound.content, cc.campaign)
    return {"draft": reply}


# ── Analytics ──────────────────────────────────────────────────────────────────

@router.get("/analytics/dashboard", response_model=LeadGenAnalyticsOut)
def lead_gen_analytics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    total_companies = db.query(ProspectCompany).count()
    total_contacts  = db.query(ProspectContact).count()
    active_campaigns = db.query(OutreachCampaign).filter(OutreachCampaign.status == "active").count()

    cc_q = db.query(CampaignContact)
    messages_sent    = cc_q.filter(CampaignContact.status.in_(["sent","replied","interested","not_interested"])).count()
    replies_received = cc_q.filter(CampaignContact.status.in_(["replied","interested"])).count()
    interested_leads = cc_q.filter(CampaignContact.status == "interested").count()

    reply_rate_pct    = round(replies_received / messages_sent * 100, 1) if messages_sent else 0.0
    interest_rate_pct = round(interested_leads / replies_received * 100, 1) if replies_received else 0.0

    funnel = [
        {"stage": "Companies Found",  "count": total_companies},
        {"stage": "Contacts Found",   "count": total_contacts},
        {"stage": "Added to Campaigns", "count": db.query(CampaignContact).count()},
        {"stage": "Messages Sent",    "count": messages_sent},
        {"stage": "Replied",          "count": replies_received},
        {"stage": "Interested",       "count": interested_leads},
    ]

    campaigns = db.query(OutreachCampaign).limit(10).all()
    top_campaigns = []
    for c in campaigns:
        sent_c    = db.query(CampaignContact).filter(CampaignContact.campaign_id == c.id, CampaignContact.status.in_(["sent","replied","interested","not_interested"])).count()
        replied_c = db.query(CampaignContact).filter(CampaignContact.campaign_id == c.id, CampaignContact.status.in_(["replied","interested"])).count()
        top_campaigns.append({
            "id": str(c.id), "name": c.name, "status": c.status,
            "sent": sent_c, "replied": replied_c,
            "reply_rate": round(replied_c / sent_c * 100, 1) if sent_c else 0.0,
        })
    top_campaigns.sort(key=lambda x: x["reply_rate"], reverse=True)

    return LeadGenAnalyticsOut(
        total_companies=total_companies,
        total_contacts=total_contacts,
        active_campaigns=active_campaigns,
        messages_sent=messages_sent,
        replies_received=replies_received,
        interested_leads=interested_leads,
        reply_rate_pct=reply_rate_pct,
        interest_rate_pct=interest_rate_pct,
        funnel=funnel,
        top_campaigns=top_campaigns,
    )
