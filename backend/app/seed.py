"""Seed the database with built-in entity types and demo data."""
from datetime import date, datetime, timedelta

from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .security import Role, hash_password

# Demo accounts
DEMO_USERS = [
    ("admin@constructerp.dev", "admin123", "Ada Admin", Role.admin.value),
    ("pm@constructerp.dev", "pm123", "Pat Manager", Role.project_manager.value),
    ("accounting@constructerp.dev", "acct123", "Cash Ledger", Role.accounting.value),
    ("viewer@constructerp.dev", "viewer123", "Val Viewer", Role.viewer.value),
]


def seed_demo_users(db: Session) -> bool:
    if db.query(models.User).count() > 0:
        return False
    for email, password, full_name, role in DEMO_USERS:
        db.add(models.User(
            email=email, full_name=full_name,
            hashed_password=hash_password(password), role=role,
        ))
    db.commit()
    return True


# ══════════════════════════════════════════════════════════════════════════
# BUILT-IN ENTITY TYPES
# ══════════════════════════════════════════════════════════════════════════

BUILTIN_TYPES = {
    "project": {
        "name": "Project",
        "plural_name": "Projects",
        "icon": "building2",
        "color": "amber",
        "attributes": [
            ("location", "Location", "text", True, True),
            ("budget", "Budget", "money", True, True),
            ("duration", "Duration", "string", True, False),
            ("progress", "Progress (%)", "number", True, True),
            ("start_date", "Start Date", "date", False, True),
            ("end_date", "End Date", "date", False, True),
            ("description", "Description", "text", False, False),
        ],
    },
    "vendor": {
        "name": "Vendor",
        "plural_name": "Vendors",
        "icon": "building",
        "color": "blue",
        "attributes": [
            ("registration_no", "Registration No.", "string", True, True),
            ("tax_id", "Tax ID", "string", False, True),
            ("contact_person", "Contact Person", "string", True, False),
            ("email", "Email", "string", True, False),
            ("phone", "Phone", "string", False, False),
            ("address", "Address", "text", False, False),
            ("category", "Category", "select", True, True),
            ("classification", "Classification", "string", False, True),
            ("pre_qualified", "Pre-Qualified", "boolean", True, True),
            ("pre_qual_expiry", "Pre-Qual Expiry", "date", False, True),
        ],
    },
    "tender": {
        "name": "Tender",
        "plural_name": "Tenders",
        "icon": "fileText",
        "color": "purple",
        "attributes": [
            ("description", "Description", "text", False, False),
            ("category", "Category", "select", True, True),
            ("tender_open_at", "Open Date", "datetime", True, True),
            ("tender_close_at", "Close Date", "datetime", True, True),
            ("budget_estimate", "Budget Estimate", "money", True, True),
            ("currency", "Currency", "string", True, False),
        ],
    },
    "contract": {
        "name": "Contract",
        "plural_name": "Contracts",
        "icon": "fileSignature",
        "color": "green",
        "attributes": [
            ("description", "Description", "text", False, False),
            ("contract_value", "Contract Value", "money", True, True),
            ("start_date", "Start Date", "date", True, True),
            ("end_date", "End Date", "date", True, True),
        ],
    },
    "boq_item": {
        "name": "BOQ Item",
        "plural_name": "BOQ Items",
        "icon": "list",
        "color": "cyan",
        "attributes": [
            ("item_no", "Item No.", "string", True, True),
            ("description", "Description", "text", True, False),
            ("unit", "Unit", "string", True, False),
            ("quantity", "Quantity", "number", True, True),
            ("rate_estimate", "Rate Estimate", "money", True, True),
            ("category", "Category", "string", False, True),
        ],
    },
    "bidder": {
        "name": "Bidder",
        "plural_name": "Bidders",
        "icon": "users",
        "color": "orange",
        "attributes": [
            ("bid_amount", "Bid Amount", "money", True, True),
            ("technical_score", "Technical Score", "number", True, True),
            ("financial_score", "Financial Score", "number", True, True),
            ("total_score", "Total Score", "number", True, True),
            ("submission_time", "Submission Time", "datetime", False, True),
            ("notes", "Notes", "text", False, False),
        ],
    },
    "defect": {
        "name": "Defect",
        "plural_name": "Defects",
        "icon": "alertTriangle",
        "color": "red",
        "attributes": [
            ("description", "Description", "text", False, False),
            ("location", "Location", "string", True, True),
            ("severity", "Severity", "select", True, True),
            ("assigned_to", "Assigned To", "user", True, False),
            ("target_resolution_date", "Target Resolution", "date", False, True),
            ("resolution_notes", "Resolution Notes", "text", False, False),
        ],
    },
    "inspection": {
        "name": "Inspection",
        "plural_name": "Inspections",
        "icon": "clipboardCheck",
        "color": "teal",
        "attributes": [
            ("description", "Description", "text", False, False),
            ("location", "Location", "string", True, True),
            ("inspection_type", "Type", "select", True, True),
            ("scheduled_date", "Scheduled Date", "datetime", True, True),
            ("result", "Result", "text", False, False),
        ],
    },
    "site_diary": {
        "name": "Site Diary",
        "plural_name": "Site Diaries",
        "icon": "bookOpen",
        "color": "slate",
        "attributes": [
            ("entry_date", "Entry Date", "date", True, True),
            ("weather", "Weather", "string", False, False),
            ("temperature", "Temperature", "string", False, False),
            ("work_summary", "Work Summary", "text", True, False),
            ("issues", "Issues", "text", False, False),
            ("safety_notes", "Safety Notes", "text", False, False),
            ("labour_count", "Labour Count", "number", True, True),
            ("equipment_on_site", "Equipment", "text", False, False),
        ],
    },
    "submittal": {
        "name": "Submittal",
        "plural_name": "Submittals",
        "icon": "fileUp",
        "color": "indigo",
        "attributes": [
            ("description", "Description", "text", False, False),
            ("category", "Category", "select", True, True),
            ("review_comments", "Review Comments", "text", False, False),
            ("due_date", "Due Date", "date", False, True),
        ],
    },
    "consultant_rfp": {
        "name": "Consultant RFP",
        "plural_name": "Consultant RFPs",
        "icon": "fileSearch",
        "color": "pink",
        "attributes": [
            ("description", "Description", "text", False, False),
            ("scope_of_work", "Scope of Work", "text", True, False),
            ("consultant_category", "Category", "select", True, True),
            ("rfp_open_at", "RFP Open Date", "datetime", True, True),
            ("rfp_close_at", "RFP Close Date", "datetime", True, True),
            ("budget_estimate", "Budget Estimate", "money", True, True),
        ],
    },
    "cost_plan": {
        "name": "Cost Plan",
        "plural_name": "Cost Plans",
        "icon": "dollarSign",
        "color": "emerald",
        "attributes": [
            ("version", "Version", "number", True, False),
            ("total_estimated", "Total Estimated", "money", True, True),
            ("total_approved", "Total Approved", "money", True, True),
            ("notes", "Notes", "text", False, False),
        ],
    },
    "purchase_request": {
        "name": "Purchase Request",
        "plural_name": "Purchase Requests",
        "icon": "shoppingCart",
        "color": "yellow",
        "attributes": [
            ("description", "Description", "text", False, False),
            ("notes", "Notes", "text", False, False),
        ],
    },
    "rfq": {
        "name": "RFQ",
        "plural_name": "RFQs",
        "icon": "fileQuestion",
        "color": "violet",
        "attributes": [
            ("description", "Description", "text", False, False),
            ("response_deadline", "Response Deadline", "datetime", True, True),
        ],
    },
    "goods_receipt": {
        "name": "Goods Receipt",
        "plural_name": "Goods Receipts",
        "icon": "package",
        "color": "lime",
        "attributes": [
            ("supplier_name", "Supplier", "string", True, True),
            ("delivery_note_no", "Delivery Note No.", "string", False, True),
            ("received_date", "Received Date", "date", True, True),
            ("notes", "Notes", "text", False, False),
        ],
    },
    "e_invoice": {
        "name": "E-Invoice",
        "plural_name": "E-Invoices",
        "icon": "receipt",
        "color": "rose",
        "attributes": [
            ("supplier_name", "Supplier", "string", True, True),
            ("invoice_date", "Invoice Date", "date", True, True),
            ("due_date", "Due Date", "date", False, True),
            ("total_amount", "Total Amount", "money", True, True),
            ("tax_amount", "Tax Amount", "money", True, True),
            ("net_amount", "Net Amount", "money", True, True),
            ("notes", "Notes", "text", False, False),
        ],
    },
}


