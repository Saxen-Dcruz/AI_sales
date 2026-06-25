from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.api.dependencies import get_current_user, get_db
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.schema.email_template import (
    EmailTemplateCreate, EmailTemplateListResponse,
    EmailTemplateOut, EmailTemplateUpdate,
)

router = APIRouter(prefix="/email-templates", tags=["Email Templates"])


def _visible_filter(q, current_user: User):
    """Return templates owned by this user OR shared global ones (owner_id IS NULL)."""
    if current_user.is_superuser:
        return q
    return q.filter(
        (EmailTemplate.owner_id == current_user.id) | (EmailTemplate.owner_id.is_(None))
    )


@router.get("/", response_model=EmailTemplateListResponse)
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = _visible_filter(db.query(EmailTemplate), current_user)
    items = q.order_by(EmailTemplate.name).all()
    return EmailTemplateListResponse(items=items, total=len(items))


@router.post("/", response_model=EmailTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Super-admins create global templates (owner_id=None); others own their templates.
    owner_id = None if current_user.is_superuser else current_user.id
    tpl = EmailTemplate(owner_id=owner_id, name=payload.name,
                        subject=payload.subject, body=payload.body)
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.get("/{template_id}", response_model=EmailTemplateOut)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if not current_user.is_superuser and tpl.owner_id and tpl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return tpl


@router.patch("/{template_id}", response_model=EmailTemplateOut)
def update_template(
    template_id: UUID,
    payload: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if not current_user.is_superuser and tpl.owner_id and tpl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tpl, field, value)
    tpl.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if not current_user.is_superuser and tpl.owner_id and tpl.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    db.delete(tpl)
    db.commit()
