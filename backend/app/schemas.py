"""Pydantic v2 schemas for the AI-native ERP entity system.

Instead of 50+ entity-specific schemas, we have:
  - EntityCreate/Read/Update — universal, accepts dynamic attributes
  - EntityType/AttributeDefinition — metamodel schemas
  - EntityRelationship — graph edge schemas
  - EntityActivity/EntityComment — activity stream schemas
  - EntityFile — file attachment schemas
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ORM = ConfigDict(from_attributes=True)

RoleLiteral = Literal["admin", "project_manager", "accounting", "viewer"]


# ══════════════════════════════════════════════════════════════════════════
# AUTH / Users
# ══════════════════════════════════════════════════════════════════════════


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = ""


class UserRegister(UserBase):
    password: str = Field(min_length=6, max_length=128)


class UserAdminCreate(UserRegister):
    role: RoleLiteral = "viewer"


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[RoleLiteral] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)


class UserRead(UserBase):
    model_config = ORM
    id: int
    role: RoleLiteral
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: RoleLiteral
    expires_in: int


# ══════════════════════════════════════════════════════════════════════════
# FILE METADATA
# ══════════════════════════════════════════════════════════════════════════


class FileMetadataBase(BaseModel):
    original_name: str = Field(min_length=1, max_length=500)
    content_type: str = ""
    size_bytes: int = 0
    checksum_sha256: str = ""


class FileMetadataCreate(FileMetadataBase):
    storage_path: str = Field(min_length=1, max_length=1000)
    version: int = 1
    uploaded_by: Optional[int] = None


class FileMetadataRead(FileMetadataBase):
    model_config = ORM
    id: int
    storage_path: str
    version: int
    uploaded_by: Optional[int] = None
    uploaded_at: datetime
    is_deleted: bool


class UploadResponse(BaseModel):
    file_id: int
    original_name: str
    size_bytes: int
    storage_path: str
    checksum_sha256: str
    upload_url: str = ""


# ══════════════════════════════════════════════════════════════════════════
# ENTITY SYSTEM — CORE
# ══════════════════════════════════════════════════════════════════════════


class AttributeValue(BaseModel):
    """A single attribute value for an entity.
    
    Only one value_* field should be set, matching the attr_type.
    """
    slug: str = Field(min_length=1, max_length=60)
    value_string: Optional[str] = None
    value_text: Optional[str] = None
    value_number: Optional[float] = None
    value_date: Optional[date] = None
    value_datetime: Optional[datetime] = None
    value_boolean: Optional[bool] = None
    value_json: Optional[Dict[str, Any]] = None
    value_entity_id: Optional[int] = None
    value_user_id: Optional[int] = None


class EntityCreate(BaseModel):
    """Create any entity in the system.
    
    Example for a project:
    {
      "entity_type_slug": "project",
      "title": "Riverside Tower",
      "reference_no": "PRJ-2026-001",
      "status": "active",
      "parent_id": null,
      "attributes": [
        {"slug": "location", "value_string": "123 Main St"},
        {"slug": "budget", "value_number": 1450000},
        {"slug": "duration", "value_string": "18 months"},
        {"slug": "progress", "value_number": 62}
      ]
    }
    """
    entity_type_slug: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=500)
    reference_no: str = ""
    status: str = "active"
    parent_id: Optional[int] = None
    summary: str = ""
    attributes: List[AttributeValue] = []


class EntityUpdate(BaseModel):
    """Update any entity. Only provided fields are changed."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    reference_no: Optional[str] = None
    status: Optional[str] = None
    parent_id: Optional[int] = None
    summary: Optional[str] = None
    attributes: Optional[List[AttributeValue]] = None


class EntityAttributeRead(BaseModel):
    """Attribute value as returned in API responses."""
    model_config = ORM
    id: int
    slug: str
    value_string: Optional[str] = None
    value_text: Optional[str] = None
    value_number: Optional[float] = None
    value_date: Optional[date] = None
    value_datetime: Optional[datetime] = None
    value_boolean: Optional[bool] = None
    value_json: Optional[Dict[str, Any]] = None
    value_entity_id: Optional[int] = None
    value_user_id: Optional[int] = None


class EntityRead(BaseModel):
    """Any entity in the system, with all its attributes."""
    model_config = ORM
    id: int
    entity_type_id: int
    title: str
    reference_no: str
    status: str
    parent_id: Optional[int] = None
    owner_id: Optional[int] = None
    tenant_id: str
    summary: str
    ai_embedding_id: str
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None
    attributes: List[EntityAttributeRead] = []