def seed_builtin_types(db: Session) -> bool:
    """Create built-in entity types and their attribute definitions."""
    if db.query(models.EntityType).count() > 0:
        return False

    for slug, config in BUILTIN_TYPES.items():
        etype = models.EntityType(
            slug=slug,
            name=config["name"],
            plural_name=config["plural_name"],
            icon=config.get("icon", ""),
            color=config.get("color", ""),
            is_builtin=True,
        )
        db.add(etype)
        db.flush()

        for i, (attr_slug, attr_name, attr_type, is_searchable, is_filterable) in enumerate(
            config["attributes"]
        ):
            db.add(models.AttributeDefinition(
                entity_type_id=etype.id,
                slug=attr_slug,
                name=attr_name,
                attr_type=attr_type,
                is_searchable=is_searchable,
                is_filterable=is_filterable,
                display_order=i,
            ))

    db.commit()
    return True


# ══════════════════════════════════════════════════════════════════════════
# DEMO DATA
# ══════════════════════════════════════════════════════════════════════════


def _get_type(db: Session, slug: str) -> models.EntityType:
    return db.query(models.EntityType).filter(models.EntityType.slug == slug).first()


def _create_entity(
    db: Session, type_slug: str, title: str, ref: str = "",
    status: str = "active", parent_id: Optional[int] = None, attrs: Optional[dict] = None,
) -> models.Entity:
    etype = _get_type(db, type_slug)
    entity = models.Entity(
        entity_type_id=etype.id,
        title=title,
        reference_no=ref,
        status=status,
        parent_id=parent_id,
    )
    db.add(entity)
    db.flush()

    if attrs:
        for slug, value in attrs.items():
            ea = models.EntityAttribute(entity_id=entity.id, slug=slug)
            if isinstance(value, bool):
                ea.value_boolean = value
            elif isinstance(value, (int, float)):
                ea.value_number = float(value)
            elif isinstance(value, (date, datetime)):
                ea.value_datetime = value if isinstance(value, datetime) else datetime.combine(value, datetime.min.time())
            else:
                ea.value_string = str(value)
            db.add(ea)

    db.add(models.EntityActivity(
        entity_id=entity.id,
        activity_type="created",
        description=f"{etype.name} '{title}' created (demo seed)",
    ))
    return entity


