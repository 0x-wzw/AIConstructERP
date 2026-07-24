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
    UniqueConstraint,
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

    # ── Malaysia LHDN MyInvois fields ────────────────────────────────
    # document_type: 01 Invoice, 02 Credit, 03 Debit, 04 Refund,
    #                11-14 self-billed variants.
    document_type: Mapped[str] = mapped_column(String(2), default="01")
    document_version: Mapped[str] = mapped_column(String(5), default="1.1")
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    exchange_rate: Mapped[float] = mapped_column(Numeric(14, 6), default=1)
    # Supplier (issuer) identity — required by LHDN.
    supplier_tin: Mapped[str] = mapped_column(String(20), default="")
    supplier_reg_no: Mapped[str] = mapped_column(String(30), default="")  # BRN/NRIC/passport
    supplier_sst: Mapped[str] = mapped_column(String(35), default="")
    supplier_msic: Mapped[str] = mapped_column(String(5), default="")
    # Buyer identity.
    buyer_tin: Mapped[str] = mapped_column(String(20), default="")
    buyer_reg_no: Mapped[str] = mapped_column(String(30), default="")
    buyer_name: Mapped[str] = mapped_column(String(200), default="")
    # MyInvois clearance results.
    myinvois_status: Mapped[str] = mapped_column(String(20), default="not_submitted", index=True)
    # not_submitted | submitting | submitted | valid | invalid | cancelled
    myinvois_uuid: Mapped[str] = mapped_column(String(40), default="", index=True)
    myinvois_long_id: Mapped[str] = mapped_column(String(80), default="")
    submission_uid: Mapped[str] = mapped_column(String(40), default="")
    validation_link: Mapped[str] = mapped_column(String(500), default="")  # QR target
    myinvois_error: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancel_reason: Mapped[str] = mapped_column(String(300), default="")

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    lines: Mapped[List["EInvoiceLine"]] = relationship(
        "EInvoiceLine", cascade="all, delete-orphan", back_populates="e_invoice"
    )


class EInvoiceLine(Base):
    """A single e-invoice line item. MyInvois validates per line, so each line
    carries its own classification code and tax breakdown."""
    __tablename__ = "e_invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    e_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("e_invoices.id", ondelete="CASCADE"), index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, default=1)
    classification_code: Mapped[str] = mapped_column(String(5), default="")  # MyInvois class code
    description: Mapped[str] = mapped_column(String(300), default="")
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    measurement: Mapped[str] = mapped_column(String(10), default="")  # UN/ECE unit code
    tax_type: Mapped[str] = mapped_column(String(10), default="")  # 01 sales, 02 service, E exempt...
    tax_rate: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    discount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    e_invoice: Mapped["EInvoice"] = relationship("EInvoice", back_populates="lines")


class MyInvoisConfig(Base):
    """Per-tenant MyInvois connection + issuer identity.

    One row per tenant. The client secret is stored ENCRYPTED (see
    einvoice.secrets); it is never returned by the API in cleartext.
    """
    __tablename__ = "myinvois_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, unique=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    environment: Mapped[str] = mapped_column(String(12), default="sandbox")  # sandbox|production
    # Issuer (this tenant, as supplier) identity.
    tin: Mapped[str] = mapped_column(String(20), default="")
    registration_no: Mapped[str] = mapped_column(String(30), default="")
    sst_no: Mapped[str] = mapped_column(String(35), default="")
    msic_code: Mapped[str] = mapped_column(String(5), default="")
    business_activity: Mapped[str] = mapped_column(String(300), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    address_line: Mapped[str] = mapped_column(String(300), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    state_code: Mapped[str] = mapped_column(String(3), default="")  # MyInvois state code
    postal_code: Mapped[str] = mapped_column(String(10), default="")
    country_code: Mapped[str] = mapped_column(String(3), default="MYS")
    # API credentials (from the MyInvois portal). Secret stored encrypted.
    client_id: Mapped[str] = mapped_column(String(100), default="")
    client_secret_enc: Mapped[str] = mapped_column(Text, default="")
    # Intermediary mode: submit on behalf of `onbehalf_tin`.
    is_intermediary: Mapped[bool] = mapped_column(Boolean, default=False)
    onbehalf_tin: Mapped[str] = mapped_column(String(20), default="")
    # Reference/alias to the signing certificate (resolved by the signer).
    cert_ref: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


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


class TenantModule(Base):
    """Per-tenant enablement of a registered module.

    Absence of a row means "use the module's default_enabled". Platform admins
    always bypass module gating (they are cross-tenant).
    """
    __tablename__ = "tenant_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    module_name: Mapped[str] = mapped_column(String(50), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "module_name", name="uq_tenant_module"),
    )


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
    # Which specific cloud container the object lives in (S3/MinIO bucket);
    # empty for the local backend.
    storage_bucket: Mapped[str] = mapped_column(String(200), default="")
    # SHA-256 of the stored bytes — integrity check + content de-duplication.
    checksum_sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    category: Mapped[str] = mapped_column(String(50), default="")
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    ocr_processed: Mapped[bool] = mapped_column(default=False)
    # ── Ingestion into system database format ────────────────────────
    # pending → processing → ingested | failed. Tracks the pipeline that turns
    # a raw file into structured domain data.
    ingest_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # Normalized fields extracted from the document (JSON, portable across
    # SQLite/Postgres — stored as Text and (de)serialized in the app layer).
    extracted_data: Mapped[str] = mapped_column(Text, default="")
    # When ingestion creates/links a domain record (e.g. an e-invoice), point
    # back to it so the file and the structured entity stay connected.
    ingested_entity_type: Mapped[str] = mapped_column(String(50), default="")
    ingested_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RawDocument(Base):
    """Landing-zone (bronze tier) manifest for unstructured documents.

    A raw document is the immutable, verbatim copy of an uploaded file as it
    landed in cloud storage, tracked *before* any ETL runs. It exists so that:
      • direct-to-cloud (pre-signed) uploads are tracked from the moment a URL
        is issued — no orphaned objects;
      • the original bytes are preserved untouched for re-processing and audit;
      • ETL state is separated from the curated FileUpload it produces.

    Lifecycle (`etl_status`):
        pending_upload → landed → extracting → extracted | failed | skipped
    `pending_upload` is only used by the pre-signed flow between URL issue and
    client confirmation. ETL promotes a landed raw doc into a curated
    FileUpload (`file_upload_id`) and, through the existing ingestion pipeline,
    a structured domain record.
    """

    __tablename__ = "raw_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # How the object arrived: upload | presign | chunked | email | api.
    source: Mapped[str] = mapped_column(String(20), default="upload")
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    # Object location within the raw landing zone.
    storage_backend: Mapped[str] = mapped_column(String(20), default="local")
    storage_bucket: Mapped[str] = mapped_column(String(200), default="")
    storage_path: Mapped[str] = mapped_column(String(500))
    checksum_sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    # Best-effort classification at landing time (refined during ETL).
    category: Mapped[str] = mapped_column(String(50), default="")
    # ETL state machine — see class docstring.
    etl_status: Mapped[str] = mapped_column(String(20), default="landed", index=True)
    etl_error: Mapped[str] = mapped_column(Text, default="")
    # Cached extracted text so re-runs don't re-OCR.
    raw_text: Mapped[str] = mapped_column(Text, default="")
    # The curated FileUpload produced by ETL (nullable until promoted).
    file_upload_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_uploads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


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