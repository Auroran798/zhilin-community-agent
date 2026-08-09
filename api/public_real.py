"""Read-only staff API for sanitized historic public regulatory records."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import PublicCase, PublicDataset, User
from .security import require_roles
from .services import audit

router = APIRouter(prefix="/api/v1/public-real", tags=["public-real-data"])


def _enabled() -> None:
    if settings.data_mode != "public_real":
        raise HTTPException(503, "Public-real mode is disabled; set DATA_MODE=public_real after data import")


def _case(row: PublicCase) -> dict:
    """Never expose source payload, raw original text, exact address or coordinates."""
    return {"id":row.id,"record_kind":row.record_kind,"source_type":row.source_type,"source_country":row.source_country,"source_dataset":row.source_dataset,"source_dataset_id":row.source_dataset_id,"source_record_id":row.source_record_id,"source_url":row.source_url,"source_license":row.source_license,"source_retrieved_at":row.source_retrieved_at,"original_language":row.original_language,"translation_status":row.translation_status,"external_category":row.external_category,"external_subcategory":row.external_subcategory,"source_status":row.source_status,"normalized_status":row.normalized_status,"sanitized_text":row.sanitized_text,"normalized_category":row.normalized_category,"normalized_subcategory":row.normalized_subcategory,"risk_level":row.risk_level,"mapping_method":row.mapping_method,"mapping_confidence":float(row.mapping_confidence),"occurred_at":row.occurred_at,"resolved_at":row.resolved_at,"location_city":row.location_city,"location_district":row.location_district,"location_zip_prefix":row.location_zip_prefix,"normalization_version":row.normalization_version,"mapping_version":row.mapping_version}


@router.get("/datasets")
def datasets(user: User = Depends(require_roles("customer_service", "manager")), db: Session = Depends(get_db)):
    _enabled()
    items = [{"dataset_id":x.dataset_id,"dataset_name":x.dataset_name,"country":x.country,"city":x.city,"publisher":x.publisher,"source_url":x.source_url,"api_url":x.api_url,"license":x.license,"license_url":x.license_url,"manifest_path":x.manifest_path,"row_count":x.row_count,"imported_at":x.imported_at} for x in db.query(PublicDataset).order_by(PublicDataset.dataset_id)]
    audit(db,user,"list_public_real_datasets","public_dataset",None,request_id="stage6-public-real"); db.commit()
    return {"mode":"public_real","items":items}


@router.get("/cases")
def cases(dataset_id: str | None = None, record_kind: str | None = None, category: str | None = None, status: str | None = None, risk_level: str | None = None, q: str | None = Query(None, min_length=2, max_length=200), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), user: User = Depends(require_roles("customer_service", "manager")), db: Session = Depends(get_db)):
    _enabled(); query=db.query(PublicCase)
    if dataset_id: query=query.filter(PublicCase.source_dataset_id==dataset_id)
    if record_kind: query=query.filter(PublicCase.record_kind==record_kind)
    if category: query=query.filter(PublicCase.normalized_category==category)
    if status: query=query.filter(PublicCase.normalized_status==status)
    if risk_level: query=query.filter(PublicCase.risk_level==risk_level)
    if q: query=query.filter(PublicCase.sanitized_text.contains(q.strip()))
    total=query.count(); items=query.order_by(PublicCase.occurred_at.desc(),PublicCase.id.desc()).offset(offset).limit(min(limit,settings.public_real_query_limit)).all()
    audit(db,user,"search_public_real_cases","public_case",None,request_id="stage6-public-real"); db.commit()
    return {"mode":"public_real","items":[_case(x) for x in items],"total":total,"limit":limit,"offset":offset,"notice":"Historic public regulatory records; not current property status and not a Chinese property-management dataset."}


@router.get("/cases/{case_id}")
def case_detail(case_id: str, user: User = Depends(require_roles("customer_service", "manager")), db: Session = Depends(get_db)):
    _enabled(); item=db.get(PublicCase,case_id)
    if not item: raise HTTPException(404,"Public case not found")
    audit(db,user,"view_public_real_case","public_case",case_id,request_id="stage6-public-real"); db.commit()
    return {"mode":"public_real","item":_case(item)}


@router.get("/summary")
def summary(user: User = Depends(require_roles("customer_service", "manager")), db: Session = Depends(get_db)):
    _enabled()
    total=db.query(func.count(PublicCase.id)).scalar() or 0
    by_dataset=dict(db.query(PublicCase.source_dataset_id,func.count(PublicCase.id)).group_by(PublicCase.source_dataset_id).all())
    by_kind=dict(db.query(PublicCase.record_kind,func.count(PublicCase.id)).group_by(PublicCase.record_kind).all())
    by_category=dict(db.query(PublicCase.normalized_category,func.count(PublicCase.id)).group_by(PublicCase.normalized_category).all())
    by_risk=dict(db.query(PublicCase.risk_level,func.count(PublicCase.id)).group_by(PublicCase.risk_level).all())
    return {"mode":"public_real","total":total,"by_dataset":by_dataset,"by_kind":by_kind,"by_category":by_category,"by_risk":by_risk,"privacy":"Only sanitized text and coarse locations are returned."}
