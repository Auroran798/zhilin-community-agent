from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy.orm import Session

from .models import Announcement, OutboxEvent
from .time import as_utc, utc_now


def enqueue_announcement_index(db: Session, announcement: Announcement, actor_id: str | None) -> OutboxEvent:
    version = announcement.published_at or announcement.updated_at or utc_now()
    key = f"announcement-index:{announcement.id}:{announcement.status}:{as_utc(version).isoformat()}"
    existing = db.query(OutboxEvent).filter_by(idempotency_key=key).first()
    if existing:
        return existing
    event = OutboxEvent(
        event_type="announcement.index.sync",
        aggregate_type="announcement",
        aggregate_id=announcement.id,
        actor_id=actor_id,
        payload_json=json.dumps({"announcement_id": announcement.id}, ensure_ascii=False),
        idempotency_key=key,
    )
    db.add(event)
    db.flush()
    return event


def process_pending(db: Session, limit: int = 20) -> dict[str, int]:
    """Process durable integration events without changing the business outcome.

    Failed events remain retryable with bounded exponential backoff. The caller
    receives counts instead of an exception so an index outage never changes a
    successfully committed announcement publication into an HTTP failure.
    """
    now = utc_now()
    events = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.status.in_(["pending", "retry", "processing"]))
        .filter((OutboxEvent.next_attempt_at.is_(None)) | (OutboxEvent.next_attempt_at <= now))
        .order_by(OutboxEvent.created_at)
        .limit(limit)
        .all()
    )
    result = {"processed": 0, "failed": 0}
    for candidate in events:
        event_id = candidate.id
        try:
            claimed = (
                db.query(OutboxEvent)
                .filter(OutboxEvent.id == event_id)
                .filter(OutboxEvent.status == candidate.status)
                .filter((OutboxEvent.next_attempt_at.is_(None)) | (OutboxEvent.next_attempt_at <= now))
                .update(
                    {
                        OutboxEvent.status: "processing",
                        OutboxEvent.attempts: OutboxEvent.attempts + 1,
                        # A crashed worker's lease becomes eligible again.
                        OutboxEvent.next_attempt_at: now + timedelta(minutes=5),
                    },
                    synchronize_session=False,
                )
            )
            if claimed != 1:
                db.rollback()
                continue
            db.commit()
            event = db.get(OutboxEvent, event_id)
            if event.event_type == "announcement.index.sync":
                announcement = db.get(Announcement, event.aggregate_id)
                if not announcement:
                    raise RuntimeError("announcement no longer exists")
                from rag.service import sync_published_announcement
                sync_published_announcement(db, announcement, event.actor_id or announcement.created_by)
            else:
                raise RuntimeError(f"unsupported outbox event: {event.event_type}")
            event = db.get(OutboxEvent, event_id)
            event.status = "completed"
            event.last_error = None
            event.next_attempt_at = None
            event.processed_at = utc_now()
            db.commit()
            result["processed"] += 1
        except Exception as exc:
            db.rollback()
            event = db.get(OutboxEvent, event_id)
            if event:
                event.status = "retry"
                event.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                event.next_attempt_at = utc_now() + timedelta(seconds=min(3600, 2 ** min(event.attempts, 10)))
                db.commit()
            result["failed"] += 1
    return result
