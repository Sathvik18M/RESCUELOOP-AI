from typing import Literal
from pydantic import BaseModel, Field, model_validator

Permission = Literal["automatic", "approval_required", "unavailable"]


class PolicyRules(BaseModel):
    return_window_days: int = Field(7, ge=0, le=365)
    auto_refund_limit_paise: int = Field(25000, ge=0, le=10000000)
    pickup: Literal["allowed", "approval_required", "prohibited"] = "approval_required"
    engraving_requires_approval: Literal[True] = True
    cancellation_before_shipping: bool = True
    warranty_days: int = Field(365, ge=0, le=3650)
    delivery_fee_paise: Literal[0] = 0
    tax_basis_points: Literal[0] = 0
    return_permission: Permission = "automatic"
    refund_permission: Permission = "automatic"
    redelivery_permission: Permission = "automatic"
    customization_permission: Permission = "approval_required"
    return_reasons: list[Literal["damaged", "defective", "incorrect_item"]] = Field(
        default_factory=lambda: ["damaged", "defective", "incorrect_item"]
    )
    require_return_inspection: bool = True
    require_photo: bool = True
    engraving_paise: int = Field(19900, ge=0, le=1000000)
    gift_wrap_paise: int = Field(14900, ge=0, le=1000000)
    preparation_days: int = Field(1, ge=0, le=90)
    proposal_hours: Literal[24] = 24


class DecisionInput(BaseModel):
    decision: Literal["approve", "reject", "request_details"]
    quote_paise: int | None = Field(None, ge=0, le=10000000)
    note: str = Field("", max_length=1000)
    preparation_days: int = Field(1, ge=0, le=90)
    waive_return: bool = False
    engraving: str | None = Field(None, max_length=40)
    gift_wrap: bool | None = None
    slot_id: str | None = Field(None, max_length=50)

    @model_validator(mode="after")
    def require_note(self):
        if (self.decision in {"reject", "request_details"} or self.waive_return) and not self.note.strip():
            raise ValueError("A reason or customer question is required")
        return self


class MessageInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    message_id: str = Field(min_length=8, max_length=100)


class HandoffInput(BaseModel):
    enabled: bool


class ProductUpdate(BaseModel):
    price_paise: int = Field(ge=0, le=100000000)
    stock: int = Field(ge=0, le=100000)


class CollectionInput(BaseModel):
    code: str | None = Field(None, pattern=r"^\d{6}$")


class PolicyDraftInput(BaseModel):
    instruction: str = Field(min_length=5, max_length=3000)


class InspectionInput(BaseModel):
    accepted: bool
    restock: bool = False
    note: str = Field(min_length=3, max_length=1000)


class ResolveInput(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


class LinkCustomerInput(BaseModel):
    customer_id: str
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")


class SettingsInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=200)
    support_email: str = Field(max_length=200)


class ReportInput(BaseModel):
    date_from: str
    date_to: str


class CaseView(BaseModel):
    id: str
    order_id: str | None
    conversation_id: str
    kind: str
    status: str
    primary_status: str
    summary: str
    details: dict
    policy_version: int
    seller_approved: bool
    seller_assisted: bool
    flag_reason: str
    resolution_attempts: int
    proposal_ref: str | None
    proposal_revision: int
    quote_paise: int
    checks: list
    expires_at: str
    created_at: str
    updated_at: str
    resolved_at: str | None
    consented_at: str | None


class WorkspaceView(BaseModel):
    merchant: dict
    products: list[dict]
    orders: list[dict]
    customers: list[dict]
    conversations: list[dict]
    cases: list[CaseView]
    policies: list[dict]
    slots: list[dict]
    reservations: list[dict]
    reviews: list[dict]
    evidence: list[dict]
    audit_logs: list[dict]
    refunds: list[dict]
    returns: list[dict]
    operations: list[dict]
    metrics: dict
    insights: list[dict]
    reports: list[dict]
    date_range: dict
    mode: dict
