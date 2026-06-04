import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.schema.deal import DealAnalyticsResponse, RevenueBreakdown, StageBreakdown

from app.models.company import Company
from app.models.deal import Deal
from app.schema.deal import DealCreate, DealUpdate

logger = logging.getLogger("rdl_app_logger")


def create_deal(db: Session, payload: DealCreate, owner_id: UUID) -> Deal:
    if not db.query(Company).filter(Company.id == payload.company_id).first():
        raise ValueError("Company not found")
    deal = Deal(owner_id=owner_id, **payload.model_dump(exclude_none=True))
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


def get_deal(db: Session, deal_id: UUID) -> Optional[Deal]:
    return db.query(Deal).filter(Deal.id == deal_id).first()


def list_deals(
    db: Session,
    page: int = 1,
    limit: int = 20,
    stage: Optional[str] = None,
    company_id: Optional[UUID] = None,
    owner_id_filter: Optional[UUID] = None,
) -> Tuple[List[Deal], int]:
    q = db.query(Deal)
    if owner_id_filter is not None:
        q = q.filter(Deal.owner_id == owner_id_filter)
    if stage:
        q = q.filter(Deal.stage == stage)
    if company_id:
        q = q.filter(Deal.company_id == company_id)
    total = q.count()
    items = q.order_by(Deal.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return items, total


def update_deal(db: Session, deal_id: UUID, payload: DealUpdate) -> Optional[Deal]:
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        return None

    prev_stage = deal.stage
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(deal, field, value)

    # Stamp closed_at when deal moves into a terminal stage
    if payload.stage in ("Closed Won", "Closed Lost") and prev_stage not in ("Closed Won", "Closed Lost"):
        deal.closed_at = datetime.utcnow()

    db.commit()
    db.refresh(deal)

    stage_changed = payload.stage is not None and payload.stage != prev_stage

    # Recalculate lead score when stage or probability changes
    if deal.lead_id and (stage_changed or payload.win_probability is not None):
        try:
            from app.services.lead_scoring_service import update_lead_score
            update_lead_score(db, deal.lead_id)
        except Exception as e:
            logger.warning(f"[DEAL] Lead score update failed: {e}")

    # Auto-schedule meeting when stage moves into a positive signal
    if stage_changed and deal.lead_id:
        try:
            from app.services.deal_signal_service import evaluate_deal_signal
            from app.models.leads import Lead
            lead = db.query(Lead).filter(Lead.id == deal.lead_id).first()
            if lead and lead.email and evaluate_deal_signal(db, deal):
                from app.services.calendar_service import create_meeting, find_next_free_slot
                from app.models.calendar_event import EventTrigger
                slot = find_next_free_slot(hours_from_now=24)
                create_meeting(
                    db=db,
                    attendee_email=lead.email,
                    title=f"Sales Discussion — {deal.deal_name}",
                    description=(
                        f"Deal stage updated to '{deal.stage}'.\n"
                        f"Win probability: {deal.win_probability}%\n"
                        f"Deal value: ₹{deal.deal_value}"
                    ),
                    start_time=slot,
                    owner_id=deal.owner_id,  # event inherits the deal's owner
                    duration_minutes=30,
                    trigger=EventTrigger.DEAL_SIGNAL,
                    lead_id=deal.lead_id,
                    deal_id=deal.id,
                )
                logger.info(f"[DEAL] Auto-scheduled meeting for deal '{deal.deal_name}' (stage → {deal.stage})")
        except Exception as e:
            logger.warning(f"[DEAL] Auto-schedule on stage change failed: {e}")

    return deal


def delete_deal(db: Session, deal_id: UUID) -> bool:
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        return False
    db.delete(deal)
    db.commit()
    return True


def get_analytics(db: Session, owner_id_filter: Optional[UUID] = None) -> DealAnalyticsResponse:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (month_start.replace(month=month_start.month - 1) if month_start.month > 1
                        else month_start.replace(year=month_start.year - 1, month=12))
    quarter_month = ((now.month - 1) // 3) * 3 + 1
    quarter_start = now.replace(month=quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    q = db.query(Deal)
    if owner_id_filter is not None:
        q = q.filter(Deal.owner_id == owner_id_filter)
    all_deals = q.all()
    total_deals = len(all_deals)

    terminal = {"Closed Won", "Closed Lost"}
    open_deals = [d for d in all_deals if d.stage not in terminal]
    won_deals = [d for d in all_deals if d.stage == "Closed Won"]
    lost_deals = [d for d in all_deals if d.stage == "Closed Lost"]

    total_open_value = float(sum(d.deal_value or 0 for d in open_deals))
    total_won_value = float(sum(d.deal_value or 0 for d in won_deals))
    avg_deal_size = total_open_value / len(open_deals) if open_deals else 0.0

    closed_count = len(won_deals) + len(lost_deals)
    win_rate = (len(won_deals) / closed_count * 100) if closed_count else 0.0

    # Avg sales cycle: days from created_at to closed_at for won deals
    cycles = [
        (d.closed_at - d.created_at).days
        for d in won_deals
        if d.closed_at and d.created_at
    ]
    avg_sales_cycle_days = sum(cycles) / len(cycles) if cycles else 0.0

    # Pipeline velocity = (open_deals × win_rate × avg_deal_size) / avg_cycle_days
    pipeline_velocity = (
        (len(open_deals) * (win_rate / 100) * avg_deal_size / avg_sales_cycle_days)
        if avg_sales_cycle_days > 0 else 0.0
    )

    # By-stage breakdown
    stage_map: dict[str, StageBreakdown] = {}
    for d in all_deals:
        key = d.stage or "Unknown"
        if key not in stage_map:
            stage_map[key] = StageBreakdown(count=0, total_value=0.0)
        stage_map[key].count += 1
        stage_map[key].total_value += float(d.deal_value or 0)

    def _won_in(start, end):
        return float(sum(
            d.deal_value or 0 for d in won_deals
            if d.closed_at and start <= d.closed_at.replace(tzinfo=timezone.utc) < end
        ))

    revenue = RevenueBreakdown(
        this_month=_won_in(month_start, now),
        last_month=_won_in(last_month_start, month_start),
        this_quarter=_won_in(quarter_start, now),
        ytd=_won_in(year_start, now),
    )

    return DealAnalyticsResponse(
        total_deals=total_deals,
        open_deals=len(open_deals),
        total_open_value=total_open_value,
        avg_deal_size=avg_deal_size,
        total_won=len(won_deals),
        total_lost=len(lost_deals),
        total_won_value=total_won_value,
        win_rate=round(win_rate, 2),
        avg_sales_cycle_days=round(avg_sales_cycle_days, 1),
        pipeline_velocity=round(pipeline_velocity, 2),
        by_stage=stage_map,
        revenue=revenue,
    )
