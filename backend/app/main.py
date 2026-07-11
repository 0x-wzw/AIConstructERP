"""ConstructERP backend — FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import router as auth_router
from .config import settings
from .crud import generate_po_number, make_crud_router
from .database import Base, SessionLocal, engine, get_db
from .security import Role, get_current_active_user


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
]
app.include_router(auth_router, prefix="/api")
for r in ROUTERS:
    app.include_router(r, prefix="/api")


# ── Meta endpoints ────────────────────────────────────────────────────
@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/api/state", tags=["meta"], summary="Full application state in one call",
         dependencies=[Depends(get_current_active_user)])
def full_state(db: Session = Depends(get_db)):
    """Mirror of the frontend `data` object — convenient single-request load."""
    resources = db.query(models.Resource).all()
    return {
        "projects": [schemas.ProjectRead.model_validate(x) for x in db.query(models.Project).all()],
        "tasks": [schemas.TaskRead.model_validate(x) for x in db.query(models.Task).all()],
        "resources": {
            cat: [schemas.ResourceRead.model_validate(x) for x in resources if x.category == cat]
            for cat in ("labor", "equipment", "materials")
        },
        "budget": [schemas.BudgetItemRead.model_validate(x) for x in db.query(models.BudgetItem).all()],
        "pos": [schemas.PurchaseOrderRead.model_validate(x) for x in db.query(models.PurchaseOrder).all()],
        "subs": [schemas.SubcontractorRead.model_validate(x) for x in db.query(models.Subcontractor).all()],
        "changeOrders": [schemas.ChangeOrderRead.model_validate(x) for x in db.query(models.ChangeOrder).all()],
    }


@app.get("/", tags=["meta"])
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}