class EntityBrief(BaseModel):
    """Minimal entity representation for relationships and lists."""
    model_config = ORM
    id: int
    title: str
    reference_no: str
    status: str
    entity_type_id: int


# ══════════════════════════════════════════════════════════════════════════
# ENTITY SYSTEM — METAMODEL
# ══════════════════════════════════════════════════════════════════════════


class AttributeDefinitionCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    attr_type: str = "string"
    is_required: bool = False
    is_unique: bool = False
    is_searchable: bool = True
    is_filterable: bool = True
    default_value: Optional[str] = None
    options_json: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    display_order: int = 0


class AttributeDefinitionRead(BaseModel):
    model_config = ORM
    id: int
    entity_type_id: int
    slug: str
    name: str
    description: str
    attr_type: str
    is_required: bool
    is_unique: bool
    is_searchable: bool
    is_filterable: bool
    default_value: Optional[str] = None
    options_json: Optional[Dict[str, Any]] = None
    validation_rules: Optional[Dict[str, Any]] = None
    display_order: int
    is_active: bool
    created_at: datetime


class EntityTypeCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    plural_name: str = ""
    description: str = ""
    icon: str = ""
    color: str = ""
    config_json: Optional[Dict[str, Any]] = None
    attributes: List[AttributeDefinitionCreate] = []


class EntityTypeRead(BaseModel):
    model_config = ORM
    id: int
    slug: str
    name: str
    plural_name: str
    description: str
    icon: str
    color: str
    is_builtin: bool
    is_active: bool
    config_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    attributes: List[AttributeDefinitionRead] = []


# ══════════════════════════════════════════════════════════════════════════
# ENTITY SYSTEM — GRAPH
# ══════════════════════════════════════════════════════════════════════════


class EntityRelationshipCreate(BaseModel):
    source_id: int
    target_id: int
    relationship_type: str = Field(min_length=1, max_length=60)
    label: str = ""
    metadata_json: Optional[Dict[str, Any]] = None


class EntityRelationshipRead(BaseModel):
    model_config = ORM
    id: int
    source_id: int
    target_id: int
    relationship_type: str
    label: str
    metadata_json: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    created_by: Optional[int] = None


# ══════════════════════════════════════════════════════════════════════════
# ENTITY SYSTEM — ACTIVITY STREAM
# ══════════════════════════════════════════════════════════════════════════


class EntityActivityRead(BaseModel):
    model_config = ORM
    id: int
    entity_id: int
    activity_type: str
    description: str
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    performed_by: Optional[int] = None
    is_ai_generated: bool
    created_at: datetime


# ══════════════════════════════════════════════════════════════════════════
# ENTITY SYSTEM — COMMENTS
# ══════════════════════════════════════════════════════════════════════════


class EntityCommentCreate(BaseModel):
    entity_id: int
    parent_id: Optional[int] = None
    body: str = Field(min_length=1)
    comment_type: str = "comment"


class EntityCommentRead(BaseModel):
    model_config = ORM
    id: int
    entity_id: int
    parent_id: Optional[int] = None
    body: str
    comment_type: str
    author_id: Optional[int] = None
    is_ai_generated: bool
    created_at: datetime


# ══════════════════════════════════════════════════════════════════════════
# ENTITY SYSTEM — FILES
# ══════════════════════════════════════════════════════════════════════════


class EntityFileCreate(BaseModel):
    entity_id: int
    file_metadata_id: int
    file_category: str = ""
    title: str = ""
    description: str = ""
    is_encrypted: bool = False


class EntityFileRead(BaseModel):
    model_config = ORM
    id: int
    entity_id: int
    file_metadata_id: int
    file_category: str
    title: str
    description: str
    is_encrypted: bool
    uploaded_by: Optional[int] = None
    created_at: datetime


# ══════════════════════════════════════════════════════════════════════════
# GRAPH TRAVERSAL
# ══════════════════════════════════════════════════════════════════════════


class GraphQuery(BaseModel):
    """Query the entity graph.
    
    Example: find all vendors that bid on tenders for project 1
    {
      "source_type": "project",
      "source_id": 1,
      "relationship_types": ["has_tender"],
      "target_types": ["tender"],
      "depth": 2
    }
    """
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    relationship_types: List[str] = []
    depth: int = 1


class GraphNode(BaseModel):
    """A node in the entity graph response."""
    entity: EntityBrief
    relationships: List[EntityRelationshipRead] = []


class GraphResponse(BaseModel):
    """Response from a graph traversal query."""
    nodes: List[GraphNode] = []
    edges: List[EntityRelationshipRead] = []
