"""SQLAlchemy ORM models — the ConstructERP domain schema.

Money is stored as NUMERIC(14,2). Enum-like fields (status, trade, color) are
plain strings validated at the Pydantic layer so the schema stays portable
across SQLite and PostgreSQL.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
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


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    location: Mapped[str] = mapped_column(String(300), default="")
    budget: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    duration: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tasks: Mapped[list[Task]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    start: Mapped[int] = mapped_column(Integer, default=0)   # timeline offset, %
    width: Mapped[int] = mapped_column(Integer, default=20)  # duration span, %
    color: Mapped[str] = mapped_column(String(20), default="amber")
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped[Project | None] = relationship(back_populates="tasks")


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)  # labor|equipment|materials
    name: Mapped[str] = mapped_column(String(200))
    required: Mapped[int] = mapped_column(Integer, default=0)
    available: Mapped[int] = mapped_column(Integer, default=0)
    unit: Mapped[str] = mapped_column(String(40), default="")


class BudgetItem(Base):
    __tablename__ = "budget_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    budget: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    committed: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    spent: Mapped[float] = mapped_column(Numeric(14, 2), default=0)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    supplier: Mapped[str] = mapped_column(String(200))
    item: Mapped[str] = mapped_column(String(200))
    qty: Mapped[str] = mapped_column(String(60), default="")
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="Pending", index=True)
    delivery: Mapped[str] = mapped_column(String(60), default="TBD")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Subcontractor(Base):
    __tablename__ = "subcontractors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    initials: Mapped[str] = mapped_column(String(4), default="")
    trade: Mapped[str] = mapped_column(String(60), default="General")
    contract: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="Active")
    color: Mapped[str] = mapped_column(String(60), default="from-slate-500 to-slate-600")


class ChangeOrder(Base):
    __tablename__ = "change_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    cost_impact: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    schedule_impact: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(30), default="Pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="viewer", index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
