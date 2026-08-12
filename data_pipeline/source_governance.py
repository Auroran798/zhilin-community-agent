"""Validation for controlled knowledge-source registries and immutable snapshots."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_COLUMNS={
    "source_no","title","source_url","publisher","publication_date","acquired_at","version",
    "effective_date","expiry_date","authority_status",
    "country","jurisdiction","language","document_type","source_type","local_path","actually_downloaded",
    "manually_verified","answerable","authority_level","license_note","license_url","contains_personal_data",
    "minimization_rule","parser_version","review_status","checksum","notes","data_class",
}
TRUE_VALUES={"1","true","yes","y"}


def truth(value: str | None) -> bool:
    return str(value or "").strip().lower() in TRUE_VALUES


def file_sha256(path: Path) -> str:
    hasher=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""): hasher.update(block)
    return hasher.hexdigest()


def validate_registry(registry_path: Path, content_root: Path) -> dict:
    errors=[];warnings=[];checked=0;source_numbers=set();source_urls=set()
    with registry_path.open(encoding="utf-8-sig",newline="") as handle:
        reader=csv.DictReader(handle);columns=set(reader.fieldnames or [])
        missing_columns=sorted(REQUIRED_COLUMNS-columns)
        if missing_columns:
            return {"status":"FAIL","checked":0,"errors":[f"missing_columns:{','.join(missing_columns)}"],"warnings":[]}
        for line,row in enumerate(reader,start=2):
            checked+=1;prefix=f"line_{line}:{row.get('source_no') or 'unknown'}"
            for key,bucket in ((row["source_no"],source_numbers),(row["source_url"],source_urls)):
                if key in bucket: errors.append(f"{prefix}:duplicate:{key}")
                bucket.add(key)
            official=row["source_type"]=="official_public_document";answerable=truth(row["answerable"])
            if official and urlparse(row["source_url"]).scheme!="https": errors.append(f"{prefix}:official_source_url_must_use_https")
            if official and answerable:
                for field in ("publisher","country","jurisdiction","language","authority_level","license_note","license_url","checksum"):
                    if not row[field].strip(): errors.append(f"{prefix}:answerable_official_missing:{field}")
                if row["review_status"]!="approved" or not truth(row["manually_verified"]): errors.append(f"{prefix}:answerable_official_not_approved")
            if row["jurisdiction"]=="GLOBAL" and row["authority_level"]!="technical_standard": errors.append(f"{prefix}:global_scope_only_allowed_for_technical_standard")
            if truth(row["contains_personal_data"]) and not row["minimization_rule"].strip(): errors.append(f"{prefix}:personal_data_requires_minimization_rule")
            translation=[row.get(name,"").strip() for name in ("translation_provider","translation_model","translation_version")]
            if any(translation) and not all(translation): errors.append(f"{prefix}:incomplete_translation_provenance")
            path=content_root/row["local_path"]
            if truth(row["actually_downloaded"]):
                if not path.is_file(): errors.append(f"{prefix}:missing_local_snapshot:{path}")
                elif row["checksum"].lower()!=file_sha256(path): errors.append(f"{prefix}:checksum_mismatch")
            elif answerable: warnings.append(f"{prefix}:answerable_source_not_downloaded")
    return {"status":"PASS" if not errors else "FAIL","checked":checked,"errors":errors,"warnings":warnings}


def validate_download_manifest(manifest_path: Path, allowlist_path: Path, content_root: Path) -> dict:
    """Validate an immutable download receipt against an exact-host allowlist."""
    errors=[]
    with allowlist_path.open(encoding="utf-8-sig",newline="") as handle:
        allowed={row["source_no"]:row for row in csv.DictReader(handle)}
    payload=json.loads(manifest_path.read_text(encoding="utf-8"))
    source_no=payload.get("source_no")
    rule=allowed.get(source_no)
    if not rule:
        return {"status":"FAIL","errors":[f"source_not_allowlisted:{source_no}"]}
    if payload.get("status")!="downloaded": errors.append("manifest_not_downloaded")
    final_url=payload.get("final_url","")
    if urlparse(final_url).scheme!="https": errors.append("final_url_not_https")
    final_host=(urlparse(final_url).hostname or "").lower()
    allowed_hosts={item.strip().lower() for item in rule["allowed_redirect_hosts"].split("|") if item.strip()}
    allowed_hosts.add(rule["allowed_host"].strip().lower())
    if final_host not in allowed_hosts: errors.append(f"final_host_not_allowlisted:{final_host}")
    if not payload.get("mime_valid"): errors.append("mime_invalid")
    if not payload.get("signature_valid"): errors.append("signature_invalid")
    size=int(payload.get("size_bytes") or 0)
    if not int(rule["min_bytes"])<=size<=int(rule["max_bytes"]): errors.append(f"size_out_of_range:{size}")
    path=content_root/payload.get("local_path","")
    if not path.is_file(): errors.append(f"snapshot_missing:{path}")
    elif payload.get("sha256")!=file_sha256(path): errors.append("sha256_mismatch")
    return {"status":"PASS" if not errors else "FAIL","source_no":source_no,"errors":errors}
