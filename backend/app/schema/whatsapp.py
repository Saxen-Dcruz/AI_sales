from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.schema.gmail import GapItem   # reuse same GapItem schema


# ── Account schemas ────────────────────────────────────────────────────────────

class WhatsAppAccountCreate(BaseModel):
    phone_number_id: str
    waba_id:         str
    access_token:    str
    verify_token:    str
    display_phone:   str
    display_name:    Optional[str] = None
    auto_send:       bool = False


class WhatsAppAccountUpdate(BaseModel):
    display_name:  Optional[str]  = None
    access_token:  Optional[str]  = None
    verify_token:  Optional[str]  = None
    is_active:     Optional[bool] = None
    auto_send:     Optional[bool] = None


class WhatsAppAccountOut(BaseModel):
    id:              UUID
    owner_id:        UUID
    phone_number_id: str
    waba_id:         str
    display_phone:   str
    display_name:    Optional[str]
    is_active:       bool
    is_primary:      bool
    auto_send:       bool
    created_at:      str

    class Config:
        from_attributes = True


class WhatsAppAccountListResponse(BaseModel):
    items: list[WhatsAppAccountOut]
    total: int


# ── Message schemas ────────────────────────────────────────────────────────────

class WhatsAppMessageOut(BaseModel):
    id:                    UUID
    wa_message_id:         str
    account_id:            Optional[UUID]
    account_phone:         Optional[str]
    lead_id:               Optional[UUID]
    direction:             str
    from_number:           str
    to_number:             str
    body:                  Optional[str]
    media_url:             Optional[str]
    received_at:           datetime
    label:                 str
    status:                str
    classifier_reasoning:  Optional[str]
    classifier_confidence: Optional[str]
    ai_draft:              Optional[str]
    followup_gaps:         Optional[list[Union[GapItem, dict]]] = None
    detected_product_id:   Optional[str]
    detected_product_name: Optional[str]
    competitor_mention:    Optional[str]
    needs_human:           bool
    resolved_by:           Optional[str]
    resolved_at:           Optional[datetime]
    # Phase 1: delivery tracking + message sub-type
    wa_sent_message_id:    Optional[str]    = None
    delivery_status:       Optional[str]    = None
    delivered_at:          Optional[datetime] = None
    read_at:               Optional[datetime] = None
    failed_reason:         Optional[str]    = None
    message_type:          Optional[str]    = "text"
    button_reply_id:       Optional[str]    = None
    button_reply_title:    Optional[str]    = None
    list_reply_id:         Optional[str]    = None
    list_reply_title:      Optional[str]    = None
    template_name:         Optional[str]    = None
    created_at:            datetime

    @field_validator("followup_gaps", mode="before")
    @classmethod
    def parse_gaps(cls, v):
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, dict):
                try:
                    result.append(GapItem(**item))
                except Exception:
                    result.append(item)
            else:
                result.append(item)
        return result

    class Config:
        from_attributes = True


class WhatsAppMessageListResponse(BaseModel):
    items: list[WhatsAppMessageOut]
    total: int
    page:  int
    limit: int


class WhatsAppGapNotificationOut(BaseModel):
    message_id:    UUID
    from_number:   str
    body:          Optional[str]
    received_at:   datetime
    gaps:          list[GapItem]


class WhatsAppGapNotificationListResponse(BaseModel):
    items: list[WhatsAppGapNotificationOut]
    total: int


class WAGapResolveRequest(BaseModel):
    gap_index: int
    answer:    str
    category:  Optional[str] = "general"


class WASendRequest(BaseModel):
    account_id: UUID
    to_number:  str
    body:       str


class WAApproveDraftRequest(BaseModel):
    edit_body: Optional[str] = None   # None → send original ai_draft


# ── Enhanced message out (new delivery + interactive fields) ───────────────────

class WhatsAppMessageOutV2(WhatsAppMessageOut):
    """Extends the base with delivery tracking and interactive-reply fields."""
    wa_sent_message_id: Optional[str]    = None
    delivery_status:    Optional[str]    = "sent"   # sent/delivered/read/failed
    delivered_at:       Optional[datetime] = None
    read_at:            Optional[datetime] = None
    failed_reason:      Optional[str]    = None
    message_type:       Optional[str]    = "text"
    button_reply_id:    Optional[str]    = None
    button_reply_title: Optional[str]    = None
    list_reply_id:      Optional[str]    = None
    list_reply_title:   Optional[str]    = None
    template_name:      Optional[str]    = None


# ── Template schemas ───────────────────────────────────────────────────────────

class WATemplateCreate(BaseModel):
    account_id:  UUID                    # which WA account to submit the template under
    name:        str
    language:    str = "en"
    category:    str = "UTILITY"         # MARKETING / UTILITY / AUTHENTICATION
    components:  list[dict]              # Meta component array (header/body/footer/buttons)


class WATemplateUpdate(BaseModel):
    components: list[dict]               # Only components can be edited on PENDING templates


