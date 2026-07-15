"""SQLAlchemy ORM models — the ConstructERP domain schema.

Money is stored as NUMERIC(14,2). Enum-like fields (status, trade, color) are
plain strings validated at the Pydantic layer so the schema stays portable
across SQLite and PostgreSQL.

Multi-tenancy: every domain model has an optional tenant_id FK. When the
authenticated user has a tenant_id, the CRUD factory auto-filters reads by it
and stamps creates with it. Admins (tenant_id=None) see all tenants.

Soft delete: domain models have an is_archived flag. The CRUD factory's
delete endpoint sets is_archived=True instead of removing the row. List
endpoints exclude archived rows by default.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# ── BRD Module 1: Vendor Management ──────────────────────────────────

class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    registration_no: Mapped[str] = mapped_column(String(100), default="")
    category: Mapped[str] = mapped_column(String(100), default="")  # trade/scope
    contact_person: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(60), default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)  # pending|qualified|suspended|blacklisted
    rating: Mapped[int] = mapped_column(Integer, default=0)  # 0-5 performance rating
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── BRD Module 2: Tender Management ───────────────────────────────────

class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)  # draft|published|closed|awarded|cancelled
    tender_type: Mapped[str] = mapped_column(String(30), default="public")  # public|selective|direct
    submission_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    awarded_vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )
    awarded_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BOQItem(Base):
    __tablename__ = "boq_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tender_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"), nullable=True, index=True
    )
    item_no: Mapped[str] = mapped_column(String(30), default="")
    description: Mapped[str] = mapped_column(String(500), default="")
    unit: Mapped[str] = mapped_column(String(40), default="")
    quantity: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    rate: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class TenderBid(Base):
    __tablename__ = "tender_bids"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )
    bid_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    technical_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="submitted")  # submitted|technical_pass|technical_fail|awarded|rejected
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TenderAddendum(Base):
    """Addendum management — amendments to tender documents after publication."""
    __tablename__ = "tender_addenda"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    addendum_no: Mapped[str] = mapped_column(String(30), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(String(500), default="")  # clarification|scope_change|deadline_extension|correction
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class ReverseAuction(Base):
    """Reverse e-auction — vendors compete by submitting progressively lower bids."""
    __tablename__ = "reverse_auctions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    tender_id: Mapped[int] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reserve_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    decrement_step: Mapped[float] = mapped_column(Numeric(14, 2), default=0)  # minimum decrement per bid
    status: Mapped[str] = mapped_column(String(30), default="scheduled", index=True)  # scheduled|active|closed|cancelled
    leading_vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )
    leading_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuctionBid(Base):
    """Individual bid placed during a reverse e-auction."""
    __tablename__ = "auction_bids"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    auction_id: Mapped[int] = mapped_column(
        ForeignKey("reverse_auctions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )
    bid_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_leading: Mapped[bool] = mapped_column(Boolean, default=False)
    placed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── BRD Module 3: Contract Management ─────────────────────────────────

class ProgressClaim(Base):
    __tablename__ = "progress_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )
    claim_no: Mapped[str] = mapped_column(String(60), default="")
    period: Mapped[str] = mapped_column(String(30), default="")  # e.g. "Jan 2026"
    claim_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    certified_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="submitted", index=True)  # submitted|certified|rejected|paid
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaymentCertificate(Base):
    __tablename__ = "payment_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )
    certificate_no: Mapped[str] = mapped_column(String(60), default="")
    claim_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("progress_claims.id", ondelete="SET NULL"), nullable=True
    )
    gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    retention_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)  # pending|issued|paid
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FinalAccount(Base):
    """Final account management — settlement of all financial obligations at contract close."""
    __tablename__ = "final_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True
    )
    account_no: Mapped[str] = mapped_column(String(60), default="")
    original_contract_sum: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    variation_orders_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    approved_claims_total: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    retention_released: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    final_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)  # draft|submitted|agreed|finalized|disputed
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── BRD Module 4: Consultant Management ───────────────────────────────

class Consultant(Base):
    __tablename__ = "consultants"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    firm: Mapped[str] = mapped_column(String(200), default="")
    discipline: Mapped[str] = mapped_column(String(100), default="")  # architect|m&e|structural|civil|qs
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)  # active|shortlisted|appointed|terminated
    appointment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── BRD Module 6: Project CDE ─────────────────────────────────────────

class Submittal(Base):
    __tablename__ = "submittals"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    submittal_no: Mapped[str] = mapped_column(String(60), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="submitted", index=True)  # submitted|under_review|approved|rejected|resubmit
    submitted_by: Mapped[str] = mapped_column(String(200), default="")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Defect(Base):
    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    defect_no: Mapped[str] = mapped_column(String(60), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(300), default="")
    severity: Mapped[str] = mapped_column(String(20), default="minor", index=True)  # minor|moderate|major|critical
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)  # open|in_progress|resolved|closed
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    inspection_no: Mapped[str] = mapped_column(String(60), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    inspector: Mapped[str] = mapped_column(String(200), default="")
    result: Mapped[str] = mapped_column(String(30), default="pending", index=True)  # pending|pass|fail|conditional
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SiteDiary(Base):
    __tablename__ = "site_diaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    diary_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    weather: Mapped[str] = mapped_column(String(100), default="")
    manpower: Mapped[int] = mapped_column(Integer, default=0)
    work_summary: Mapped[str] = mapped_column(Text, default="")
    issues: Mapped[str] = mapped_column(Text, default="")
    prepared_by: Mapped[str] = mapped_column(String(200), default="")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── BRD Module 8: Procurement Pipeline ────────────────────────────────

class CostCode(Base):
    __tablename__ = "cost_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    request_no: Mapped[str] = mapped_column(String(60), default="")
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    estimated_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)  # draft|submitted|approved|rejected|converted
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RFQ(Base):
    __tablename__ = "rfqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    purchase_request_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("purchase_requests.id", ondelete="SET NULL"), nullable=True
    )
    rfq_no: Mapped[str] = mapped_column(String(60), default="")
    description: Mapped[str] = mapped_column(String(500), default="")
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)  # open|closed|awarded|cancelled
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True
    )
    receipt_no: Mapped[str] = mapped_column(String(60), default="")
    received_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    quantity_received: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    condition: Mapped[str] = mapped_column(String(30), default="good")  # good|damaged|partial
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)  # pending|accepted|rejected
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EInvoice(Base):
    __tablename__ = "e_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True
    )
    invoice_no: Mapped[str] = mapped_column(String(60), default="", index=True)
    vendor_name: Mapped[str] = mapped_column(String(200), default="")
    invoice_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)  # draft|submitted|validated|rejected|paid
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── BRD Module 5: Cost Data Management ─────────────────────────────────

class CostBenchmark(Base):
    """Project cost benchmarking — compare cost per unit across projects."""
    __tablename__ = "cost_benchmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(120), index=True)
    unit: Mapped[str] = mapped_column(String(40), default="")
    cost_per_unit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    benchmark_type: Mapped[str] = mapped_column(String(30), default="actual")  # actual|planned|industry
    region: Mapped[str] = mapped_column(String(100), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RateItem(Base):
    """Rate analysis — standard rates for cross-project comparison."""
    __tablename__ = "rate_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(String(500), index=True)
    unit: Mapped[str] = mapped_column(String(40), default="")
    standard_rate: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    lowest_rate: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    highest_rate: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    average_rate: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    source: Mapped[str] = mapped_column(String(200), default="")  # which tender/project
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── BRD Module 7: Project Reports ──────────────────────────────────────

class ReportTemplate(Base):
    """User-customizable report templates."""
    __tablename__ = "report_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    report_type: Mapped[str] = mapped_column(String(50), default="custom")  # budget|progress|procurement|vendor|custom
    config: Mapped[str] = mapped_column(Text, default="")  # JSON config: filters, columns, group_by
    created_by: Mapped[str] = mapped_column(String(200), default="")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EmailReminder(Base):
    """Automated email reminder scheduling."""
    __tablename__ = "email_reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), default="")  # tender|claim|po|inspection
    entity_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    reminder_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|sent|cancelled|failed
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── AI Chat History ────────────────────────────────────────────────────

class ChatSession(Base):
    """AI chat conversation sessions — persisted per user."""
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="New Conversation")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChatMessage(Base):
    """Individual messages within a chat session."""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # user|assistant|system
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    """Immutable record of every create/update/delete action."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_email: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(20), index=True)  # create|update|delete|archive
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    summary: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    location: Mapped[str] = mapped_column(String(300), default="")
    budget: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    duration: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tasks: Mapped[List["Task"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    start: Mapped[int] = mapped_column(Integer, default=0)   # timeline offset, %
    width: Mapped[int] = mapped_column(Integer, default=20)  # duration span, %
    color: Mapped[str] = mapped_column(String(20), default="amber")
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    project: Mapped[Optional["Project"]] = relationship(back_populates="tasks")


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(20), index=True)  # labor|equipment|materials
    name: Mapped[str] = mapped_column(String(200))
    required: Mapped[int] = mapped_column(Integer, default=0)
    available: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(40), default="")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class BudgetItem(Base):
    __tablename__ = "budget_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(120), index=True)
    budget: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    committed: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    spent: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    po_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    supplier: Mapped[str] = mapped_column(String(200))
    item: Mapped[str] = mapped_column(String(200))
    qty: Mapped[str] = mapped_column(String(60), default="")
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="Pending", index=True)
    delivery: Mapped[str] = mapped_column(String(60), default="TBD")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Subcontractor(Base):
    __tablename__ = "subcontractors"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), index=True)
    initials: Mapped[str] = mapped_column(String(4), default="")
    trade: Mapped[str] = mapped_column(String(60), default="General")
    contract: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="Active")
    color: Mapped[str] = mapped_column(String(60), default="from-slate-500 to-slate-600")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class ChangeOrder(Base):
    __tablename__ = "change_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    cost_impact: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    schedule_impact: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(30), default="Pending")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class FileUpload(Base):
    __tablename__ = "file_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    storage_path: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(50), default="")
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    ocr_processed: Mapped[bool] = mapped_column(default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="viewer", index=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())