def _relate(db: Session, source_id: int, target_id: int, rel_type: str, label: str = ""):
    db.add(models.EntityRelationship(
        source_id=source_id,
        target_id=target_id,
        relationship_type=rel_type,
        label=label,
    ))


def seed_demo_data(db: Session) -> bool:
    """Create demo entities if none exist."""
    if db.query(models.Entity).count() > 0:
        return False

    now = datetime.utcnow()

    # ── Projects ──────────────────────────────────────────────────────
    p1 = _create_entity(db, "project", "Riverside Tower", "PRJ-2026-001",
                        attrs={"location": "123 Main St", "budget": 1_450_000,
                               "duration": "18 months", "progress": 62,
                               "description": "Mixed-use commercial tower"})
    p2 = _create_entity(db, "project", "Harbor Bridge", "PRJ-2026-002",
                        attrs={"location": "456 Bay Ave", "budget": 3_200_000,
                               "duration": "24 months", "progress": 34,
                               "description": "Suspension bridge rehabilitation"})
    p3 = _create_entity(db, "project", "Greenfield School", "PRJ-2026-003",
                        attrs={"location": "789 Oak Dr", "budget": 890_000,
                               "duration": "12 months", "progress": 78,
                               "description": "K-12 educational facility"})

    # ── Vendors ───────────────────────────────────────────────────────
    v1 = _create_entity(db, "vendor", "BuildCo Construction Sdn Bhd", "VEN-001",
                        attrs={"registration_no": "BC-2020-001",
                               "contact_person": "Ahmad Razak", "email": "ahmad@buildco.my",
                               "phone": "+6012-345-6789", "category": "contractor",
                               "classification": "Grade 7", "pre_qualified": True,
                               "pre_qual_expiry": date(2027, 6, 30)})
    v2 = _create_entity(db, "vendor", "SteelMaster Fabricators", "VEN-002",
                        attrs={"registration_no": "SM-2019-045",
                               "contact_person": "Lim Wei Ming", "email": "weiming@steelmaster.my",
                               "category": "supplier", "classification": "Grade 5",
                               "pre_qualified": True, "pre_qual_expiry": date(2026, 12, 31)})
    v3 = _create_entity(db, "vendor", "MEP Solutions PLT", "VEN-003",
                        attrs={"registration_no": "MEP-2021-012",
                               "contact_person": "Siti Nurhaliza", "email": "siti@mepsolutions.my",
                               "category": "contractor", "classification": "Grade 6",
                               "pre_qualified": False})
    v4 = _create_entity(db, "vendor", "DesignWorks Architects", "VEN-004",
                        attrs={"registration_no": "DW-2018-033",
                               "contact_person": "Kevin Tan", "email": "kevin@designworks.my",
                               "category": "consultant", "classification": "Grade 4",
                               "pre_qualified": True, "pre_qual_expiry": date(2027, 3, 15)})

    # ── Tenders ────────────────────────────────────────────────────────
    t1 = _create_entity(db, "tender", "Riverside Tower — Structural Steel Package",
                        "TND-2026-001", status="open",
                        attrs={"description": "Supply and installation of structural steel",
                               "category": "selective",
                               "tender_open_at": now - timedelta(days=7),
                               "tender_close_at": now + timedelta(days=23),
                               "budget_estimate": 2_500_000, "currency": "MYR"})
    t2 = _create_entity(db, "tender", "Harbor Bridge — Cable Rehabilitation",
                        "TND-2026-002", status="draft",
                        attrs={"description": "Replacement and tensioning of suspension cables",
                               "category": "public", "budget_estimate": 4_800_000, "currency": "MYR"})

    # ── BOQ Items ──────────────────────────────────────────────────────
    b1 = _create_entity(db, "boq_item", "Structural steel beams (Grade 50)",
                        parent_id=t1.id,
                        attrs={"item_no": "1.1", "description": "Grade 50 steel beams",
                               "unit": "ton", "quantity": 120, "rate_estimate": 8500,
                               "category": "Steelwork"})
    b2 = _create_entity(db, "boq_item", "Steel columns (box section)",
                        parent_id=t1.id,
                        attrs={"item_no": "1.2", "description": "Box section columns",
                               "unit": "ton", "quantity": 85, "rate_estimate": 9200,
                               "category": "Steelwork"})
    b3 = _create_entity(db, "boq_item", "Fireproofing spray application",
                        parent_id=t1.id,
                        attrs={"item_no": "2.1", "description": "Fireproofing spray",
                               "unit": "m²", "quantity": 3200, "rate_estimate": 45,
                               "category": "Fireproofing"})

    # ── Bidders ────────────────────────────────────────────────────────
    bid1 = _create_entity(db, "bidder", "BuildCo Construction — Steel Bid",
                          parent_id=t1.id, status="submitted",
                          attrs={"bid_amount": 2_350_000, "technical_score": 88,
                                 "financial_score": 82, "total_score": 85.6,
                                 "submission_time": now - timedelta(days=1)})
    bid2 = _create_entity(db, "bidder", "SteelMaster — Steel Bid",
                          parent_id=t1.id, status="submitted",
                          attrs={"bid_amount": 2_180_000, "technical_score": 92,
                                 "financial_score": 78, "total_score": 86.4,
                                 "submission_time": now - timedelta(hours=6)})

    # ── Defects ────────────────────────────────────────────────────────
    _create_entity(db, "defect", "Crack in column B-12", "DEF-001",
                   parent_id=p1.id, status="open",
                   attrs={"description": "Hairline crack on ground floor column",
                          "location": "Ground Floor - Column B-12",
                          "severity": "major"})
    _create_entity(db, "defect", "Paint peeling on level 3 walls", "DEF-002",
                   parent_id=p1.id, status="in_progress",
                   attrs={"description": "Paint peeling near window frames",
                          "location": "Level 3 - East Wing",
                          "severity": "minor"})

    # ── Site Diaries ──────────────────────────────────────────────────
    _create_entity(db, "site_diary", "Daily Log - Day 45",
                   parent_id=p1.id,
                   attrs={"entry_date": date.today(), "weather": "Sunny 32°C",
                          "work_summary": "Steel erection ongoing on floor 8",
                          "labour_count": 45, "safety_notes": "No incidents"})
    _create_entity(db, "site_diary", "Daily Log - Day 46",
                   parent_id=p1.id,
                   attrs={"entry_date": date.today(), "weather": "Partly cloudy 29°C",
                          "work_summary": "Concrete pouring for floor 8 slab",
                          "labour_count": 52, "safety_notes": "All clear"})

    # ── Consultant RFPs ───────────────────────────────────────────────
    rfp1 = _create_entity(db, "consultant_rfp",
                          "Architectural Design — Riverside Tower", "RFP-2026-001",
                          status="open",
                          attrs={"scope_of_work": "Full architectural design for 20-storey tower",
                                 "consultant_category": "architect",
                                 "budget_estimate": 250_000,
                                 "rfp_open_at": now - timedelta(days=3),
                                 "rfp_close_at": now + timedelta(days=27)})

    # ── Relationships ─────────────────────────────────────────────────
    # Project has vendors
    _relate(db, p1.id, v1.id, "has_vendor")
    _relate(db, p1.id, v2.id, "has_vendor")
    _relate(db, p1.id, v3.id, "has_vendor")
    _relate(db, p1.id, v4.id, "has_consultant")

    # Project has tenders
    _relate(db, p1.id, t1.id, "has_tender")
    _relate(db, p2.id, t2.id, "has_tender")

    # Tender has BOQ items
    _relate(db, t1.id, b1.id, "has_boq_item")
    _relate(db, t1.id, b2.id, "has_boq_item")
    _relate(db, t1.id, b3.id, "has_boq_item")

    # Tender has bidders
    _relate(db, t1.id, bid1.id, "has_bidder")
    _relate(db, t1.id, bid2.id, "has_bidder")

    # Vendor bids on tender
    _relate(db, v1.id, t1.id, "bids_on")
    _relate(db, v2.id, t1.id, "bids_on")

    # Project has defects
    _relate(db, p1.id, 1, "has_defect")  # defect IDs
    _relate(db, p1.id, 2, "has_defect")

    # Project has RFPs
    _relate(db, p1.id, rfp1.id, "has_rfp")

    db.commit()
    return True
