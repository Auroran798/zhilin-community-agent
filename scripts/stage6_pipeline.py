"""CLI for repeatable Stage 6 public-real ingestion. Never scrapes HTML or uses credentials."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.config import MANIFEST_DIR, NORMALIZED_DIR, PROCESSED_DIR, PROFILE_DIR, RAW_DIR, SAMPLES_DIR
from data_pipeline.downloaders import SocrataDownloader
from data_pipeline.mapping import write_mapping_catalog
from data_pipeline.normalization import normalize_file
from data_pipeline.profiling import profile_jsonl, write_profile
from data_pipeline.registry import SELECTED_DATASETS, candidate_rows
from data_pipeline.reports import write_stage6_reports


def paths(spec):
    return RAW_DIR / f"{spec.slug}.jsonl", PROCESSED_DIR / f"{spec.slug}.jsonl", NORMALIZED_DIR / f"{spec.slug}.jsonl", MANIFEST_DIR / f"{spec.slug}_manifest.json"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def line_count(path: Path) -> int:
    return sum(1 for _ in path.open("r", encoding="utf-8")) if path.exists() else 0


def research() -> None:
    rows = candidate_rows(); path = Path("data/source_research/dataset_candidates.csv"); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    selected = [row for row in rows if row["selected"] == "yes"]
    registry = Path("data/public_real/source_registry.csv"); registry.parent.mkdir(parents=True, exist_ok=True)
    with registry.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["dataset_id", "dataset_name", "source_url", "api_url", "publisher", "country", "city", "license", "license_verified", "selected", "selection_reason", "verified_at"]); writer.writeheader(); writer.writerows([{key: row[key] for key in writer.fieldnames} for row in selected])
    write_mapping_catalog(Path("data/mappings/external_category_mapping.csv"))
    print(f"research: candidates={len(rows)} selected={len(selected)}")


def write_manifest(spec, raw: Path, outcome: dict) -> dict:
    manifest = {"dataset_name":spec.name,"dataset_id":spec.dataset_id,"source_url":spec.source_url,"api_url":spec.api_url,"publisher":spec.publisher,"country":spec.country,"retrieved_at":datetime.now(timezone.utc).isoformat(),"license":spec.license,"license_url":spec.license_url,"original_format":"JSON from official Socrata SODA API","file_name":raw.name,"file_size":raw.stat().st_size,"sha256":checksum(raw),"row_count":line_count(raw),"column_count":len(spec.selected_fields),"encoding":"UTF-8 JSONL","download_method":"official SODA API, deterministic random-offset sampling across published row range, no credentials","page_size":SocrataDownloader().page_size,"resume":True,"download_outcome":outcome,"privacy_minimization":"The API select list excludes street address, house number, apartment, latitude and longitude."}
    manifest_path = paths(spec)[3]; manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def download(work_order_rows: int, violation_rows: int) -> list[dict]:
    results = []; downloader = SocrataDownloader()
    for spec in SELECTED_DATASETS:
        raw, _, _, _ = paths(spec); target = work_order_rows if spec.record_kind == "work_order" else violation_rows
        outcome = downloader.download_stratified(spec, raw, target); results.append(write_manifest(spec, raw, outcome)); print(f"download: {spec.slug} {outcome}")
    return results


def profile() -> list[dict]:
    reports = []
    for spec in SELECTED_DATASETS:
        raw, _, _, _ = paths(spec)
        if not raw.exists():
            raise FileNotFoundError(f"Missing raw data: {raw}. Run download first.")
        report = profile_jsonl(raw, spec.source_id_field, (spec.category_field,), ("problem_status", "complaint_status") if spec.record_kind == "work_order" else ("currentstatus", "violationstatus"), ("status_description",) if spec.record_kind == "work_order" else ("novdescription",), ("received_date", "problem_status_date") if spec.record_kind == "work_order" else ("inspectiondate", "currentstatusdate"))
        write_profile(report, PROFILE_DIR / f"{spec.slug}_profile.json", PROFILE_DIR / f"{spec.slug}_profile.md"); reports.append(report)
        _, _, normalized, _ = paths(spec)
        if normalized.exists():
            normalized_report=profile_jsonl(normalized, "source_record_id", ("normalized_category",), ("normalized_status",), ("sanitized_text",), ("occurred_at", "resolved_at"))
            write_profile(normalized_report, PROFILE_DIR / f"{spec.slug}_normalized_profile.json", PROFILE_DIR / f"{spec.slug}_normalized_profile.md")
        print(f"profile: {spec.slug} rows={report['row_count']}")
    return reports


def normalize() -> list[dict]:
    results=[]
    for spec in SELECTED_DATASETS:
        raw, processed, normalized, _ = paths(spec)
        if not raw.exists(): raise FileNotFoundError(f"Missing raw data: {raw}. Run download first.")
        result=normalize_file(spec, raw, processed, normalized); result["dataset_id"]=spec.dataset_id; results.append(result); print(f"normalize: {spec.slug} {result}")
        sample_path=SAMPLES_DIR / f"{spec.slug}_sanitized_sample.jsonl"
        allowed=("source_dataset_id","source_record_id","record_kind","source_country","original_language","translation_status","external_category","normalized_category","risk_level","normalized_status","sanitized_text","occurred_at","resolved_at","location_city","location_district","location_zip_prefix")
        with normalized.open("r",encoding="utf-8") as source, sample_path.open("w",encoding="utf-8",newline="\n") as sample:
            for _, line in zip(range(10), source):
                row=json.loads(line); sample.write(json.dumps({key:row.get(key) for key in allowed},ensure_ascii=False)+"\n")
    return results


def import_data() -> list[dict]:
    from api.database import SessionLocal
    from data_pipeline.importers import import_normalized_file
    results=[]; db=SessionLocal()
    try:
        for spec in SELECTED_DATASETS:
            _, _, normalized, manifest = paths(spec)
            if not normalized.exists(): raise FileNotFoundError(f"Missing normalized data: {normalized}. Run normalize first.")
            result=import_normalized_file(db, spec, normalized, str(manifest).replace("\\", "/")); result["dataset_id"]=spec.dataset_id; results.append(result); print(f"import: {spec.slug} {result}")
    finally:
        db.close()
    return results


def prepare_evaluation(size: int = 320) -> dict:
    """Create a blind annotation worksheet; never manufacture gold labels."""
    examples=[]
    for spec in SELECTED_DATASETS:
        _,_,normalized,_=paths(spec)
        if normalized.exists():examples.extend((spec.record_kind,json.loads(line)) for line in normalized.open("r",encoding="utf-8"))
    if not examples:raise FileNotFoundError("No normalized records available for evaluation sampling")
    rng=random.Random(20260807);rng.shuffle(examples);selected=examples[:max(size,300)]
    path=Path("evals/stage6/category_mapping_annotation.jsonl");path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="\n") as output:
        for kind,row in selected:
            output.write(json.dumps({"source_dataset_id":row["source_dataset_id"],"source_record_id":row["source_record_id"],"record_kind":kind,"external_category":row.get("external_category"),"original_text":row.get("original_text"),"expected_category":None,"review_status":"pending_human_review","reviewer":None,"reviewed_at":None},ensure_ascii=False)+"\n")
    result={"status":"READY_FOR_HUMAN_REVIEW","sample_size":len(selected),"annotation_file":str(path).replace("\\","/"),"instructions":"A reviewer must fill expected_category, reviewer, reviewed_at and set review_status=human_reviewed. Do not copy model predictions into the gold file."};print(json.dumps(result,ensure_ascii=False));return result


def evaluate(size: int = 320) -> dict:
    from data_pipeline.mapping import map_category
    path=Path("evals/stage6/category_mapping_gold.jsonl")
    rows=[json.loads(line) for line in path.open("r",encoding="utf-8")] if path.exists() else []
    reviewed=[row for row in rows if row.get("review_status")=="human_reviewed" and row.get("expected_category") and row.get("reviewer") and row.get("reviewed_at")]
    if len(reviewed)<300:
        result={"status":"NOT_RUN","sample_size":len(reviewed),"required":300,"accuracy":None,"dataset":str(path).replace("\\","/"),"reason":"At least 300 independently human-reviewed gold labels are required; legacy rule-generated labels are rejected."}
    else:
        selected=reviewed[:size];correct=0;failures=[]
        for row in selected:
            predicted=map_category(row["record_kind"],row.get("external_category"),row.get("original_text"))["normalized_category"]
            ok=predicted==row["expected_category"];correct+=int(ok)
            if not ok:failures.append({"source_dataset_id":row["source_dataset_id"],"source_record_id":row["source_record_id"],"expected":row["expected_category"],"predicted":predicted})
        result={"status":"PASS","sample_size":len(selected),"correct":correct,"incorrect":len(selected)-correct,"accuracy":round(correct/len(selected),4),"dataset":str(path).replace("\\","/"),"failures":failures}
    Path("artifacts/data_quality/stage6_mapping_evaluation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(result,ensure_ascii=False));return result


def report() -> None:
    profiles=[]; manifests=[]
    for spec in SELECTED_DATASETS:
        p=PROFILE_DIR / f"{spec.slug}_profile.json"; m=paths(spec)[3]
        if p.exists(): profiles.append(json.loads(p.read_text(encoding="utf-8")))
        if m.exists(): manifests.append(json.loads(m.read_text(encoding="utf-8")))
    if not profiles or not manifests: raise FileNotFoundError("Profiles/manifests are required before report")
    write_stage6_reports(profiles,manifests,Path("docs/stage6_data_quality_report.md")); print("report: docs/stage6_data_quality_report.md")


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("command",choices=("research","download","profile","normalize","import","prepare-evaluation","evaluate","report","all")); parser.add_argument("--work-order-rows",type=int,default=51_200); parser.add_argument("--violation-rows",type=int,default=20_000); args=parser.parse_args()
    if args.command in {"research","all"}: research()
    if args.command in {"download","all"}: download(args.work_order_rows,args.violation_rows)
    if args.command in {"profile","all"}: profile()
    if args.command in {"normalize","all"}: normalize()
    if args.command in {"import","all"}: import_data()
    if args.command=="prepare-evaluation":prepare_evaluation()
    if args.command in {"evaluate","all"}:
        result=evaluate()
        if result["status"]!="PASS":raise SystemExit(2)
    if args.command in {"report","all"}: report()


if __name__ == "__main__": main()
