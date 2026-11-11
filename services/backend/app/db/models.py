from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)


class Membership(Base):
    __tablename__ = "memberships"
    user_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"))
    role: Mapped[str] = mapped_column(String(20), default="owner")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("merchant_id", "phone"),)
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=uid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(30))
    language: Mapped[str] = mapped_column(String(10), default="en")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    price_paise: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(50))
    options: Mapped[dict] = mapped_column(JSON, default=dict)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    status: Mapped[str] = mapped_column(String(40))
    delivery_status: Mapped[str] = mapped_column(String(40))
    total_paise: Mapped[int] = mapped_column(Integer)
    paid_paise: Mapped[int] = mapped_column(Integer, default=0)
    refunded_paise: Mapped[int] = mapped_column(Integer, default=0)
    customizations: Mapped[list] = mapped_column(JSON, default=list)
    inventory_reserved: Mapped[bool] = mapped_column(Boolean, default=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("merchant_id", "version"),)
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=uid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    rules: Mapped[dict] = mapped_column(JSON)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=uid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    handoff: Mapped[bool] = mapped_column(Boolean, default=False)
    channel: Mapped[str] = mapped_column(String(20), default="demo")
    last_inbound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="saved")
    provider_id: Mapped[str | None] = mapped_column(String(200), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=uid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="pending_seller")
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    policy_version: Mapped[int] = mapped_column(Integer)
    seller_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    quote_paise: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PickupSlot(Base):
    __tablename__ = "pickup_slots"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"))
    label: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(200))
    capacity: Mapped[int] = mapped_column(Integer, default=5)
    reserved: Mapped[int] = mapped_column(Integer, default=0)


class Reservation(Base):
    __tablename__ = "reservations"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), unique=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    slot_id: Mapped[str] = mapped_column(ForeignKey("pickup_slots.id"))
    code_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="reserved")
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), unique=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    amount_paise: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(30), default="mock")
    status: Mapped[str] = mapped_column(String(30), default="succeeded")


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=uid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    object_key: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(200))
    mime_type: Mapped[str] = mapped_column(String(60))
    assessment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=uid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    author: Mapped[str] = mapped_column(String(120))
    rating: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(30), default="demo")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=uid)
    merchant_id: Mapped[str] = mapped_column(String(50), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
