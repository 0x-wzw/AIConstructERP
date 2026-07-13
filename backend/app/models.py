"""AIConstructERP — Enterprise Construction ERP data model.

Architecture: Unified Entity System + BIM Digital Twin + AI Orchestration
             + External API Integration Layer

┌─────────────────────────────────────────────────────────────────┐
│  React + Autodesk Web Viewer (Presentation)                    │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI Gateway + LangGraph Orchestrator                      │
├─────────────────────────────────────────────────────────────────┤
│  Temporal/Celery Workers (async, heavy tasks)                  │
├─────────────────────────────────────────────────────────────────┤
│  UNIFIED POSTGRESQL ENGINE                                     │
│  ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Relational   │ │ pgvector │ │ PostGIS  │ │ TimescaleDB   │  │
│  │ (Entity Sys) │ │ (Embeds) │ │ (3D Geo) │ │ (IoT/Sensors) │  │
│  └──────────────┘ └──────────┘ └──────────┘ └──────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  EXTERNAL API INTEGRATION LAYER                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ Connector│ │Credential│ │Webhook   │ │ Data Mapping     │  │
│  │ Registry │ │ Store    │ │ Receiver │ │ Templates        │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Government Systems: SSM | CIDB | LHDN | KPKT | JKR     │  │
│  │ Specialized: Autodesk | Xero | Sage | Procore | Aconex  │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  Debezium + Kafka → Autodesk APS (CDC Pipeline)                │
└─────────────────────────────────────────────────────────────────┘
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
    __tablename__ = "attribute_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type_id: Mapped[int] = mapped_column(
        ForeignKey("entity_types.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    attr_type: Mapped[str] = mapped_column(String(30), default="string", index=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False)
    is_searchable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=True)
    default_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    options_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    validation_rules: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entity_type: Mapped["EntityType"] = relationship(back_populates="attributes")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type_id: Mapped[int] = mapped_column(
        ForeignKey("entity_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    reference_no: Mapped[str] = mapped_column(String(60), default="", index=True)
    status: Mapped[str] = mapped_column(String(60), default="active", index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    tenant_id: Mapped[str] = mapped_column(String(60), default="default", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    ai_embedding_id: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    entity_type: Mapped["EntityType"] = relationship()
    attributes: Mapped[List["EntityAttribute"]] = relationship(
        back_populates="entity", cascade="all, delete-orphan",
        foreign_keys="EntityAttribute.entity_id",
    )
    children: Mapped[List["Entity"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan",
        single_parent=True, remote_side=[id],
    )
    parent: Mapped[Optional["Entity"]] = relationship(
        back_populates="children", remote_side=[parent_id]
    )
    source_relationships: Mapped[List["EntityRelationship"]] = relationship(
        back_populates="source_entity", cascade="all, delete-orphan",
        foreign_keys="EntityRelationship.source_id",
    )
    target_relationships: Mapped[List["EntityRelationship"]] = relationship(
        back_populates="target_entity", cascade="all, delete-orphan",
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
    __tablename__ = "entity_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
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
    __tablename__ = "entity_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), default="")
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
    __tablename__ = "entity_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entity_comments.id", ondelete="CASCADE"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    comment_type: Mapped[str] = mapped_column(String(30), default="comment", index=True)
    author_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="comments")
    replies: Mapped[List["EntityComment"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan",
        single_parent=True, remote_side=[id],
    )
    parent: Mapped[Optional["EntityComment"]] = relationship(
        back_populates="replies", remote_side=[parent_id]
    )


class EntityFile(Base):
    __tablename__ = "entity_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_metadata_id: Mapped[int] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="RESTRICT"), nullable=False
    )
    file_category: Mapped[str] = mapped_column(String(60), default="", index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entity: Mapped["Entity"] = relationship(back_populates="files")
    file_metadata: Mapped["FileMetadata"] = relationship()


# ══════════════════════════════════════════════════════════════════════════
# BIM DIGITAL TWIN
# ══════════════════════════════════════════════════════════════════════════


class BIMElement(Base):
    __tablename__ = "bim_elements"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    aps_urn: Mapped[str] = mapped_column(String(500), nullable=False)
    aps_external_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), default="", index=True)
    family: Mapped[str] = mapped_column(String(200), default="")
    family_type: Mapped[str] = mapped_column(String(200), default="")
    floor_level: Mapped[str] = mapped_column(String(50), default="", index=True)
    bounding_box_min_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bounding_box_min_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bounding_box_min_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bounding_box_max_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bounding_box_max_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bounding_box_max_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    specs_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    specs_embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    material_name: Mapped[str] = mapped_column(String(200), default="")
    material_grade: Mapped[str] = mapped_column(String(100), default="")
    volume_m3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BIMElementProperty(Base):
    __tablename__ = "bim_element_properties"

    id: Mapped[int] = mapped_column(primary_key=True)
    element_id: Mapped[int] = mapped_column(
        ForeignKey("bim_elements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, default="")
    value_type: Mapped[str] = mapped_column(String(30), default="string")


class BIMModel(Base):
    __tablename__ = "bim_models"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    aps_urn: Mapped[str] = mapped_column(String(500), nullable=False)
    file_metadata_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="uploaded", index=True)
    element_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════
# RFI
# ══════════════════════════════════════════════════════════════════════════


class RFI(Base):
    __tablename__ = "rfis"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rfi_no: Mapped[str] = mapped_column(String(30), unique=True, default="", index=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    detailed_question: Mapped[str] = mapped_column(Text, nullable=False)
    question_embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_agent_status: Mapped[str] = mapped_column(
        String(50), default="unassigned", index=True
    )
    ai_confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    suggested_resolution: Mapped[str] = mapped_column(Text, default="")
    assigned_to: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    target_response_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    response: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RFIBIMAssignment(Base):
    __tablename__ = "rfi_bim_assignments"

    rfi_id: Mapped[int] = mapped_column(
        ForeignKey("rfis.id", ondelete="CASCADE"), primary_key=True
    )
    element_id: Mapped[int] = mapped_column(
        ForeignKey("bim_elements.id", ondelete="CASCADE"), primary_key=True
    )


# ══════════════════════════════════════════════════════════════════════════
# SITE TELEMETRY
# ══════════════════════════════════════════════════════════════════════════


class SiteSensor(Base):
    __tablename__ = "site_sensors"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    sensor_id: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    sensor_type: Mapped[str] = mapped_column(String(60), default="", index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    floor_level: Mapped[str] = mapped_column(String(50), default="")
    pos_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pos_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pos_z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SiteSensorLog(Base):
    __tablename__ = "site_sensor_logs"

    recorded_at: Mapped[datetime] = mapped_column(DateTime, primary_key=True, index=True)
    sensor_id: Mapped[str] = mapped_column(String(60), primary_key=True, index=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    temperature_celsius: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    humidity_percentage: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    concrete_maturity_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vibration_mm_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    strain_microepsilon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed_kmh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rainfall_mm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_level_pct: Mapped[Optional[float]] = mapped_column(Numeric(4, 1), nullable=True)
    signal_strength_dbm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


# ══════════════════════════════════════════════════════════════════════════
# LANGGRAPH STATE CHECKPOINTS
# ══════════════════════════════════════════════════════════════════════════


class LangGraphCheckpoint(Base):
    __tablename__ = "langgraph_checkpoints"

    thread_id: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)
    checkpoint_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    parent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    serialized_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(60), default="", index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    interrupt_reason: Mapped[str] = mapped_column(Text, default="")
    resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resumed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════
# CDC PIPELINE
# ══════════════════════════════════════════════════════════════════════════


class CDCPipeline(Base):
    __tablename__ = "cdc_pipeline"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════
# EXTERNAL API INTEGRATION LAYER
# ══════════════════════════════════════════════════════════════════════════


class APIConnector(Base):
    """Registry of external API connections.
    
    Each connector defines how to reach a 3rd party system:
    - Government: SSM (company registry), CIDB (contractor registration),
      LHDN (tax), KPKT (housing), JKR (public works), MYNIC (domain)
    - Construction: Autodesk APS, Procore, Aconex, PlanGrid, Bluebeam
    - Financial: Xero, Sage, QuickBooks, SQL Financials
    - Geospatial: JUPEM (survey), PLANMalaysia, OpenStreetMap
    - Weather: MET Malaysia, OpenWeatherMap
    - Document: ePerolehan, MyProcurement, Panels
    """
    __tablename__ = "api_connectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True
    )  # ssm|cidb|lhdn|kplt|jkr|autodesk|procore|aconex|xero|sage|quickbooks|openstreetmap|weather|eperolehan|custom
    category: Mapped[str] = mapped_column(
        String(30), default="government", index=True
    )  # government|construction|financial|geospatial|weather|procurement|custom
    base_url: Mapped[str] = mapped_column(String(500), default="")
    api_version: Mapped[str] = mapped_column(String(30), default="")
    auth_type: Mapped[str] = mapped_column(
        String(30), default="api_key", index=True
    )  # api_key|oauth2|basic|bearer|jwt|mtls|none
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    retry_count: Mapped[int] = mapped_column(Integer, default=3)
    config_json: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, nullable=True
    )  # Provider-specific config (endpoints, scopes, etc.)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class APICredential(Base):
    """Securely stored API credentials for external systems.
    
    Credentials are encrypted at rest using the system's encryption key.
    Access is audited via entity_activities.
    """
    __tablename__ = "api_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("api_connectors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), default="")
    # Encrypted credential payload
    encrypted_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_api_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # OAuth2 fields
    oauth_client_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    oauth_scopes: Mapped[str] = mapped_column(String(500), default="")
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Environment
    environment: Mapped[str] = mapped_column(
        String(30), default="production", index=True
    )  # production|staging|sandbox|development
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    connector: Mapped["APIConnector"] = relationship()


class APIIntegrationLog(Base):
    """Audit log for all external API calls.
    
    Every request to an external system is logged here for:
    - Debugging failed integrations
    - Monitoring API usage and rate limits
    - Audit trail for regulatory compliance
    - Cost tracking (many APIs are pay-per-call)
    """
    __tablename__ = "api_integration_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("api_connectors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="GET")
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_summary: Mapped[str] = mapped_column(String(500), default="")
    response_data_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    retry_attempt: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    performed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    connector: Mapped["APIConnector"] = relationship()


class APIDataMapping(Base):
    """Maps external API data fields to internal entity attributes.
    
    Enables transforming data from any external system into the unified
    entity system without code changes. Supports:
    - Field-level mapping (external_field -> internal_attribute)
    - Value transformation (string replacements, unit conversions)
    - Conditional logic (if/then/else for different data shapes)
    """
    __tablename__ = "api_data_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("api_connectors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    direction: Mapped[str] = mapped_column(
        String(10), default="inbound", index=True
    )  # inbound|outbound|bidirectional
    source_entity_type: Mapped[str] = mapped_column(String(60), default="", index=True)
    target_entity_type: Mapped[str] = mapped_column(String(60), default="", index=True)
    # JSON mapping rules
    mapping_rules: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Example:
    # {
    #   "field_mappings": [
    #     {"from": "company.name", "to": "title", "transform": null},
    #     {"from": "company.registration_no", "to": "reference_no", "transform": null},
    #     {"from": "company.address", "to": "attributes.address", "transform": null},
    #     {"from": "company.ssm_status", "to": "attributes.ssm_status",
    #      "transform": {"type": "enum_map", "mapping": {"active": "active", "dissolved": "inactive"}}}
    #   ],
    #   "pre_hooks": ["lookup_vendor_by_registration"],
    #   "post_hooks": ["create_relationship_to_project", "send_notification"]
    # }
    pre_hooks: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    post_hooks: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    connector: Mapped["APIConnector"] = relationship()


class APIDataSyncSchedule(Base):
    """Scheduled data synchronization with external systems.
    
    Defines when and how to sync data between AIConstructERP and
    external APIs. Supports one-time, periodic, and event-driven syncs.
    """
    __tablename__ = "api_data_sync_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("api_connectors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mapping_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("api_data_mappings.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    frequency: Mapped[str] = mapped_column(
        String(30), default="manual", index=True
    )  # manual|once|hourly|daily|weekly|monthly|realtime|event_driven
    cron_expression: Mapped[str] = mapped_column(String(100), default="")
    # Sync scope
    sync_type: Mapped[str] = mapped_column(
        String(30), default="full", index=True
    )  # full|incremental|delta
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_sync_status: Mapped[str] = mapped_column(
        String(30), default="never", index=True
    )  # never|running|success|partial|failed
    last_sync_summary: Mapped[str] = mapped_column(Text, default="")
    next_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    connector: Mapped["APIConnector"] = relationship()


class APIWebhookReceiver(Base):
    """Registered webhook endpoints for receiving data from external systems.
    
    External systems (SSM, CIDB, Procore, etc.) can push data to these
    endpoints. The system validates the webhook signature, processes the
    payload through the configured data mapping, and creates/updates entities.
    """
    __tablename__ = "api_webhook_receivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("api_connectors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mapping_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("api_data_mappings.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    webhook_path: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, index=True
    )  # e.g. "/webhooks/ssm/company-update"
    # Security
    secret_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    verify_signature: Mapped[bool] = mapped_column(Boolean, default=True)
    signature_header: Mapped[str] = mapped_column(String(100), default="X-Webhook-Signature")
    allowed_ips: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Processing
    process_async: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_received: Mapped[int] = mapped_column(Integer, default=0)
    total_errors: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    connector: Mapped["APIConnector"] = relationship()


class APIWebhookEvent(Base):
    """Record of every webhook event received from external systems."""
    __tablename__ = "api_webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("api_webhook_receivers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), default="", index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    signature_valid: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending|processing|completed|failed|ignored
    result_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str] = mapped_column(Text, default="")
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    receiver: Mapped["APIWebhookReceiver"] = relationship()


# ══════════════════════════════════════════════════════════════════════════
# GOVERNMENT SYSTEM INTEGRATIONS — Localized Data Models
# ══════════════════════════════════════════════════════════════════════════


class GovernmentSSMRecord(Base):
    """SSM (Suruhanjaya Syarikat Malaysia) — Company Registry.
    
    Used for vendor registration verification, director lookup,
    company status checks, and financial statement retrieval.
    API: https://www.ssm.com.my/Pages/Services/API/Overview.aspx
    """
    __tablename__ = "government_ssm_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    registration_no: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(300), default="")
    company_type: Mapped[str] = mapped_column(String(100), default="")
    incorporation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="", index=True)
    business_address: Mapped[str] = mapped_column(Text, default="")
    directors: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    shareholders: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    paid_up_capital: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    financial_year_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_agm_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GovernmentCIDBRecord(Base):
    """CIDB (Construction Industry Development Board) — Contractor Registration.
    
    Used for contractor grade verification, expiry tracking,
    project registration, and levy calculation.
    API: https://www.cidb.gov.my/en/construction-professionals/contractors
    """
    __tablename__ = "government_cidb_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cidb_registration_no: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False, index=True
    )
    company_name: Mapped[str] = mapped_column(String(300), default="")
    grade: Mapped[str] = mapped_column(String(10), default="", index=True)  # G1-G7
    head_category: Mapped[str] = mapped_column(
        String(10), default="", index=True
    )  # A (Civil), B (Building), C (Mechanical), D (Electrical), E (Special)
    sub_category: Mapped[str] = mapped_column(String(100), default="")
    registration_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="", index=True)
    tender_capacity_limit: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    work_capacity_limit: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GovernmentLHDNRecord(Base):
    """LHDN (Lembaga Hasil Dalam Negeri Malaysia) — Tax & Compliance.
    
    Used for tax identification, SST registration, withholding tax,
    and e-invoice compliance verification.
    """
    __tablename__ = "government_lhdn_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tax_id: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(300), default="")
    tax_status: Mapped[str] = mapped_column(String(30), default="", index=True)
    sst_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    sst_registration_no: Mapped[str] = mapped_column(String(60), default="")
    sst_expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    e_invoice_compliant: Mapped[bool] = mapped_column(Boolean, default=False)
    tax_clearance_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    tax_clearance_expiry: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GovernmentKPKTRecord(Base):
    """KPKT (Kementerian Perumahan dan Kerajaan Tempatan) — Housing & Local Govt.
    
    Used for developer licensing, housing project registration,
    strata title tracking, and building plan approvals.
    """
    __tablename__ = "government_kpkt_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    developer_license_no: Mapped[str] = mapped_column(String(60), default="", index=True)
    project_approval_no: Mapped[str] = mapped_column(String(60), default="", index=True)
    project_type: Mapped[str] = mapped_column(String(100), default="")
    land_title_no: Mapped[str] = mapped_column(String(100), default="")
    lot_no: Mapped[str] = mapped_column(String(60), default="")
    mukim: Mapped[str] = mapped_column(String(100), default="")
    district: Mapped[str] = mapped_column(String(100), default="")
    state: Mapped[str] = mapped_column(String(60), default="")
    approval_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="", index=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GovernmentJKRRecord(Base):
    """JKR (Jabatan Kerja Raya) — Public Works Department.
    
    Used for public project registration, contractor registration for
    government projects, and project code lookup.
    """
    __tablename__ = "government_jkr_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    jkr_project_code: Mapped[str] = mapped_column(String(60), unique=True, default="", index=True)
    project_name: Mapped[str] = mapped_column(String(300), default="")
    project_category: Mapped[str] = mapped_column(String(100), default="")
    procurement_method: Mapped[str] = mapped_column(String(60), default="")
    contract_value: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    completion_period_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="", index=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GovernmentEPerolehanRecord(Base):
    """ePerolehan — Government e-Procurement System.
    
    Used for tender listing, vendor registration on government panels,
    and procurement award tracking.
    """
    __tablename__ = "government_eperolehan_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    eperolehan_ref_no: Mapped[str] = mapped_column(
        String(60), unique=True, default="", index=True
    )
    tender_title: Mapped[str] = mapped_column(String(300), default="")
    ministry: Mapped[str] = mapped_column(String(200), default="")
    procurement_type: Mapped[str] = mapped_column(String(60), default="")
    tender_status: Mapped[str] = mapped_column(String(30), default="", index=True)
    tender_value: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    published_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closing_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    awarded_to: Mapped[str] = mapped_column(String(300), default="")
    award_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════
# SPECIALIZED DATASET INTEGRATIONS
# ══════════════════════════════════════════════════════════════════════════


class ExternalDatasetCache(Base):
    """Cached data from external specialized datasets.
    
    Many government and industry datasets have rate limits or charge
    per-query fees. This cache stores results locally with TTL-based
    expiration to minimize API calls and improve response times.
    """
    __tablename__ = "external_dataset_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(
        ForeignKey("api_connectors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cache_key: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True
    )
    query_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════
# CREDIT REPORTING — CTOS / CCRIS / FICO / Credit Bureau Integration
# ══════════════════════════════════════════════════════════════════════════


class CreditBureauQuery(Base):
    """Credit bureau inquiry record — CTOS, CCRIS, FICO, Experian, etc.
    
    Used for:
    - Vendor pre-qualification (credit check before tender award)
    - Subcontractor financial health assessment
    - Partner/supplier due diligence
    - Project financing eligibility
    
    Supports:
    - CTOS (Malaysia) — credit reports, scores, bankruptcy, litigation
    - CCRIS (Malaysia) — central credit reference, loan history
    - FICO / Experian / TransUnion — international credit scoring
    - SSM — director background, company winding-up
    """
    __tablename__ = "credit_bureau_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Query identifiers
    query_type: Mapped[str] = mapped_column(
        String(30), default="ctos", index=True
    )  # ctos|ccris|fico|experian|transunion|ssm_director|ssm_winding_up
    query_reference: Mapped[str] = mapped_column(
        String(100), unique=True, default="", index=True
    )
    # Subject identification
    id_type: Mapped[str] = mapped_column(
        String(30), default="ssm_registration", index=True
    )  # ssm_registration|ic_number|passport|business_registration|tax_id
    id_number: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    subject_name: Mapped[str] = mapped_column(String(300), default="")
    
    # CTOS specific
    ctos_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ctos_rating: Mapped[str] = mapped_column(
        String(10), default="", index=True
    )  # A1|A2|A3|B1|B2|B3|C1|C2|C3|D|E|F
    ctos_band: Mapped[str] = mapped_column(
        String(20), default=""
    )  # Excellent|Good|Fair|Below Average|Poor|Very Poor
    ctos_credit_limit: Mapped[Optional[float]] = mapped_column(
        Numeric(16, 2), nullable=True
    )
    ctos_outstanding_total: Mapped[Optional[float]] = mapped_column(
        Numeric(16, 2), nullable=True
    )
    
    # CCRIS specific
    cCRIS_total_loans: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cCRIS_total_outstanding: Mapped[Optional[float]] = mapped_column(
        Numeric(16, 2), nullable=True
    )
    cCRIS_special_attention: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # Count of accounts with special attention flags
    cCRIS_non_performing: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # Count of non-performing loans
    
    # FICO / International
    fico_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fico_range: Mapped[str] = mapped_column(String(20), default="")
    
    # Legal & adverse records
    bankruptcy_filed: Mapped[bool] = mapped_column(Boolean, default=False)
    bankruptcy_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    litigation_count: Mapped[int] = mapped_column(Integer, default=0)
    winding_up_filed: Mapped[bool] = mapped_column(Boolean, default=False)
    director_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Adverse media / sanctions
    sanctions_list_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    pep_status: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Politically Exposed Person
    adverse_media_mentions: Mapped[int] = mapped_column(Integer, default=0)
    
    # Query metadata
    purpose: Mapped[str] = mapped_column(
        String(60), default="vendor_pre_qualification", index=True
    )  # vendor_pre_qualification|tender_evaluation|contract_award|
      # subcontractor_onboarding|project_financing|due_diligence|periodic_review
    consent_obtained: Mapped[bool] = mapped_column(Boolean, default=True)
    consent_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Results
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending|processing|completed|failed|consent_required
    decision: Mapped[str] = mapped_column(
        String(30), default="", index=True
    )  # pass|conditional_pass|fail|review_required|insufficient_data
    decision_notes: Mapped[str] = mapped_column(Text, default="")
    score_summary: Mapped[str] = mapped_column(String(200), default="")
    
    # Raw data
    raw_request: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Audit
    requested_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    queried_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )  # Credit reports have validity periods
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CreditBureauConsent(Base):
    """Record of consent obtained for credit bureau inquiries.
    
    Regulatory requirement: must maintain proof of consent for each
    credit check performed. Includes digital signature or recorded
    verbal consent per jurisdiction requirements.
    """
    __tablename__ = "credit_bureau_consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    consent_type: Mapped[str] = mapped_column(
        String(30), default="credit_check", index=True
    )  # credit_check|director_background|financial_review|periodic_monitoring
    consent_method: Mapped[str] = mapped_column(
        String(30), default="digital_signature", index=True
    )  # digital_signature|written|verbal_recorded|email|portal_agreement|implied
    consent_reference: Mapped[str] = mapped_column(String(100), default="", index=True)
    consent_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    consent_document_file_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="SET NULL"), nullable=True
    )
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    user_agent: Mapped[str] = mapped_column(String(500), default="")
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CreditWatchlist(Base):
    """Internal watchlist for entities with adverse credit events.
    
    Automatically populated from credit bureau queries and manual entries.
    Used to flag high-risk vendors, subcontractors, or partners during
    tender evaluation and contract award processes.
    """
    __tablename__ = "credit_watchlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    watchlist_type: Mapped[str] = mapped_column(
        String(30), default="credit", index=True
    )  # credit|legal|sanctions|pep|adverse_media|internal
    source: Mapped[str] = mapped_column(
        String(60), default="ctos", index=True
    )  # ctos|ccris|fico|ssm|court|bkn|police|internal|media
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), default="medium", index=True
    )  # critical|high|medium|low|informational
    status: Mapped[str] = mapped_column(
        String(30), default="active", index=True
    )  # active|reviewed|resolved|expired
    source_query_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("credit_bureau_queries.id", ondelete="SET NULL"), nullable=True
    )
    added_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════
# PAYMENT GATEWAY — PayNET / FPX / Online Banking / Card Processing
# ══════════════════════════════════════════════════════════════════════════


class PaymentGateway(Base):
    """Registered payment gateway configurations.
    
    Supports:
    - PayNET (Malaysia) — FPX, online banking, MyDebit
    - FPX (Financial Process Exchange) — direct online banking
    - DuitNow — real-time transfers, QR payments
    - Credit/Debit cards — Visa, Mastercard, Amex
    - e-Wallet — Touch 'n Go, GrabPay, ShopeePay, Boost
    - International — Stripe, PayPal, Braintree
    - Bank integrations — CIMB Clicks, Maybank2u, RHB Now, etc.
    """
    __tablename__ = "payment_gateways"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # paynet|fpx|duitnow|stripe|paypal|billplz|tng|grabpay|shopee|boost|bank|custom
    gateway_type: Mapped[str] = mapped_column(
        String(30), default="fpx", index=True
    )  # fpx|card|ewallet|bank_transfer|qr|realtime_transfer|bnpl|crypto
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Configuration
    merchant_id: Mapped[str] = mapped_column(String(100), default="")
    merchant_name: Mapped[str] = mapped_column(String(200), default="")
    api_endpoint: Mapped[str] = mapped_column(String(500), default="")
    webhook_url: Mapped[str] = mapped_column(String(500), default="")
    callback_url: Mapped[str] = mapped_column(String(500), default="")
    # Fee structure
    transaction_fee_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    transaction_fee_fixed: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    settlement_days: Mapped[int] = mapped_column(Integer, default=1)
    # Limits
    min_transaction: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    max_transaction: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    daily_limit: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    monthly_limit: Mapped[Optional[float]] = mapped_column(Numeric(16, 2), nullable=True)
    # Supported payment methods
    supported_methods: Mapped[Optional[list]] = mapped_column(
        JSON, default=list, nullable=True
    )  # ["fpx_maybank2u", "fpx_cimb", "visa", "mastercard", "tng_ewallet"]
    config_json: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaymentTransaction(Base):
    """Payment transaction record — every payment processed through any gateway.
    
    Tracks the full lifecycle: initiation → authorization → capture → settlement.
    Supports refunds, chargebacks, and reconciliation.
    """
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    gateway_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_gateways.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Transaction identifiers
    transaction_no: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False, index=True
    )
    gateway_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, index=True
    )
    gateway_reference: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )  # FPX transaction ID, PayNET ref, etc.
    
    # Amounts
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    fee_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    exchange_rate: Mapped[float] = mapped_column(Numeric(10, 6), default=1.0)
    amount_in_base_currency: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    
    # Payer / Payee
    payer_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payer_name: Mapped[str] = mapped_column(String(300), default="")
    payer_email: Mapped[str] = mapped_column(String(255), default="")
    payer_phone: Mapped[str] = mapped_column(String(60), default="")
    payer_bank: Mapped[str] = mapped_column(String(100), default="")
    payer_bank_account: Mapped[str] = mapped_column(String(60), default="")
    
    payee_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payee_name: Mapped[str] = mapped_column(String(300), default="")
    payee_bank: Mapped[str] = mapped_column(String(100), default="")
    payee_bank_account: Mapped[str] = mapped_column(String(60), default="")
    
    # Payment method
    payment_method: Mapped[str] = mapped_column(
        String(30), default="fpx", index=True
    )  # fpx|credit_card|debit_card|ewallet|bank_transfer|duitnow_qr|duitnow_transfer|bnpl|crypto|cash|cheque
    payment_channel: Mapped[str] = mapped_column(
        String(60), default="", index=True
    )  # maybank2u|cimbclicks|rhbnow|visa|mastercard|tng|grabpay|shopee|boost
    payment_detail: Mapped[str] = mapped_column(String(200), default="")
    
    # Status
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending|authorized|captured|settled|refunded|partially_refunded|
      # failed|cancelled|expired|chargeback|disputed
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    failure_code: Mapped[str] = mapped_column(String(60), default="")
    
    # Business context
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("e_invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payment_type: Mapped[str] = mapped_column(
        String(30), default="invoice", index=True
    )  # invoice|deposit|retention|progress_claim|tender_bond|performance_bond|refund|subscription
    description: Mapped[str] = mapped_column(String(500), default="")
    
    # Timing
    authorized_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Reconciliation
    reconciliation_status: Mapped[str] = mapped_column(
        String(30), default="unreconciled", index=True
    )  # unreconciled|matched|partial_match|unmatched|disputed
    reconciliation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    bank_statement_line_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    
    # Audit
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    user_agent: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PaymentRefund(Base):
    """Refund records linked to payment transactions.
    
    Supports full, partial, and conditional refunds with audit trail.
    """
    __tablename__ = "payment_refunds"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refund_no: Mapped[str] = mapped_column(String(60), unique=True, default="", index=True)
    gateway_refund_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    refund_type: Mapped[str] = mapped_column(
        String(30), default="full", index=True
    )  # full|partial|conditional
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending|processing|completed|failed
    failure_reason: Mapped[str] = mapped_column(Text, default="")
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    processed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaymentReconciliation(Base):
    """Bank statement reconciliation records.
    
    Matches payment transactions against bank statements for accounting.
    Supports automated reconciliation via bank API integration.
    """
    __tablename__ = "payment_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    bank_name: Mapped[str] = mapped_column(String(100), default="")
    bank_account_no: Mapped[str] = mapped_column(String(60), default="", index=True)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    statement_reference: Mapped[str] = mapped_column(String(100), default="")
    statement_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    statement_balance: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    match_status: Mapped[str] = mapped_column(
        String(30), default="unmatched", index=True
    )  # matched|partial_match|unmatched|pending_review
    match_confidence_pct: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    difference_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    reconciled_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reconciled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaymentSettlement(Base):
    """Settlement records — funds transferred from gateway to merchant bank.
    
    Tracks when PayNET/FPX/Stripe settles funds to the company's bank account.
    Critical for cash flow forecasting and reconciliation.
    """
    __tablename__ = "payment_settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    gateway_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_gateways.id", ondelete="SET NULL"), nullable=True, index=True
    )
    settlement_no: Mapped[str] = mapped_column(String(60), unique=True, default="", index=True)
    gateway_settlement_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    settlement_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    fee_deducted: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    bank_account: Mapped[str] = mapped_column(String(60), default="")
    transaction_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending|processing|completed|failed|disputed
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaymentMethod(Base):
    """Saved payment methods for recurring payments.
    
    Supports tokenized cards, saved bank accounts, and e-wallet
    references for repeat transactions (e.g., monthly progress claims,
    subscription fees, retention releases).
    """
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    gateway_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_gateways.id", ondelete="SET NULL"), nullable=True
    )
    method_type: Mapped[str] = mapped_column(
        String(30), default="bank_account", index=True
    )  # bank_account|credit_card|debit_card|ewallet|fpx
    # Tokenized reference
    gateway_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    gateway_customer_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # Display info (masked)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    masked_identifier: Mapped[str] = mapped_column(
        String(60), default=""
    )  # e.g. "XXXX-1234" or "Maybank2u - a****@gmail.com"
    expiry_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expiry_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PaymentDispute(Base):
    """Dispute/chargeback tracking for payment transactions.
    
    Required for:
    - Chargeback management (credit card disputes)
    - Transaction disputes (FPX, bank transfer)
    - Regulatory reporting (BNM, payment networks)
    """
    __tablename__ = "payment_disputes"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dispute_no: Mapped[str] = mapped_column(String(60), unique=True, default="", index=True)
    dispute_type: Mapped[str] = mapped_column(
        String(30), default="chargeback", index=True
    )  # chargeback|transaction_dispute|unauthorized|duplicate|amount_mismatch|service_not_rendered
    amount_in_dispute: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_document_file_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="open", index=True
    )  # open|investigating|responded|won|lost|closed
    response_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    response_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    response_notes: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════
# E-INVOICE & TAX SYSTEM — Full Compliance Suite
# ══════════════════════════════════════════════════════════════════════════


class TaxCode(Base):
    """Tax codes and rates for different jurisdictions and tax types.
    
    Supports:
    - Malaysia: SST (6% service tax, 5-10% sales tax), VAT-equivalent
    - Singapore: GST (9%)
    - Indonesia: PPN (11%)
    - Thailand: VAT (7%)
    - Philippines: VAT (12%)
    - Vietnam: VAT (10%)
    - Brunei: GST (0%)
    - International: Withholding tax rates
    """
    __tablename__ = "tax_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    tax_type: Mapped[str] = mapped_column(
        String(30), default="sst", index=True
    )  # sst|gst|vat|ppn|withholding|income|stamp_duty|levy|customs
    jurisdiction: Mapped[str] = mapped_column(
        String(60), default="MY", index=True
    )  # MY|SG|ID|TH|PH|VN|BN|US|UK|AU|custom
    rate_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    is_recoverable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    config_json: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, nullable=True
    )  # {"sst_category": "A|B|C", "hs_codes": [...], "exemptions": [...]}
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EInvoice(Base):
    """E-invoice record — compliant with LHDN MyInvois / PEPPOL / national standards.
    
    Malaysia's LHDN MyInvois mandate (phased from 2024):
    - Phase 1 (Aug 2024): Revenue > RM100M
    - Phase 2 (Jul 2025): Revenue > RM50M
    - Phase 3 (Jul 2026): Revenue > RM25M
    - Phase 4 (Jul 2027): All taxpayers
    
    Supports:
    - MyInvois API (LHDN Malaysia)
    - PEPPOL BIS Billing 3.0 (international)
    - Custom JSON format for other jurisdictions
    """
    __tablename__ = "e_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Core identifiers
    invoice_no: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    invoice_type: Mapped[str] = mapped_column(
        String(30), default="invoice", index=True
    )  # invoice|credit_note|debit_note|refund|proforma|cancellation
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    
    # Supplier (issuer)
    supplier_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supplier_name: Mapped[str] = mapped_column(String(300), default="")
    supplier_tax_id: Mapped[str] = mapped_column(String(60), default="", index=True)
    supplier_sst_reg_no: Mapped[str] = mapped_column(String(60), default="")
    supplier_address: Mapped[str] = mapped_column(Text, default="")
    
    # Buyer (recipient)
    buyer_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    buyer_name: Mapped[str] = mapped_column(String(300), default="")
    buyer_tax_id: Mapped[str] = mapped_column(String(60), default="", index=True)
    buyer_sst_reg_no: Mapped[str] = mapped_column(String(60), default="")
    buyer_address: Mapped[str] = mapped_column(Text, default="")
    
    # Financial
    currency: Mapped[str] = mapped_column(String(3), default="MYR")
    exchange_rate: Mapped[float] = mapped_column(Numeric(10, 6), default=1.0)
    total_excluding_tax: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_including_tax: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_discount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_paid: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    balance_due: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    
    # References
    purchase_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    contract_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    original_invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("e_invoices.id", ondelete="SET NULL"), nullable=True
    )  # For credit/debit notes referencing original invoice
    
    # E-invoice submission status
    submission_status: Mapped[str] = mapped_column(
        String(30), default="draft", index=True
    )  # draft|pending_submission|submitted|validated|rejected|cancelled
    submission_method: Mapped[str] = mapped_column(
        String(30), default="api", index=True
    )  # api|web_portal|email|peppol|manual
    submission_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )  # MyInvoys submission UUID
    submission_uuid: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # MyInvoys / PEPPOL document UUID
    validation_status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending|passed|failed_with_warnings|failed_with_errors
    validation_errors: Mapped[Optional[dict]] = mapped_column(
        JSON, default=dict, nullable=True
    )
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    
    # LHDN MyInvoys specific
    myinvois_status: Mapped[str] = mapped_column(
        String(30), default="", index=True
    )  # Draft|Submitted|Validated|Rejected|Cancelled|Pending
    myinvois_long_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    myinvois_validation_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    
    # PEPPOL specific
    peppol_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    peppol_scheme: Mapped[str] = mapped_column(String(30), default="")
    
    # File attachments
    invoice_file_metadata_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="SET NULL"), nullable=True
    )
    signed_invoice_file_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="SET NULL"), nullable=True
    )
    
    # Audit
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[List["EInvoiceLineItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )
    tax_details: Mapped[List["EInvoiceTaxDetail"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class EInvoiceLineItem(Base):
    """Individual line item on an e-invoice."""
    __tablename__ = "e_invoice_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("e_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 4), default=0)
    unit: Mapped[str] = mapped_column(String(30), default="")
    unit_price: Mapped[float] = mapped_column(Numeric(16, 4), default=0)
    discount_pct: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    tax_code_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tax_codes.id", ondelete="SET NULL"), nullable=True
    )
    tax_rate_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    # Classification
    hs_code: Mapped[str] = mapped_column(String(30), default="")
    classification: Mapped[str] = mapped_column(String(60), default="")
    # Reference to procurement
    purchase_request_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    # Custom fields for jurisdiction-specific requirements
    custom_fields: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    invoice: Mapped["EInvoice"] = relationship(back_populates="items")


class EInvoiceTaxDetail(Base):
    """Tax breakdown summary per tax code on an e-invoice."""
    __tablename__ = "e_invoice_tax_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("e_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tax_code_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tax_codes.id", ondelete="SET NULL"), nullable=True
    )
    tax_code: Mapped[str] = mapped_column(String(30), default="", index=True)
    tax_rate_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    taxable_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    tax_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    exemption_reason: Mapped[str] = mapped_column(String(200), default="")
    is_exempt: Mapped[bool] = mapped_column(Boolean, default=False)

    invoice: Mapped["EInvoice"] = relationship(back_populates="tax_details")


class EInvoiceSubmissionLog(Base):
    """Detailed log of every e-invoice submission attempt.
    
    Required for audit compliance with LHDN / tax authorities.
    Each submission attempt is recorded regardless of success/failure.
    """
    __tablename__ = "e_invoice_submission_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("e_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    submission_method: Mapped[str] = mapped_column(String(30), default="api")
    endpoint_url: Mapped[str] = mapped_column(String(500), default="")
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str] = mapped_column(Text, default="")
    submitted_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    invoice: Mapped["EInvoice"] = relationship()


class WithholdingTax(Base):
    """Withholding tax tracking for cross-border payments and contracts.
    
    Malaysia withholding tax requirements:
    - Interest (15%), Royalty (10%), Contract payments (10%+3%),
    - Technical fees (10%), Management fees (10%)
    - Reduced rates under Double Taxation Agreements (DTAs)
    """
    __tablename__ = "withholding_taxes"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("e_invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payment_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient_entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payment_type: Mapped[str] = mapped_column(
        String(30), default="contract", index=True
    )  # contract|interest|royalty|technical_fee|management_fee|commission|rental|other
    gross_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    withholding_rate_pct: Mapped[float] = mapped_column(Numeric(6, 4), default=0)
    withholding_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    dta_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    dta_country: Mapped[str] = mapped_column(String(60), default="")
    dta_reduced_rate_pct: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 4), nullable=True
    )
    remittance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    remittance_reference: Mapped[str] = mapped_column(String(100), default="")
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending|remitted|certificate_received|exempt
    certificate_no: Mapped[str] = mapped_column(String(60), default="")
    certificate_file_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SSTReturn(Base):
    """SST (Sales & Service Tax) return filing records.
    
    Malaysia SST:
    - Service Tax: 6% (8% for certain services from Mar 2024)
    - Sales Tax: 5%, 10% (varies by goods category)
    - Filing frequency: every 2 months (bimonthly)
    """
    __tablename__ = "sst_returns"

    id: Mapped[int] = mapped_column(primary_key=True)
    return_no: Mapped[str] = mapped_column(String(60), unique=True, default="", index=True)
    taxable_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    taxable_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    filing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Service Tax
    total_service_taxable: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    service_tax_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=6.0)
    service_tax_due: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    
    # Sales Tax
    total_sales_taxable: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    sales_tax_rate_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=5.0)
    sales_tax_due: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    
    # Totals
    total_tax_due: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_penalty: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    total_paid: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    balance: Mapped[float] = mapped_column(Numeric(16, 2), default=0)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(30), default="draft", index=True
    )  # draft|calculated|ready_for_filing|filed|paid|assessed|disputed
    filing_method: Mapped[str] = mapped_column(
        String(30), default="online", index=True
    )  # online|manual|agent
    payment_method: Mapped[str] = mapped_column(String(30), default="")
    payment_reference: Mapped[str] = mapped_column(String(100), default="")
    
    # Audit
    prepared_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TaxInvoice(Base):
    """Tax invoice document — for jurisdictions requiring specific invoice formats.
    
    Different from e-invoice: this is the physical/PDF invoice that must
    contain specific tax information per jurisdiction.
    """
    __tablename__ = "tax_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    e_invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("e_invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    invoice_no: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(60), default="MY", index=True)
    template: Mapped[str] = mapped_column(String(100), default="standard")
    language: Mapped[str] = mapped_column(String(10), default="EN")  # EN|MS|CN|Tamil
    file_metadata_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="SET NULL"), nullable=True
    )
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sent_to_email: Mapped[str] = mapped_column(String(255), default="")
    delivery_status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending|sent|delivered|failed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TaxClearance(Base):
    """Tax clearance certificate tracking.
    
    Required for:
    - Contractor registration renewal (CIDB requires tax clearance)
    - Government project bidding
    - Company dissolution
    - Director exit
    """
    __tablename__ = "tax_clearance"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    certificate_no: Mapped[str] = mapped_column(String(60), unique=True, default="", index=True)
    clearance_type: Mapped[str] = mapped_column(
        String(30), default="general", index=True
    )  # general|contractor|dissolution|director_exit|bid_requirement
    issuing_authority: Mapped[str] = mapped_column(
        String(60), default="lhdn", index=True
    )  # lhdn|cidb|ssm|other
    issued_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="valid", index=True
    )  # valid|expired|revoked|pending
    file_metadata_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("file_metadata.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TaxAuditLog(Base):
    """Comprehensive audit log for all tax-related actions.
    
    Required for tax authority audits. Every tax calculation, submission,
    payment, and adjustment is recorded immutably.
    """
    __tablename__ = "tax_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True
    )  # invoice_created|invoice_submitted|invoice_validated|invoice_rejected|
      # invoice_cancelled|sst_calculated|sst_filed|sst_paid|withholding_remitted|
      # tax_clearance_issued|tax_clearance_expired|rate_changed|exemption_applied
    entity_type: Mapped[str] = mapped_column(
        String(30), default="", index=True
    )  # e_invoice|sst_return|withholding_tax|tax_clearance|tax_code
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    previous_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    performed_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ══════════════════════════════════════════════════════════════════════════
# AUTH & FILE STORAGE
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
