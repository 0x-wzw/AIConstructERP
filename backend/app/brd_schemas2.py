"""Pydantic v2 schemas for Module 2 (e-bidding/auction/addendum),
Module 3 (final account), Module 5 (cost benchmarking), Module 7 (reports),
and AI chat persistence.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

ORM = ConfigDict(from_attributes=True)


# ── Tender Addendum (Module 2) ────────────────────────────────────────
class TenderAddendumBase(BaseModel):
    tender_id: int
    addendum_no: str = ""
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    reason: str = ""


class TenderAddendumCreate(TenderAddendumBase):
    pass


class TenderAddendumUpdate(BaseModel):
    addendum_no: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    reason: Optional[str] = None


class TenderAddendumRead(TenderAddendumBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    issued_at: Optional[datetime] = None


# ── Reverse Auction (Module 2) ────────────────────────────────────────
class ReverseAuctionBase(BaseModel):
    tender_id: int
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reserve_price: float = Field(default=0, ge=0)
    decrement_step: float = Field(default=0, ge=0)
    status: str = "scheduled"


class ReverseAuctionCreate(ReverseAuctionBase):
    pass


class ReverseAuctionUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reserve_price: Optional[float] = Field(default=None, ge=0)
    decrement_step: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None


class ReverseAuctionRead(ReverseAuctionBase):
    model_config = ORM
    id: int
    leading_vendor_id: Optional[int] = None
    leading_amount: float = 0
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Auction Bid (Module 2) ────────────────────────────────────────────
class AuctionBidBase(BaseModel):
    auction_id: int
    vendor_id: Optional[int] = None
    bid_amount: float = Field(ge=0)


class AuctionBidCreate(AuctionBidBase):
    pass


class AuctionBidRead(AuctionBidBase):
    model_config = ORM
    id: int
    is_leading: bool = False
    placed_at: Optional[datetime] = None


# ── Final Account (Module 3) ───────────────────────────────────────────
class FinalAccountBase(BaseModel):
    project_id: Optional[int] = None
    vendor_id: Optional[int] = None
    account_no: str = ""
    original_contract_sum: float = Field(default=0, ge=0)
    variation_orders_total: float = Field(default=0, ge=0)
    approved_claims_total: float = Field(default=0, ge=0)
    retention_released: float = Field(default=0, ge=0)
    final_amount: float = Field(default=0, ge=0)
    status: str = "draft"


class FinalAccountCreate(FinalAccountBase):
    pass


class FinalAccountUpdate(BaseModel):
    project_id: Optional[int] = None
    vendor_id: Optional[int] = None
    account_no: Optional[str] = None
    original_contract_sum: Optional[float] = Field(default=None, ge=0)
    variation_orders_total: Optional[float] = Field(default=None, ge=0)
    approved_claims_total: Optional[float] = Field(default=None, ge=0)
    retention_released: Optional[float] = Field(default=None, ge=0)
    final_amount: Optional[float] = Field(default=None, ge=0)
    status: Optional[str] = None


class FinalAccountRead(FinalAccountBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Cost Benchmark (Module 5) ─────────────────────────────────────────
class CostBenchmarkBase(BaseModel):
    project_id: Optional[int] = None
    category: str = Field(min_length=1, max_length=120)
    unit: str = ""
    cost_per_unit: float = Field(default=0, ge=0)
    benchmark_type: str = "actual"
    region: str = ""
    notes: str = ""


class CostBenchmarkCreate(CostBenchmarkBase):
    pass


class CostBenchmarkUpdate(BaseModel):
    project_id: Optional[int] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    cost_per_unit: Optional[float] = Field(default=None, ge=0)
    benchmark_type: Optional[str] = None
    region: Optional[str] = None
    notes: Optional[str] = None


class CostBenchmarkRead(CostBenchmarkBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Rate Item (Module 5) ───────────────────────────────────────────────
class RateItemBase(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    unit: str = ""
    standard_rate: float = Field(default=0, ge=0)
    lowest_rate: float = Field(default=0, ge=0)
    highest_rate: float = Field(default=0, ge=0)
    average_rate: float = Field(default=0, ge=0)
    source: str = ""


class RateItemCreate(RateItemBase):
    pass


class RateItemUpdate(BaseModel):
    description: Optional[str] = None
    unit: Optional[str] = None
    standard_rate: Optional[float] = Field(default=None, ge=0)
    lowest_rate: Optional[float] = Field(default=None, ge=0)
    highest_rate: Optional[float] = Field(default=None, ge=0)
    average_rate: Optional[float] = Field(default=None, ge=0)
    source: Optional[str] = None


class RateItemRead(RateItemBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Report Template (Module 7) ────────────────────────────────────────
class ReportTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    report_type: str = "custom"
    config: str = ""
    created_by: str = ""


class ReportTemplateCreate(ReportTemplateBase):
    pass


class ReportTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    report_type: Optional[str] = None
    config: Optional[str] = None
    created_by: Optional[str] = None


class ReportTemplateRead(ReportTemplateBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Email Reminder (Module 7) ──────────────────────────────────────────
class EmailReminderBase(BaseModel):
    entity_type: str = ""
    entity_id: Optional[int] = None
    recipient_email: str = ""
    subject: str = ""
    body: str = ""
    reminder_date: Optional[datetime] = None
    status: str = "pending"


class EmailReminderCreate(EmailReminderBase):
    pass


class EmailReminderUpdate(BaseModel):
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    reminder_date: Optional[datetime] = None
    status: Optional[str] = None


class EmailReminderRead(EmailReminderBase):
    model_config = ORM
    id: int
    sent_at: Optional[datetime] = None
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Chat Session (AI) ─────────────────────────────────────────────────
class ChatSessionBase(BaseModel):
    title: str = "New Conversation"


class ChatSessionCreate(ChatSessionBase):
    pass


class ChatSessionRead(ChatSessionBase):
    model_config = ORM
    id: int
    user_id: Optional[int] = None
    is_archived: bool = False
    created_at: Optional[datetime] = None


# ── Chat Message (AI) ─────────────────────────────────────────────────
class ChatMessageBase(BaseModel):
    session_id: int
    role: str = Field(min_length=1, max_length=20)
    content: str = Field(min_length=1)


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessageRead(ChatMessageBase):
    model_config = ORM
    id: int
    created_at: Optional[datetime] = None