"""Pydantic v2 request/response schemas.

Convention per entity:
  * <Entity>Base    — shared writable fields
  * <Entity>Create  — POST body
  * <Entity>Update  — PATCH body (all fields optional)
  * <Entity>Read    — response (adds id / server fields)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ORM = ConfigDict(from_attributes=True)

RoleLiteral = Literal["admin", "project_manager", "accounting", "viewer"]

ProjectStatus = Literal["active", "planning", "on_hold", "complete"]
TaskColor = Literal["amber", "blue", "green", "purple", "rose", "cyan"]
ResourceCategory = Literal["labor", "equipment", "materials"]
POStatus = Literal["Pending", "Ordered", "In Transit", "Delivered"]


# ── Projects ──────────────────────────────────────────────────────────
class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str = ""
    budget: float = Field(default=0, ge=0)
    duration: str = ""
    description: str = ""
    status: ProjectStatus = "active"
    progress: int = Field(default=0, ge=0, le=100)
    tenant_id: Optional[int] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    location: Optional[str] = None
    budget: Optional[float] = Field(default=None, ge=0)
    duration: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    tenant_id: Optional[int] = None


class ProjectRead(ProjectBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: datetime


# ── Tasks ─────────────────────────────────────────────────────────────
class TaskBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    start: int = Field(default=0, ge=0, le=100)
    width: int = Field(default=20, ge=1, le=100)
    color: TaskColor = "amber"
    project_id: Optional[int] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    start: Optional[int] = Field(default=None, ge=0, le=100)
    width: Optional[int] = Field(default=None, ge=1, le=100)
    color: Optional[TaskColor] = None
    project_id: Optional[int] = None


class TaskRead(TaskBase):
    model_config = ORM
    id: int
    is_archived: bool = False


# ── Resources ─────────────────────────────────────────────────────────
class ResourceBase(BaseModel):
    category: ResourceCategory
    name: str = Field(min_length=1, max_length=200)
    required: int = Field(default=0, ge=0)
    available: int = Field(default=0, ge=0)
    unit: str = ""


class ResourceCreate(ResourceBase):
    pass


class ResourceUpdate(BaseModel):
    category: Optional[ResourceCategory] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    required: Optional[int] = Field(default=None, ge=0)
    available: Optional[int] = Field(default=None, ge=0)
    unit: Optional[str] = None


class ResourceRead(ResourceBase):
    model_config = ORM
    id: int
    is_archived: bool = False


# ── Budget items ──────────────────────────────────────────────────────
class BudgetItemBase(BaseModel):
    category: str = Field(min_length=1, max_length=120)
    budget: float = Field(default=0, ge=0)
    committed: float = Field(default=0, ge=0)
    spent: float = Field(default=0, ge=0)


class BudgetItemCreate(BudgetItemBase):
    pass


class BudgetItemUpdate(BaseModel):
    category: Optional[str] = Field(default=None, min_length=1, max_length=120)
    budget: Optional[float] = Field(default=None, ge=0)
    committed: Optional[float] = Field(default=None, ge=0)
    spent: Optional[float] = Field(default=None, ge=0)


class BudgetItemRead(BudgetItemBase):
    model_config = ORM
    id: int
    is_archived: bool = False


# ── Purchase orders ───────────────────────────────────────────────────
class PurchaseOrderBase(BaseModel):
    supplier: str = Field(min_length=1, max_length=200)
    item: str = Field(min_length=1, max_length=200)
    qty: str = ""
    amount: float = Field(default=0, ge=0)
    status: POStatus = "Pending"
    delivery: str = "TBD"


class PurchaseOrderCreate(PurchaseOrderBase):
    # Auto-generated (PO-YYYY-NNN) when omitted.
    po_number: Optional[str] = None


class PurchaseOrderUpdate(BaseModel):
    supplier: Optional[str] = Field(default=None, min_length=1, max_length=200)
    item: Optional[str] = Field(default=None, min_length=1, max_length=200)
    qty: Optional[str] = None
    amount: Optional[float] = Field(default=None, ge=0)
    status: Optional[POStatus] = None
    delivery: Optional[str] = None


class PurchaseOrderRead(PurchaseOrderBase):
    model_config = ORM
    id: int
    po_number: str
    is_archived: bool = False
    created_at: datetime


# ── Subcontractors ────────────────────────────────────────────────────
class SubcontractorBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    initials: str = ""
    trade: str = "General"
    contract: float = Field(default=0, ge=0)
    progress: int = Field(default=0, ge=0, le=100)
    status: str = "Active"
    color: str = "from-slate-500 to-slate-600"


class SubcontractorCreate(SubcontractorBase):
    pass


class SubcontractorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    initials: Optional[str] = None
    trade: Optional[str] = None
    contract: Optional[float] = Field(default=None, ge=0)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    status: Optional[str] = None
    color: Optional[str] = None


class SubcontractorRead(SubcontractorBase):
    model_config = ORM
    id: int
    is_archived: bool = False


# ── Change orders ─────────────────────────────────────────────────────
class ChangeOrderBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    cost_impact: float = 0
    schedule_impact: str = ""
    status: str = "Pending"


class ChangeOrderCreate(ChangeOrderBase):
    pass


class ChangeOrderUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    cost_impact: Optional[float] = None
    schedule_impact: Optional[str] = None
    status: Optional[str] = None


class ChangeOrderRead(ChangeOrderBase):
    model_config = ORM
    id: int
    is_archived: bool = False
    created_at: datetime


# ── Auth / Users ──────────────────────────────────────────────────────
class UserBase(BaseModel):
    email: EmailStr
    full_name: str = ""


class UserRegister(UserBase):
    """Public self-signup — role is forced to 'viewer' server-side."""
    password: str = Field(min_length=6, max_length=128)


class UserAdminCreate(UserRegister):
    """Admin-created user with an explicit role."""
    role: RoleLiteral = "viewer"
    tenant_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[RoleLiteral] = None
    tenant_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)


class UserRead(UserBase):
    model_config = ORM
    id: int
    role: RoleLiteral
    tenant_id: Optional[int] = None
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    role: RoleLiteral
    expires_in: int  # seconds
