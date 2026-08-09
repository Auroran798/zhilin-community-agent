from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import IdempotencyRecord, User
from .time import utc_now


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def storage_key(actor_id: str, operation: str, key: str) -> str:
    return fingerprint(f"{actor_id}:{operation}:{key}")


def claim(
    db: Session,
    actor: User,
    operation: str,
    key: str | None,
    payload: Any,
) -> tuple[IdempotencyRecord | None, bool]:
    """Claim a scoped idempotency key before any business mutation.

    A replay is accepted only for the same actor, operation and canonical
    request payload. Raw client keys are never persisted.
    """
    if not key:
        return None, False
    key_hash = fingerprint(key)
    request_hash = fingerprint(_canonical(payload))
    existing = db.query(IdempotencyRecord).filter_by(
        actor_id=actor.id, operation=operation, key_hash=key_hash
    ).first()
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(409, "同一幂等键不能用于不同请求参数")
        if existing.status == "failed":
            existing.status = "in_progress"
            existing.completed_at = None
            existing.response_json = None
            db.flush()
            return existing, False
        if existing.status != "completed":
            raise HTTPException(409, "相同请求正在处理中，请稍后查询结果")
        return existing, True

    record = IdempotencyRecord(
        actor_id=actor.id,
        operation=operation,
        key_hash=key_hash,
        request_hash=request_hash,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(IdempotencyRecord).filter_by(
            actor_id=actor.id, operation=operation, key_hash=key_hash
        ).first()
        if not existing or existing.request_hash != request_hash:
            raise HTTPException(409, "幂等键冲突")
        if existing.status != "completed":
            raise HTTPException(409, "相同请求正在处理中，请稍后查询结果")
        return existing, True
    return record, False


def complete(
    record: IdempotencyRecord | None,
    resource_type: str,
    resource_id: str,
    response: Any | None = None,
) -> None:
    if not record:
        return
    record.status = "completed"
    record.resource_type = resource_type
    record.resource_id = resource_id
    record.response_json = _canonical(response) if response is not None else None
    record.completed_at = utc_now()


def fail(record: IdempotencyRecord | None) -> None:
    """Make an unsuccessful claim retryable without changing completed writes."""
    if record and record.status != "completed":
        record.status = "failed"
