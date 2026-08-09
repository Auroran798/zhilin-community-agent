from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.mapping.category import map_category
from data_pipeline.privacy.sanitizer import PrivacySanitizer
from data_pipeline.types import DatasetSpec

NORMALIZATION_VERSION = "stage6-v1"
MAPPING_VERSION = "stage6-v1"


def _source_url(spec: DatasetSpec, record_id: str) -> str:
    return f"{spec.source_url}?source_record_id={record_id}"


def _complaint(row: dict, spec: DatasetSpec, retrieved_at: str, sanitizer: PrivacySanitizer) -> dict:
    category = row.get("major_category") or ""
    original = " | ".join(str(row.get(x, "")) for x in ("major_category", "minor_category", "problem_code", "status_description") if row.get(x))
    mapping = map_category("work_order", category, original)
    source_id = str(row[spec.source_id_field])
    return {"source_type":"public_real","source_country":spec.country,"source_dataset":spec.name,"source_dataset_id":spec.dataset_id,"source_record_id":source_id,"source_url":_source_url(spec, source_id),"source_license":spec.license,"source_retrieved_at":retrieved_at,"original_language":"en","translation_status":"not_translated","translation_provider":None,"translation_model":None,"translation_version":None,"translated_at":None,"human_verified":False,"normalization_version":NORMALIZATION_VERSION,"mapping_version":MAPPING_VERSION,"record_kind":"work_order","external_category":category,"external_subcategory":row.get("minor_category"),"source_status":row.get("problem_status") or row.get("complaint_status"),"normalized_status":"closed" if (row.get("problem_status") or row.get("complaint_status")) == "CLOSE" else "open","original_text":original,"sanitized_text":sanitizer.sanitize_text(original),"normalized_category":mapping["normalized_category"],"normalized_subcategory":mapping["normalized_subcategory"],"risk_level":mapping["default_risk"],"mapping_method":mapping["mapping_method"],"mapping_confidence":mapping["mapping_confidence"],"occurred_at":row.get("received_date"),"resolved_at":row.get("problem_status_date") or row.get("complaint_status_date"),"location_city":"New York City","location_district":row.get("borough"),"location_zip_prefix":str(row.get("post_code") or "")[:3] or None,"source_payload":row}


def _violation(row: dict, spec: DatasetSpec, retrieved_at: str, sanitizer: PrivacySanitizer) -> dict:
    external = str(row.get("class") or "")
    original = str(row.get("novdescription") or "")
    mapping = map_category("inspection_rectification", external, original)
    source_id = str(row[spec.source_id_field])
    return {"source_type":"public_real","source_country":spec.country,"source_dataset":spec.name,"source_dataset_id":spec.dataset_id,"source_record_id":source_id,"source_url":_source_url(spec, source_id),"source_license":spec.license,"source_retrieved_at":retrieved_at,"original_language":"en","translation_status":"not_translated","translation_provider":None,"translation_model":None,"translation_version":None,"translated_at":None,"human_verified":False,"normalization_version":NORMALIZATION_VERSION,"mapping_version":MAPPING_VERSION,"record_kind":"inspection_rectification","external_category":external,"external_subcategory":row.get("violationstatus"),"source_status":row.get("currentstatus") or row.get("violationstatus"),"normalized_status":"closed" if "CLOSE" in str(row.get("currentstatus") or row.get("violationstatus") or "").upper() else "open","original_text":original,"sanitized_text":sanitizer.sanitize_text(original),"normalized_category":mapping["normalized_category"],"normalized_subcategory":mapping["normalized_subcategory"],"risk_level":mapping["default_risk"],"mapping_method":mapping["mapping_method"],"mapping_confidence":mapping["mapping_confidence"],"occurred_at":row.get("inspectiondate") or row.get("novissueddate"),"resolved_at":row.get("currentstatusdate"),"location_city":"New York City","location_district":row.get("boro"),"location_zip_prefix":str(row.get("zip") or "")[:3] or None,"source_payload":row}


def normalize_file(spec: DatasetSpec, raw_path: Path, processed_path: Path, normalized_path: Path) -> dict[str, int]:
    sanitizer = PrivacySanitizer()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    processed_path.parent.mkdir(parents=True, exist_ok=True); normalized_path.parent.mkdir(parents=True, exist_ok=True)
    unique: set[str] = set(); counts = {"input":0,"duplicate":0,"normalized":0,"pii_hits":0,"unmapped":0}
    with raw_path.open("r", encoding="utf-8") as source, processed_path.open("w", encoding="utf-8", newline="\n") as processed, normalized_path.open("w", encoding="utf-8", newline="\n") as normalized:
        for line in source:
            row = json.loads(line); counts["input"] += 1
            record_id = str(row.get(spec.source_id_field, ""))
            if not record_id or record_id in unique:
                counts["duplicate"] += 1; continue
            unique.add(record_id)
            record = _complaint(row, spec, retrieved_at, sanitizer) if spec.record_kind == "work_order" else _violation(row, spec, retrieved_at, sanitizer)
            counts["pii_hits"] += sanitizer.pii_hits(record["original_text"])
            counts["unmapped"] += int(not record.get("normalized_category"))
            processed.write(json.dumps({"source_record_id":record_id,"sanitized_text":record["sanitized_text"],"location_city":record["location_city"],"location_district":record["location_district"],"location_zip_prefix":record["location_zip_prefix"]}, ensure_ascii=False) + "\n")
            normalized.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            counts["normalized"] += 1
    return counts
