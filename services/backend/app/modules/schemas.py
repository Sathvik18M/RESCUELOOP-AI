from typing import Literal
from pydantic import BaseModel, Field


class PolicyRules(BaseModel):
    return_window_days: int = Field(7, ge=0, le=365)
    auto_refund_limit_paise: int = Field(25000, ge=0, le=10000000)
    pickup: Literal["allowed", "approval_required", "prohibited"] = "approval_required"
    engraving_requires_approval: Literal[True] = True
    cancellation_before_shipping: bool = True
    warranty_days: int = Field(365, ge=0, le=3650)
    delivery_fee_paise: int = Field(0, ge=0, le=100000)
    tax_basis_points: int = Field(0, ge=0, le=10000)


class DecisionInput(BaseModel):
    decision: Literal["approve", "reject", "request_details"]
    quote_paise: int = Field(0, ge=0, le=10000000)
    note: str = Field("", max_length=1000)
    preparation_days: int = Field(1, ge=0, le=90)


class MessageInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    message_id: str = Field(min_length=8, max_length=100)


class ProductUpdate(BaseModel):
    price_paise: int = Field(ge=0, le=100000000)
    stock: int = Field(ge=0, le=100000)


class HandoffInput(BaseModel):
    enabled: bool


class CollectionInput(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class ReviewInput(BaseModel):
    rating: int = Field(ge=1, le=5)
    body: str = Field(min_length=1, max_length=2000)


class SettingsInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=200)
    support_email: str = Field(max_length=200)


class PolicyDraftInput(BaseModel):
    instruction: str = Field(min_length=5, max_length=3000)


class CaseView(BaseModel):
    id: str
    order_id: str
    conversation_id: str
    kind: str
    status: str
    summary: str
    details: dict
    policy_version: int
    seller_approved: bool
    quote_paise: int
    expires_at: str
    created_at: str


class WorkspaceView(BaseModel):
    merchant: dict
    products: list[dict]
    orders: list[dict]
    conversations: list[dict]
    cases: list[CaseView]
    policies: list[dict]
    slots: list[dict]
    reservations: list[dict]
    reviews: list[dict]
    evidence: list[dict]
    audit_logs: list[dict]
    refunds: list[dict]
    metrics: dict
    insights: list[dict]
    mode: dict
