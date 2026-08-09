from __future__ import annotations

import json
from hashlib import sha256
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from data_pipeline.types import DatasetSpec
from api.time import utc_now


def _dt(value: object):
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def import_normalized_file(db: Session, spec: DatasetSpec, path: Path, manifest_path: str) -> dict[str, int]:
    """Idempotently load only normalised, sanitized public records into external schema."""
    from api.models import PublicCase, PublicDataset
    dataset = db.query(PublicDataset).filter_by(dataset_id=spec.dataset_id).first()
    if not dataset:
        dataset = PublicDataset(dataset_id=spec.dataset_id, dataset_name=spec.name, country=spec.country, city=spec.city, publisher=spec.publisher, source_url=spec.source_url, api_url=spec.api_url, license=spec.license, license_url=spec.license_url, manifest_path=manifest_path)
        db.add(dataset); db.flush()
    counts = {"created":0, "updated":0, "input":0}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line); counts["input"] += 1
            item = db.query(PublicCase).filter_by(source_dataset_id=spec.dataset_id, source_record_id=row["source_record_id"]).first()
            raw_payload = row.get("source_payload") or {}
            trace = {
                "source_field_names": sorted(raw_payload),
                "source_row_sha256": sha256(json.dumps(raw_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
            }
            payload = {key: row.get(key) for key in ("source_type","source_country","source_dataset","source_dataset_id","source_record_id","source_url","source_license","original_language","translation_status","normalization_version","mapping_version","record_kind","external_category","external_subcategory","source_status","normalized_status","sanitized_text","normalized_category","normalized_subcategory","risk_level","mapping_method","location_city","location_district","location_zip_prefix")}
            payload.update({"original_text":None,"source_retrieved_at":_dt(row.get("source_retrieved_at")),"occurred_at":_dt(row.get("occurred_at")),"resolved_at":_dt(row.get("resolved_at")),"mapping_confidence":float(row.get("mapping_confidence") or 0),"source_payload_json":json.dumps(trace, ensure_ascii=False, sort_keys=True)})
            if item:
                for key, value in payload.items(): setattr(item, key, value)
                counts["updated"] += 1
            else:
                db.add(PublicCase(**payload)); counts["created"] += 1
            if counts["input"] % 500 == 0:
                db.commit()
    dataset.row_count = counts["input"]; dataset.imported_at = utc_now(); db.commit()
    return counts