class WATemplateOut(BaseModel):
    id:                UUID
    owner_id:          UUID
    waba_id:           str
    account_id:        Optional[UUID]
    meta_template_id:  Optional[str]
    name:              str
    language:          str
    category:          str
    status:            str
    rejection_reason:  Optional[str]
    components:        list[dict]
    created_at:        datetime
    updated_at:        datetime

    class Config:
        from_attributes = True


class WATemplateListResponse(BaseModel):
    items: list[WATemplateOut]
    total: int


class WASendTemplateRequest(BaseModel):
    """Send a stored template to a phone number with variable substitution.
    template_id comes from the URL path — not included in the body.
    """
    to_number:   str
    variables:   dict[str, str] = {}    # {variable_name: value} — substituted into {{N}} slots


# ── Interactive message schemas ────────────────────────────────────────────────

class WAButton(BaseModel):
    id:    str           # max 256 chars — used to identify which button was clicked
    title: str           # max 20 chars — displayed text on the button

    @model_validator(mode="after")
    def validate_limits(self) -> "WAButton":
        if len(self.title) > 20:
            raise ValueError("Button title must be ≤ 20 characters")
        if len(self.id) > 256:
            raise ValueError("Button id must be ≤ 256 characters")
        return self


class WAListRow(BaseModel):
    id:          str
    title:       str           # max 24 chars
    description: Optional[str] = None   # max 72 chars

    @model_validator(mode="after")
    def validate_limits(self) -> "WAListRow":
        if len(self.title) > 24:
            raise ValueError("Row title must be ≤ 24 characters")
        return self


class WAListSection(BaseModel):
    title: Optional[str] = None   # max 24 chars
    rows:  list[WAListRow]


class WASendButtonsRequest(BaseModel):
    account_id:  UUID
    to_number:   str
    body:        str                      # message body text
    buttons:     list[WAButton]           # 1–3 buttons
    header:      Optional[str] = None     # optional text header
    footer:      Optional[str] = None     # optional footer text

    @model_validator(mode="after")
    def validate_button_count(self) -> "WASendButtonsRequest":
        if not 1 <= len(self.buttons) <= 3:
            raise ValueError("Must have between 1 and 3 buttons")
        return self


class WASendListRequest(BaseModel):
    account_id:  UUID
    to_number:   str
    body:        str
    sections:    list[WAListSection]
    button_text: str = "Select"           # text on the list-open button (max 20 chars)
    header:      Optional[str] = None
    footer:      Optional[str] = None

    @model_validator(mode="after")
    def validate_row_count(self) -> "WASendListRequest":
        total = sum(len(s.rows) for s in self.sections)
        if not 1 <= total <= 10:
            raise ValueError("Total rows across all sections must be 1–10")
        if len(self.sections) > 5:
            raise ValueError("Maximum 5 sections allowed")
        return self


class WASendMediaRequest(BaseModel):
    account_id: UUID
    to_number:  str
    media_type: str        # image / document / audio / video
    url:        str        # public URL of the media file
    caption:    Optional[str] = None
    filename:   Optional[str] = None   # for document type only


class WASendReactionRequest(BaseModel):
    account_id:     UUID
    to_number:      str
    message_id:     str   # wa_message_id of the message to react to
    emoji:          str   # single emoji character


class WABusinessProfileOut(BaseModel):
    about:       Optional[str]
    address:     Optional[str]
    description: Optional[str]
    email:       Optional[str]
    websites:    list[str] = []
    vertical:    Optional[str]   # e.g. TECHNOLOGY, RETAIL


class WABusinessProfileUpdate(BaseModel):
    about:       Optional[str] = None
    address:     Optional[str] = None
    description: Optional[str] = None
    email:       Optional[str] = None
    websites:    Optional[list[str]] = None


class WAAnalytics(BaseModel):
    # Volume
    total_messages:          int
    total_inbound:           int
    total_outbound:          int
    total_sales:             int
    total_support:           int
    total_grievance:         int

    # Pipeline performance
    auto_sent:               int
    auto_sent_rate:          float          # % of Sales messages auto-replied
    drafted_for_review:      int
    pending_human:           int
    needs_human_count:       int

    # Response quality
    avg_response_time_minutes: float        # avg time from received_at → replied (inbound Sales)
    sla_breaches:            int            # Sales/Support messages unresolved for > 2 hours
    knowledge_gap_count:     int            # messages with unresolved gaps
    knowledge_gap_resolution_rate: float   # % gaps resolved across all messages

    # Competitor intelligence
    competitor_mention_count: int

    # Breakdowns
    by_label:                dict
    by_status:               dict
    by_direction:            dict           # {"inbound": N, "outbound": N}

    # Customer-level aggregations
    top_senders: list = []   # [{from_number, total, labels, last_at, lead_id, lead_name}]
    top_products: list = []  # [{name, inquiries, converted, conversion_pct}]
