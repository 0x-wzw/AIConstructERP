"""ConstructERP backend — FastAPI application entrypoint.

Provides: exception handling, request logging, lifespan, router registration.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import models, schemas
from .ai_routes import router as ai_router
from .auction_routes import router as auction_router
from .audit_routes import router as audit_router
from .auth import router as auth_router
from .brd_schemas import (
    BOQItemCreate, BOQItemRead, BOQItemUpdate,
    ConsultantCreate, ConsultantRead, ConsultantUpdate,
    CostCodeCreate, CostCodeRead, CostCodeUpdate,
    DefectCreate, DefectRead, DefectUpdate,
    EInvoiceCreate, EInvoiceRead, EInvoiceUpdate,
    GoodsReceiptCreate, GoodsReceiptRead, GoodsReceiptUpdate,
    InspectionCreate, InspectionRead, InspectionUpdate,
    PaymentCertificateCreate, PaymentCertificateRead, PaymentCertificateUpdate,
    ProgressClaimCreate, ProgressClaimRead, ProgressClaimUpdate,
    PurchaseRequestCreate, PurchaseRequestRead, PurchaseRequestUpdate,
    RFQCreate, RFQRead, RFQUpdate,
    SiteDiaryCreate, SiteDiaryRead, SiteDiaryUpdate,
    SubmittalCreate, SubmittalRead, SubmittalUpdate,
    TenderBidCreate, TenderBidRead, TenderBidUpdate,
    TenderCreate, TenderRead, TenderUpdate,
    VendorCreate, VendorRead, VendorUpdate,
)
from .brd_schemas2 import (
    CostBenchmarkCreate, CostBenchmarkRead, CostBenchmarkUpdate,
    EmailReminderCreate, EmailReminderRead, EmailReminderUpdate,
    FinalAccountCreate, FinalAccountRead, FinalAccountUpdate,
    RateItemCreate, RateItemRead, RateItemUpdate,
    ReportTemplateCreate, ReportTemplateRead, ReportTemplateUpdate,
    ReverseAuctionCreate, ReverseAuctionRead, ReverseAuctionUpdate,
    TenderAddendumCreate, TenderAddendumRead, TenderAddendumUpdate,
)
from .chat_routes import router as chat_router
from .config import settings
from .crud import generate_po_number, make_crud_router
from .database import Base, SessionLocal, engine, get_db
from .files import router as files_router
from .ocr_routes import router as ocr_router
from .sse_routes import router as sse_router
from .models import User
from .security import Role, get_current_active_user
from .tenants import router as tenants_router

logger = logging.getLogger("constructerp")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure structured logging.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)

    # Create tables and seed demo data on startup (idempotent).
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from .seed import seed_demo_users, seed_if_empty
        seed_if_empty(db)
        if settings.seed_demo_users:
            seed_demo_users(db)
    finally:
        db.close()
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="REST API for the ConstructERP construction management suite.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*"
    else [o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=settings.cors_origins != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handlers ─────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# ── Request logging middleware ────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    # Skip health checks to reduce noise.
    if request.url.path != "/api/health":
        logger.info(
            "%s %s %d %.1fms",
            request.method, request.url.path,
            response.status_code, duration_ms,
        )
    return response


# ── Resource routers (mounted under /api) ─────────────────────────────
PM = Role.project_manager.value
ACCT = Role.accounting.value

ROUTERS = [
    make_crud_router(
        model=models.Project, read_schema=schemas.ProjectRead,
        create_schema=schemas.ProjectCreate, update_schema=schemas.ProjectUpdate,
        prefix="/projects", tag="projects", search_fields=["name", "location"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.Task, read_schema=schemas.TaskRead,
        create_schema=schemas.TaskCreate, update_schema=schemas.TaskUpdate,
        prefix="/tasks", tag="tasks", search_fields=["name"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.Resource, read_schema=schemas.ResourceRead,
        create_schema=schemas.ResourceCreate, update_schema=schemas.ResourceUpdate,
        prefix="/resources", tag="resources", search_fields=["name", "category"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.BudgetItem, read_schema=schemas.BudgetItemRead,
        create_schema=schemas.BudgetItemCreate, update_schema=schemas.BudgetItemUpdate,
        prefix="/budget", tag="budget", search_fields=["category"],
        write_roles=[ACCT],
    ),
    make_crud_router(
        model=models.PurchaseOrder, read_schema=schemas.PurchaseOrderRead,
        create_schema=schemas.PurchaseOrderCreate, update_schema=schemas.PurchaseOrderUpdate,
        prefix="/purchase-orders", tag="purchase_orders",
        search_fields=["po_number", "supplier", "item"], on_create=generate_po_number,
        write_roles=[ACCT],
    ),
    make_crud_router(
        model=models.Subcontractor, read_schema=schemas.SubcontractorRead,
        create_schema=schemas.SubcontractorCreate, update_schema=schemas.SubcontractorUpdate,
        prefix="/subcontractors", tag="subcontractors", search_fields=["name", "trade"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.ChangeOrder, read_schema=schemas.ChangeOrderRead,
        create_schema=schemas.ChangeOrderCreate, update_schema=schemas.ChangeOrderUpdate,
        prefix="/change-orders", tag="change_orders", search_fields=["title"],
        write_roles=[ACCT, PM],
    ),
    # ── BRD Module 1: Vendor Management ──────────────────────────
    make_crud_router(
        model=models.Vendor, read_schema=VendorRead,
        create_schema=VendorCreate, update_schema=VendorUpdate,
        prefix="/vendors", tag="vendors", search_fields=["name", "category", "registration_no"],
        write_roles=[PM],
    ),
    # ── BRD Module 2: Tender Management ─────────────────────────
    make_crud_router(
        model=models.Tender, read_schema=TenderRead,
        create_schema=TenderCreate, update_schema=TenderUpdate,
        prefix="/tenders", tag="tenders", search_fields=["title"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.BOQItem, read_schema=BOQItemRead,
        create_schema=BOQItemCreate, update_schema=BOQItemUpdate,
        prefix="/boq-items", tag="boq_items", search_fields=["item_no", "description"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.TenderBid, read_schema=TenderBidRead,
        create_schema=TenderBidCreate, update_schema=TenderBidUpdate,
        prefix="/tender-bids", tag="tender_bids", search_fields=[],
        write_roles=[PM],
    ),
    # ── BRD Module 3: Contract Management ────────────────────────
    make_crud_router(
        model=models.ProgressClaim, read_schema=ProgressClaimRead,
        create_schema=ProgressClaimCreate, update_schema=ProgressClaimUpdate,
        prefix="/progress-claims", tag="progress_claims", search_fields=["claim_no", "period"],
        write_roles=[ACCT, PM],
    ),
    make_crud_router(
        model=models.PaymentCertificate, read_schema=PaymentCertificateRead,
        create_schema=PaymentCertificateCreate, update_schema=PaymentCertificateUpdate,
        prefix="/payment-certificates", tag="payment_certificates", search_fields=["certificate_no"],
        write_roles=[ACCT],
    ),
    # ── BRD Module 4: Consultant Management ──────────────────────
    make_crud_router(
        model=models.Consultant, read_schema=ConsultantRead,
        create_schema=ConsultantCreate, update_schema=ConsultantUpdate,
        prefix="/consultants", tag="consultants", search_fields=["name", "firm", "discipline"],
        write_roles=[PM],
    ),
    # ── BRD Module 6: Project CDE ────────────────────────────────
    make_crud_router(
        model=models.Submittal, read_schema=SubmittalRead,
        create_schema=SubmittalCreate, update_schema=SubmittalUpdate,
        prefix="/submittals", tag="submittals", search_fields=["submittal_no", "title"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.Defect, read_schema=DefectRead,
        create_schema=DefectCreate, update_schema=DefectUpdate,
        prefix="/defects", tag="defects", search_fields=["defect_no", "title", "location"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.Inspection, read_schema=InspectionRead,
        create_schema=InspectionCreate, update_schema=InspectionUpdate,
        prefix="/inspections", tag="inspections", search_fields=["inspection_no", "title"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.SiteDiary, read_schema=SiteDiaryRead,
        create_schema=SiteDiaryCreate, update_schema=SiteDiaryUpdate,
        prefix="/site-diaries", tag="site_diaries", search_fields=[],
        write_roles=[PM],
    ),
    # ── BRD Module 8: Procurement Pipeline ───────────────────────
    make_crud_router(
        model=models.CostCode, read_schema=CostCodeRead,
        create_schema=CostCodeCreate, update_schema=CostCodeUpdate,
        prefix="/cost-codes", tag="cost_codes", search_fields=["code", "description"],
        write_roles=[ACCT],
    ),
    make_crud_router(
        model=models.PurchaseRequest, read_schema=PurchaseRequestRead,
        create_schema=PurchaseRequestCreate, update_schema=PurchaseRequestUpdate,
        prefix="/purchase-requests", tag="purchase_requests", search_fields=["request_no", "title"],
        write_roles=[PM, ACCT],
    ),
    make_crud_router(
        model=models.RFQ, read_schema=RFQRead,
        create_schema=RFQCreate, update_schema=RFQUpdate,
        prefix="/rfqs", tag="rfqs", search_fields=["rfq_no", "description"],
        write_roles=[ACCT],
    ),
    make_crud_router(
        model=models.GoodsReceipt, read_schema=GoodsReceiptRead,
        create_schema=GoodsReceiptCreate, update_schema=GoodsReceiptUpdate,
        prefix="/goods-receipts", tag="goods_receipts", search_fields=["receipt_no"],
        write_roles=[ACCT, PM],
    ),
    make_crud_router(
        model=models.EInvoice, read_schema=EInvoiceRead,
        create_schema=EInvoiceCreate, update_schema=EInvoiceUpdate,
        prefix="/e-invoices", tag="e_invoices", search_fields=["invoice_no", "vendor_name"],
        write_roles=[ACCT],
    ),
    # ── Module 2: Addendum & Reverse Auction CRUD ───────────────
    make_crud_router(
        model=models.TenderAddendum, read_schema=TenderAddendumRead,
        create_schema=TenderAddendumCreate, update_schema=TenderAddendumUpdate,
        prefix="/tender-addenda", tag="tender_addenda", search_fields=["addendum_no", "title"],
        write_roles=[PM],
    ),
    make_crud_router(
        model=models.ReverseAuction, read_schema=ReverseAuctionRead,
        create_schema=ReverseAuctionCreate, update_schema=ReverseAuctionUpdate,
        prefix="/reverse-auctions", tag="reverse_auctions", search_fields=[],
        write_roles=[PM],
    ),
    # ── Module 3: Final Account ─────────────────────────────────
    make_crud_router(
        model=models.FinalAccount, read_schema=FinalAccountRead,
        create_schema=FinalAccountCreate, update_schema=FinalAccountUpdate,
        prefix="/final-accounts", tag="final_accounts", search_fields=["account_no"],
        write_roles=[ACCT, PM],
    ),
    # ── Module 5: Cost Benchmarking & Rate Analysis ────────────
    make_crud_router(
        model=models.CostBenchmark, read_schema=CostBenchmarkRead,
        create_schema=CostBenchmarkCreate, update_schema=CostBenchmarkUpdate,
        prefix="/cost-benchmarks", tag="cost_benchmarks", search_fields=["category", "region"],
        write_roles=[ACCT, PM],
    ),
    make_crud_router(
        model=models.RateItem, read_schema=RateItemRead,
        create_schema=RateItemCreate, update_schema=RateItemUpdate,
        prefix="/rate-items", tag="rate_items", search_fields=["description", "source"],
        write_roles=[ACCT, PM],
    ),
    # ── Module 7: Reports & Email Reminders ────────────────────
    make_crud_router(
        model=models.ReportTemplate, read_schema=ReportTemplateRead,
        create_schema=ReportTemplateCreate, update_schema=ReportTemplateUpdate,
        prefix="/report-templates", tag="report_templates", search_fields=["name", "report_type"],
        write_roles=[PM, ACCT],
    ),
    make_crud_router(
        model=models.EmailReminder, read_schema=EmailReminderRead,
        create_schema=EmailReminderCreate, update_schema=EmailReminderUpdate,
        prefix="/email-reminders", tag="email_reminders", search_fields=["entity_type", "recipient_email"],
        write_roles=[PM, ACCT],
    ),
]
app.include_router(auth_router, prefix="/api")
app.include_router(tenants_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(auction_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(sse_router, prefix="/api")
app.include_router(ocr_router, prefix="/api")
for r in ROUTERS:
    app.include_router(r, prefix="/api")


# ── Meta endpoints ────────────────────────────────────────────────────
@app.get("/api/health", tags=["meta"])
def health():
    from .ai import ai_agent
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "ai_available": ai_agent.is_available(),
    }


@app.get("/api/state", tags=["meta"], summary="Full application state in one call")
def full_state(db: Session = Depends(get_db), user: User = Depends(get_current_active_user)):
    """Mirror of the frontend `data` object — convenient single-request load.

    Auto-filtered by the caller's tenant_id (admins see all)."""
    from .crud import _tenant_filter

    def scoped(model):
        q = db.query(model)
        tf = _tenant_filter(model, user)
        if tf is not None:
            q = q.filter(tf)
        return q.all()

    resources = scoped(models.Resource)
    return {
        "projects": [schemas.ProjectRead.model_validate(x) for x in scoped(models.Project)],
        "tasks": [schemas.TaskRead.model_validate(x) for x in scoped(models.Task)],
        "resources": {
            cat: [schemas.ResourceRead.model_validate(x) for x in resources if x.category == cat]
            for cat in ("labor", "equipment", "materials")
        },
        "budget": [schemas.BudgetItemRead.model_validate(x) for x in scoped(models.BudgetItem)],
        "pos": [schemas.PurchaseOrderRead.model_validate(x) for x in scoped(models.PurchaseOrder)],
        "subs": [schemas.SubcontractorRead.model_validate(x) for x in scoped(models.Subcontractor)],
        "changeOrders": [schemas.ChangeOrderRead.model_validate(x) for x in scoped(models.ChangeOrder)],
    }


@app.get("/", tags=["meta"])
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}