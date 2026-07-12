"""ConstructERP — AI-native ERP data model.

Architecture: Unified Entity System with Graph Relationships

Instead of 56 rigid tables, the system uses:
  1. entities         — one table for ALL domain objects (projects, vendors, tenders, etc.)
  2. entity_attributes — dynamic key-value metadata (replaces all specific columns)
  3. entity_relationships — graph edges between any two entities
  4. entity_activities  — activity/event/audit stream
  5. entity_comments    — threaded comments on any entity
  6. entity_files       — file attachments linked to entities
  7. entity_types       — schema definitions for each entity type
  8. attribute_definitions — schema for what attributes each type can have

This enables:
  - Zero-migration field additions (just add an attribute)
  - Graph traversal across domains (find all vendors linked to a project)
  - AI-native context (full activity stream per entity)
  - Multi-tenancy by entity_type
  - Dynamic form generation from attribute_definitions
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# ══════════════════════════════════════════════════════════════════════════
# CORE: Entity System
# ══════════════════════════════════════════════════════════════════════════


class EntityType(Base):
    """Schema definition for an entity type (e.g. 'project', 'vendor', 'tender').
    
    This is the metamodel — it defines what kinds of entities exist and what
    attributes they can have. The system bootstraps with built-in types and
    allows user-defined types at runtime.
    """
    __tablename__ = "entity_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plural_name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(60), default="")
    color: Mapped[str] = mapped_column(String(30), default="")
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    attributes: Mapped[List["AttributeDefinition"]] = relationship(
        back_populates="entity_type", cascade="all, delete-orphan"
    )


class AttributeDefinition(Base):
    """Schema definition for an attribute on an entity type.
    
    Defines what fields an entity type can have, their types, validation rules,
    and display properties. This drives dynamic form generation.
    """
    __tablename__ = "attribute_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type_id: Mapped[int] = mapped_column(
        ForeignKey("entity_types.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    attr_type: Mapped[str] = mapped_column(
        String(30), default="string", index=True
    )  # string|text|number|money|date|datetime|boolean|select|json|user|entity
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False)
    is_searchable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=True)
    default_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    options_json: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, nullable=True
    )  # For select types: {"choices": ["a", "b"]}; for money: {"currency": "MYR"}
    validation_rules: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, nullable=True
    )  # {"min": 0, "max": 1000000, "pattern": "^...$"}
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entity_type: Mapped["EntityType"] = relationship(back_populates="attributes")


class Entity(Base):
    """Universal entity — replaces all domain-specific tables.
    
    Every object in the system (project, vendor, tender, contract, defect, etc.)
    is a single row here. Type-specific fields are stored in entity_attributes.
    """
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type_id: Mapped[int] = mapped_column(
        ForeignKey("entity_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Human-readable identifier (e.g. "Riverside Tower", "BuildCo Sdn Bhd")
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    # Auto-generated or user-assigned reference number (e.g. "PRJ-2026-001", "TND-2026-001")
    reference_no: Mapped[str] = mapped_column(String(60), default="", index=True)
    # Core status — all entities have a lifecycle
    status: Mapped[str] = mapped_column(String(60), default="active", index=True)
    # Optional parent entity (for hierarchies: project -> phase -> task)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Tenant / organization scope
    tenant_id: Mapped[str] = mapped_column(String(60), default="default", index=True)
    # AI context
    summary: Mapped[str] = mapped_column(Text, default="")
    ai_embedding_id: Mapped[str] = mapped_column(String(100), default="")
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    entity_type: Mapped["EntityType"] = relationship()
    attributes: Mapped[List["EntityAttribute"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan",
        foreign_keys="EntityAttribute.entity_id",
    )
    children: Mapped[List["Entity"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        single_parent=True,
        remote_side=[id],
    )
    parent: Mapped[Optional["Entity"]] = relationship(
        back_populates="children", remote_side=[parent_id]
    )
    # Graph edges (both directions)
    source_relationships: Mapped[List["EntityRelationship"]] = relationship(
        back_populates="source_entity",
        cascade="all, delete-orphan",
        foreign_keys="EntityRelationship.source_id",
    )
    target_relationships: Mapped[List["EntityRelationship"]] = relationship(
        back_populates="target_entity",
        cascade="all, delete-orphan",
        foreign_keys="EntityRelationship.target_id",
    )
    activities: Mapped[List["EntityActivity"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    comments: Mapped[List["EntityComment"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )
    files: Mapped[List["EntityFile"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class EntityAttribute(Base):
    """Dynamic key-value attributes for entities.
    
    This replaces all the specific columns in traditional ERP tables.
    Each entity can have any number of attributes, defined by the
    attribute_definitions for its entity_type.
    """
    __tablename__ = "entity_attributes"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attribute_definition_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("attribute_definitions.id", ondelete="SET NULL"), nullable=True
    )
    slug: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    value_string: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_number: Mapped[Optional[float]] = mapped_column(Numeric(16, 4), nullable=True)
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    value_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    value_boolean: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    value_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    value_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    value_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    entity: Mapped["Entity"] = relationship(
        back_populates="attributes", foreign_keys=[entity_id]
    )


class EntityRelationship(Base):
    """Graph edge between any two entities.
    
    Enables full graph traversal: find all vendors for a project, all
    tenders a vendor bid on, all contracts linked to a tender, etc.
    """
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True
    )  # manages|belongs_to|bids_on|awarded_to|has_contract|contains|references|approved_by
    label: Mapped[str] = mapped_column(String(200), default="")
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    source_entity: Mapped["Entity"] = relationship(
        back_populates="source_relationships", foreign_keys=[source_id]
    )
    target_entity: Mapped["Entity"] = relationship(
        back_populates="target_relationships", foreign_keys=[target_id]
    )


class EntityActivity(Base):
    """Activity/event/audit stream for any entity.
    
    Every state change, file upload, comment, or AI action is recorded here.
    This is the source of truth for audit trails and AI context.
    """
    __tablename__ = "entity_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_type: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True
    )  # created|updated|status_changed|attribute_changed|file_uploaded|commented|relationship_added|ai_summarized|ai_analyzed
    description: Mapped[str] = mapped_column(String(500), default="")
    # Before/after snapshots for audit
    previous_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    performed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="activities")


class EntityComment(Base):
    """Threaded comments on any entity.
    
    Supports internal discussions, review notes, and AI-generated insights.
    """
    __tablename__ = "entity_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entity_comments.id", ondelete="CASCADE"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    comment_type: Mapped[str] = mapped_column(
        String(30), default="comment", index=True
    )  # comment|review|approval|rejection|ai_insight|system_note
    author_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="comments")
    replies: Mapped[List["EntityComment"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        single_parent=True,
        remote_side=[id],
    )
    parent: Mapped[Optional["EntityComment"]] = relationship(
        back_populates="replies", remote_side=[parent_id]
    )


class EntityFile(Base):
    """File attachments linked to entities.
    
    Links the file_metadata table to entities with context about the attachment.
    """
    __tablename__ = "entity_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_metadata_id: Mapped[int] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="RESTRICT"), nullable=False
    )
    file_category: Mapped[str] = mapped_column(
        String(60), default="", index=True
    )  # tender_document|bid_submission|contract|drawing|photo|report|attachment
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="files")


# ══════════════════════════════════════════════════════════════════════════
# AUTH (kept separate — not part of entity system)
# ══════════════════════════════════════════════════════════════════════════


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="viewer", index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════
# FILE STORAGE (kept separate — referenced by entity_files)
# ══════════════════════════════════════════════════════════════════════════


class FileMetadata(Base):
    __tablename__ = "file_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
