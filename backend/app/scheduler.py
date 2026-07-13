"""Scheduler for tender countdown and auto-close.

Runs in a background thread, checking for:
  1. Tenders that have passed their close date → auto-close them
  2. Tenders closing within the threshold → log notification

Uses the entity system: tenders are entities with entity_type_slug='tender'
and have a 'tender_close_at' attribute.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import SessionLocal

logger = logging.getLogger("constructerp.scheduler")

# Global flag to stop the scheduler
_running = False
_thread: Optional[threading.Thread] = None


def _get_tender_close_at(entity: models.Entity) -> Optional[datetime]:
    """Extract tender_close_at from entity attributes."""
    for attr in entity.attributes:
        if attr.slug == "tender_close_at" and attr.value_datetime:
            return attr.value_datetime
    return None


def _set_tender_status(entity: models.Entity, db: Session, new_status: str):
    """Update a tender's status and record activity."""
    old_status = entity.status
    entity.status = new_status
    db.add(models.EntityActivity(
        entity_id=entity.id,
        activity_type="status_changed",
        description=f"Tender auto-closed: '{old_status}' -> '{new_status}'",
        previous_state={"status": old_status},
        new_state={"status": new_status},
        is_ai_generated=True,
    ))
    db.commit()


def _scheduler_loop():
    """Main scheduler loop — runs every tender_auto_close_interval seconds."""
    global _running
    logger.info("Tender scheduler started (interval=%ds)", settings.tender_auto_close_interval)

    while _running:
        try:
            db = SessionLocal()
            try:
                _check_tenders(db)
            finally:
                db.close()
        except Exception as e:
            logger.error("Scheduler error: %s", e)

        # Sleep in 1-second intervals so we can stop quickly
        for _ in range(settings.tender_auto_close_interval):
            if not _running:
                break
            time.sleep(1)

    logger.info("Tender scheduler stopped")


def _check_tenders(db: Session):
    """Check all open tenders for auto-close conditions."""
    now = datetime.utcnow()

    # Find the tender entity type
    tender_type = db.query(models.EntityType).filter(
        models.EntityType.slug == "tender"
    ).first()
    if tender_type is None:
        return

    # Get all open tenders with their attributes loaded
    tenders = (
        db.query(models.Entity)
        .filter(
            models.Entity.entity_type_id == tender_type.id,
            models.Entity.status.in_(["open", "closing_soon"]),
            models.Entity.archived_at.is_(None),
        )
        .all()
    )

    for tender in tenders:
        close_at = _get_tender_close_at(tender)
        if close_at is None:
            continue

        # Ensure close_at is timezone-aware for comparison
        if close_at.tzinfo is None:
            close_at = close_at.replace(tzinfo=timezone.utc)
        now_utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now

        hours_until_close = (close_at - now_utc).total_seconds() / 3600

        if hours_until_close <= 0:
            # Tender has closed — auto-close it
            _set_tender_status(tender, db, "evaluation")
            logger.info("Auto-closed tender %s (ID=%d)", tender.reference_no, tender.id)

        elif hours_until_close <= settings.tender_countdown_threshold_hours:
            # Tender is closing soon — update status if not already set
            if tender.status == "open":
                _set_tender_status(tender, db, "closing_soon")
                logger.info(
                    "Tender %s (ID=%d) closing in %.1f hours",
                    tender.reference_no, tender.id, hours_until_close,
                )


def start_scheduler():
    """Start the tender scheduler in a background thread."""
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_scheduler_loop, daemon=True, name="tender-scheduler")
    _thread.start()


def stop_scheduler():
    """Stop the tender scheduler."""
    global _running
    _running = False
    logger.info("Tender scheduler stopping...")
