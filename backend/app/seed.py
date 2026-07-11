"""Seed the database with the same demo data the frontend ships with."""
from sqlalchemy.orm import Session

from . import models
from .security import Role, hash_password

# Demo accounts (DEV ONLY). Documented in backend/README.md.
DEMO_USERS = [
    ("admin@constructerp.dev", "admin123", "Ada Admin", Role.admin.value),
    ("pm@constructerp.dev", "pm123", "Pat Manager", Role.project_manager.value),
    ("accounting@constructerp.dev", "acct123", "Cash Ledger", Role.accounting.value),
    ("viewer@constructerp.dev", "viewer123", "Val Viewer", Role.viewer.value),
]


def seed_demo_users(db: Session) -> bool:
    """Create demo users if none exist. Returns True if seeded."""
    if db.query(models.User).count() > 0:
        return False
    for email, password, full_name, role in DEMO_USERS:
        db.add(models.User(
            email=email, full_name=full_name,
            hashed_password=hash_password(password), role=role,
        ))
    db.commit()
    return True


def seed_if_empty(db: Session) -> bool:
    """Populate demo data only when the projects table is empty. Returns True if seeded."""
    if db.query(models.Project).count() > 0:
        return False

    db.add_all([
        models.Project(name="Riverside Tower", location="123 Main St", budget=1_450_000,
                       duration="18 months", description="Mixed-use commercial tower",
                       status="active", progress=62),
        models.Project(name="Harbor Bridge", location="456 Bay Ave", budget=3_200_000,
                       duration="24 months", description="Suspension bridge rehabilitation",
                       status="active", progress=34),
        models.Project(name="Greenfield School", location="789 Oak Dr", budget=890_000,
                       duration="12 months", description="K-12 educational facility",
                       status="active", progress=78),
    ])

    db.add_all([
        models.Task(name="Site Preparation", start=0, width=18, color="amber"),
        models.Task(name="Foundation Excavation", start=5, width=22, color="blue"),
        models.Task(name="Concrete Foundation", start=15, width=25, color="green"),
        models.Task(name="Structural Steel", start=30, width=30, color="purple"),
        models.Task(name="MEP Rough-In", start=45, width=28, color="rose"),
        models.Task(name="Interior Finishes", start=60, width=35, color="cyan"),
    ])

    db.add_all([
        models.Resource(category="labor", name="Carpenters", required=15, available=12),
        models.Resource(category="labor", name="Electricians", required=8, available=6),
        models.Resource(category="labor", name="Operators", required=4, available=4),
        models.Resource(category="labor", name="Laborers", required=20, available=18),
        models.Resource(category="equipment", name="Excavators", required=3, available=3),
        models.Resource(category="equipment", name="Cranes", required=2, available=1),
        models.Resource(category="equipment", name="Forklifts", required=4, available=4),
        models.Resource(category="equipment", name="Dump Trucks", required=6, available=5),
        models.Resource(category="materials", name="Steel", required=85, available=42, unit="tons"),
        models.Resource(category="materials", name="Concrete", required=600, available=320, unit="yd³"),
        models.Resource(category="materials", name="Lumber", required=18000, available=12000, unit="bdft"),
        models.Resource(category="materials", name="Rebar", required=32, available=18, unit="tons"),
    ])

    db.add_all([
        models.BudgetItem(category="Site Work", budget=180_000, committed=165_000, spent=148_000),
        models.BudgetItem(category="Foundation", budget=280_000, committed=260_000, spent=245_000),
        models.BudgetItem(category="Structure", budget=650_000, committed=520_000, spent=480_000),
        models.BudgetItem(category="MEP", budget=220_000, committed=180_000, spent=155_000),
        models.BudgetItem(category="Finishes", budget=120_000, committed=95_000, spent=64_000),
    ])

    db.add_all([
        models.PurchaseOrder(po_number="PO-2024-038", supplier="BuildCo Steel", item="Structural Steel",
                             qty="42 tons", amount=168_000, status="Delivered", delivery="Jul 2"),
        models.PurchaseOrder(po_number="PO-2024-039", supplier="Concrete Supply Co", item="Ready-Mix Concrete",
                             qty="320 yd³", amount=96_000, status="In Transit", delivery="Jul 10"),
        models.PurchaseOrder(po_number="PO-2024-040", supplier="Electrical Wholesale", item="Cable & Wiring",
                             qty="5,000 ft", amount=24_500, status="Ordered", delivery="Jul 15"),
        models.PurchaseOrder(po_number="PO-2024-041", supplier="Lumber Yard Inc", item="Framing Lumber",
                             qty="12,000 bdft", amount=38_400, status="Pending", delivery="Jul 22"),
        models.PurchaseOrder(po_number="PO-2024-042", supplier="HVAC Distributors", item="HVAC Units",
                             qty="6 units", amount=72_000, status="In Transit", delivery="Jul 18"),
    ])

    db.add_all([
        models.Subcontractor(name="Elite Electrical", initials="EC", trade="Electrical",
                             contract=185_000, progress=62, color="from-blue-500 to-cyan-600"),
        models.Subcontractor(name="Metro Plumbing", initials="MP", trade="Plumbing",
                             contract=142_000, progress=45, color="from-green-500 to-emerald-600"),
        models.Subcontractor(name="Steel Fabricators Inc", initials="SF", trade="Structural",
                             contract=420_000, progress=88, color="from-amber-500 to-orange-600"),
    ])

    db.commit()
    return True
