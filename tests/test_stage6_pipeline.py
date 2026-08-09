import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base
from api.models import PublicCase
from data_pipeline.importers.public_real import import_normalized_file
from data_pipeline.mapping import map_category
from data_pipeline.privacy import PrivacySanitizer
from data_pipeline.types import DatasetSpec


def test_stage6_privacy_sanitizer_redacts_contact_and_unit_details():
    text = "Call 212-555-0199 or owner@example.com. Apartment 5B at 123 Main Street."
    sanitized = PrivacySanitizer().sanitize_text(text)
    assert "212-555-0199" not in sanitized
    assert "owner@example.com" not in sanitized
    assert "Apartment 5B" not in sanitized
    assert "123 Main Street" not in sanitized
    assert "[PHONE_REDACTED]" in sanitized and "[EMAIL_REDACTED]" in sanitized


def test_stage6_mapping_reuses_existing_property_categories():
    assert map_category("work_order", "ELEVATOR")["normalized_category"] == "电梯"
    assert map_category("work_order", "ELECTRIC")["normalized_category"] == "配电设施"
    assert map_category("inspection_rectification", "C", "unsafe smoke detector")["normalized_category"] == "消防设施"
    fallback = map_category("inspection_rectification", "A", "paint wall")
    assert fallback["normalized_category"] == "其他"
    assert fallback["mapping_method"] == "default_other"


def test_stage6_business_import_never_persists_raw_text_or_source_payload(tmp_path):
    path = tmp_path / "normalized.jsonl"
    raw_value = "Apartment 12B at 123 Main Street; owner@example.com"
    record = {
        "source_type": "public_real", "source_country": "US", "source_dataset": "Test", "source_dataset_id": "test", "source_record_id": "source-1", "source_url": "https://example.test/1", "source_license": "terms", "source_retrieved_at": "2026-08-07T00:00:00+00:00", "original_language": "en", "translation_status": "not_translated", "normalization_version": "stage6-v1", "mapping_version": "stage6-v1", "record_kind": "work_order", "external_category": "TEST", "source_status": "OPEN", "normalized_status": "open", "original_text": raw_value, "sanitized_text": "[UNIT_REDACTED] address removed", "normalized_category": "\u5176\u4ed6", "risk_level": "low", "mapping_method": "keyword_rule", "mapping_confidence": 0.8, "occurred_at": "2026-08-01T00:00:00+00:00", "location_city": "Test City", "source_payload": {"description": raw_value, "email": "owner@example.com"},
    }
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    spec = DatasetSpec("test", "test", "Test", "example.test", "US", "Test City", "Test publisher", "https://example.test", "https://example.test/api", "https://example.test/data", "terms", "https://example.test/terms", "work_order", "id", ("id",), "id", "category", 1)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    import_normalized_file(session, spec, path, "manifest.json")
    item = session.query(PublicCase).one()
    assert item.original_text is None
    assert raw_value not in item.source_payload_json
    assert "owner@example.com" not in item.source_payload_json
    assert "source_row_sha256" in item.source_payload_json
    session.close()
