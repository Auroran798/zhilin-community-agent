import csv
import json
from pathlib import Path
from urllib.parse import urlparse

from data_pipeline.source_governance import file_sha256, validate_registry


FIELDS=["source_no","title","source_url","publisher","publication_date","acquired_at","version","effective_date","expiry_date","authority_status","country","jurisdiction","language","document_type","source_type","local_path","actually_downloaded","manually_verified","answerable","authority_level","license_note","license_url","contains_personal_data","minimization_rule","parser_version","review_status","checksum","translation_provider","translation_model","translation_version","notes","data_class"]


def write_registry(path:Path,row:dict):
    with path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS);writer.writeheader();writer.writerow(row)


def base_row(content:Path):
    return {"source_no":"SRC-1","title":"Rule","source_url":"https://official.example/rule","publisher":"Authority","publication_date":"2026-01-01","acquired_at":"2026-08-10","version":"1","effective_date":"2026-01-01","expiry_date":"","authority_status":"effective","country":"GB","jurisdiction":"GB","language":"en","document_type":"complaint_code","source_type":"official_public_document","local_path":content.name,"actually_downloaded":"true","manually_verified":"true","answerable":"true","authority_level":"statutory_code","license_note":"official publication terms","license_url":"https://official.example/terms","contains_personal_data":"false","minimization_rule":"","parser_version":"structured-v1","review_status":"approved","checksum":file_sha256(content),"translation_provider":"","translation_model":"","translation_version":"","notes":"","data_class":"KB_POLICY"}


def test_governed_source_registry_accepts_verified_snapshot(tmp_path):
    content=tmp_path/"rule.md";content.write_text("official rule",encoding="utf-8")
    registry=tmp_path/"registry.csv";write_registry(registry,base_row(content))
    assert validate_registry(registry,tmp_path)["status"]=="PASS"


def test_governed_source_registry_rejects_unreviewed_or_changed_snapshot(tmp_path):
    content=tmp_path/"rule.md";content.write_text("official rule",encoding="utf-8")
    row=base_row(content);row["review_status"]="pending";row["checksum"]="0"*64
    registry=tmp_path/"registry.csv";write_registry(registry,row)
    result=validate_registry(registry,tmp_path)
    assert result["status"]=="FAIL"
    assert any("not_approved" in error for error in result["errors"])
    assert any("checksum_mismatch" in error for error in result["errors"])


def test_official_download_catalog_matches_metadata_and_manifests():
    root=Path(__file__).resolve().parents[1]/"data/knowledge"
    with (root/"international_sources.csv").open(encoding="utf-8",newline="") as handle:
        allowlisted={row["source_no"]:row for row in csv.DictReader(handle)}
    with (root/"official_source_metadata.csv").open(encoding="utf-8",newline="") as handle:
        metadata={row["source_no"]:row for row in csv.DictReader(handle)}
    assert len(allowlisted)==22
    assert set(allowlisted)==set(metadata)
    for source_no,row in allowlisted.items():
        governed=metadata[source_no]
        assert urlparse(row["url"]).hostname==row["allowed_host"]
        assert governed["source_url"]==row["url"]
        assert governed["local_path"]==row["destination"]
        manifest=json.loads((root/"manifests"/f"{source_no.lower()}.json").read_text(encoding="utf-8"))
        assert manifest["source_url"]==row["url"]
        assert manifest["local_path"]==row["destination"]
        assert manifest["content_type"]==row["expected_content_type"]
        assert manifest["sha256"]==file_sha256(root/row["destination"])
