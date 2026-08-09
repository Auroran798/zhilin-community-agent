"""Stage 6 pilot endpoints: audited, manager-only and strictly read-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from domain.property_system import AdapterNotFound, AdapterUnavailable, get_property_system_adapter

from .database import get_db
from .models import User
from .security import require_roles
from .services import audit

router = APIRouter(prefix="/api/v1/integrations/property-systems", tags=["property-system-integration"])


def _adapter():
    from .config import settings
    if not settings.stage6_readonly_integration_enabled:
        raise HTTPException(503, "Stage 6 read-only integration is disabled")
    try:
        return get_property_system_adapter()
    except AdapterNotFound as exc:
        raise HTTPException(503, str(exc)) from exc


def _upstream_error(exc: AdapterUnavailable) -> HTTPException:
    return HTTPException(503, "Property system is unavailable; no data was inferred or fabricated")


@router.get("/status")
def integration_status(user: User = Depends(require_roles("manager"))):
    try:
        return _adapter().healthcheck()
    except AdapterUnavailable as exc:
        raise _upstream_error(exc) from exc


@router.get("/work-orders")
def list_external_work_orders(
    status: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_roles("manager")),
    db: Session = Depends(get_db),
):
    try:
        items, total = _adapter().list_work_orders(status=status, limit=limit, offset=offset)
    except AdapterUnavailable as exc:
        raise _upstream_error(exc) from exc
    audit(db, user, "list_external_work_orders", "external_work_order", None, request_id="stage6-readonly")
    db.commit()
    return {"items": [item.model_dump(mode="json") for item in items], "total": total, "limit": limit, "offset": offset, "mode": "read_only"}


@router.get("/work-orders/{external_id}")
def get_external_work_order(external_id: str, user: User = Depends(require_roles("manager")), db: Session = Depends(get_db)):
    try:
        item = _adapter().get_work_order(external_id)
    except AdapterNotFound as exc:
        raise HTTPException(404, "External work order was not found") from exc
    except AdapterUnavailable as exc:
        raise _upstream_error(exc) from exc
    audit(db, user, "view_external_work_order", "external_work_order", external_id, request_id="stage6-readonly")
    db.commit()
    return {"item": item.model_dump(mode="json"), "mode": "read_only"}
