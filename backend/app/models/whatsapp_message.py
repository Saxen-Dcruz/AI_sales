from datetime import datetime, timezone
import enum
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from app.database.core import Base
from app.core.utils import new_uuid


class WALabel(str, enum.Enum):
    SALES          = "Sales"
    SUPPORT        = "Support"
    GRIEVANCE      = "Grievance"
    TRANSACTIONAL  = "Transactional"
    PROMOTIONAL    = "Promotional"
    PERSONAL       = "Personal"
    UNCLASSIFIED   = "Unclassified"


class WAStatus(str, enum.Enum):
    NEW            = "new"
    CLASSIFIED     = "classified"
    DRAFT_READY    = "draft_ready"
    PENDING_HUMAN  = "pending_human"
    REPLIED        = "replied"
    ARCHIVED       = "archived"
    IGNORED        = "ignored"


class WAHumanStatus(str, enum.Enum):
    """Tracks what a human has actually done with this message in the dashboard —
    independent of `status`, which only reflects AI pipeline progress. See
    EmailHumanStatus in app/models/communication.py for the Gmail counterpart and
    full rationale. Only set by human-driven endpoints — never by the automated
    workflow."""
    UNREAD = "unread"      # default — nobody has opened this message in the dashboard
    READ = "read"          # opened, but no reply/resolution recorded yet
    REPLIED = "replied"    # a human sent or approved a reply
    RESOLVED = "resolved"  # a human resolved it without a reply (or discarded the draft)


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id              = Column(PGUUID(as_uuid=True), primary_key=True, default=new_uuid)

    # Meta message identifier (unique per message from Meta)
    wa_message_id   = Column(String, unique=True, index=True, nullable=False)

    # Which WA business account received/sent this
    account_id      = Column(PGUUID(as_uuid=True), ForeignKey("whatsapp_accounts.id", ondelete="SET NULL"),
                             nullable=True, index=True)
    account_phone   = Column(String, nullable=True)   # phone_number_id of the account

    # CRM linkage
    lead_id         = Column(PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"),
                             nullable=True, index=True)

    direction       = Column(String, nullable=False)   # "inbound" | "outbound"
    from_number     = Column(String, nullable=False)   # sender phone (+91...)
    to_number       = Column(String, nullable=False)   # recipient phone (+91...)
    body            = Column(Text, nullable=True)
    media_url       = Column(String, nullable=True)    # for image/document messages

    received_at     = Column(DateTime(timezone=True), nullable=False)

    label           = Column(Enum(WALabel),   default=WALabel.UNCLASSIFIED, index=True)
    status          = Column(Enum(WAStatus),  default=WAStatus.NEW, index=True)

    classifier_reasoning  = Column(Text, nullable=True)
    classifier_confidence = Column(String, nullable=True)

    # AI pipeline outputs
    ai_draft        = Column(Text, nullable=True)
    followup_gaps   = Column(JSON, nullable=True)   # same GapItem structure as emails

    detected_product_id   = Column(String, nullable=True)
    detected_product_name = Column(String, nullable=True)
    competitor_mention    = Column(String, nullable=True)

    needs_human     = Column(Boolean, default=False, index=True)
    resolved_by     = Column(String, nullable=True)
    resolved_at     = Column(DateTime(timezone=True), nullable=True)

    # See WAHumanStatus — the human-driven counterpart to `status`.
    human_status    = Column(Enum(WAHumanStatus), default=WAHumanStatus.UNREAD, nullable=False, index=True)

    # Delivery tracking (updated via status webhooks from Meta)
    wa_sent_message_id = Column(String, nullable=True, index=True)  # wamid from Meta send response
    delivery_status    = Column(String, default="sent", nullable=True)  # sent/delivered/read/failed
    delivered_at       = Column(DateTime(timezone=True), nullable=True)
    read_at            = Column(DateTime(timezone=True), nullable=True)
    failed_reason      = Column(String, nullable=True)

    # Sub-type of message (text/template/button/list/image/document/audio/reaction/location)
    message_type    = Column(String, default="text", nullable=True)

    # Interactive reply data (inbound — customer tapped a button or selected from list)
    button_reply_id    = Column(String, nullable=True)
    button_reply_title = Column(String, nullable=True)
    list_reply_id      = Column(String, nullable=True)
    list_reply_title   = Column(String, nullable=True)

    # Template name used (outbound template messages)
    template_name   = Column(String, nullable=True)

    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))

    lead            = relationship("Lead", backref="whatsapp_messages")
    account         = relationship("WhatsAppAccount", backref="messages", foreign_keys=[account_id])
