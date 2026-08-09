from datetime import datetime

from api.config import settings
from api.database import get_db
from api.main import app
from api.models import PublicCase, PublicDataset, WorkOrder
from harness.service import ExecutionContext, get_harness
from test_isolated_integration import isolated_client


def _login(client, username):
    result = client.post("/api/v1/auth/login", json={"username": username, "password": "DemoPass123!"})
    return {"Authorization": "Bearer " + result.json()["data"]["access_token"]}


def _public_case(db):
    dataset = PublicDataset(dataset_id="hpd-test", dataset_name="HPD test", country="US", city="New York City", publisher="HPD", source_url="https://example.test/source", api_url="https://example.test/api", license="test terms", license_url="https://example.test/terms", manifest_path="data/public_real/manifests/test.json", row_count=1)
    db.add(dataset); db.flush()
    item = PublicCase(source_type="public_real", source_country="US", source_dataset="HPD test", source_dataset_id=dataset.dataset_id, source_record_id="case-1", source_url="https://example.test/source/case-1", source_license="test terms", source_retrieved_at=datetime.utcnow(), original_language="en", translation_status="not_translated", normalization_version="stage6-v1", mapping_version="stage6-v1", record_kind="inspection_rectification", external_category="C", source_status="VIOLATION OPEN", normalized_status="open", original_text="Apartment 12B at 123 Main Street", sanitized_text="[UNIT_REDACTED] unsafe smoke detector", normalized_category="消防设施", normalized_subcategory="fire_safety", risk_level="high", mapping_method="keyword_rule", mapping_confidence=0.85, occurred_at=datetime.utcnow(), location_city="New York City", location_district="BROOKLYN", location_zip_prefix="112", source_payload_json='{"street":"not exposed"}')
    db.add(item); db.commit(); return item


def test_public_real_api_is_staff_only_and_never_leaks_raw_payload(isolated_client, monkeypatch):
    client, _ = isolated_client
    db = next(app.dependency_overrides[get_db]())
    _public_case(db); db.close()
    monkeypatch.setattr(settings, "data_mode", "public_real")
    resident = _login(client, "r"); manager = _login(client, "m")
    assert client.get("/api/v1/public-real/cases", headers=resident).status_code == 403
    response = client.get("/api/v1/public-real/cases", headers=manager)
    assert response.status_code == 200
    row = response.json()["items"][0]
    assert row["sanitized_text"] == "[UNIT_REDACTED] unsafe smoke detector"
    assert "original_text" not in row and "source_payload_json" not in row
    assert client.get(f"/api/v1/public-real/cases/{row['id']}", headers=manager).status_code == 200


def test_public_real_harness_tool_is_read_only_and_role_gated(isolated_client, monkeypatch):
    client, ids = isolated_client
    db = next(app.dependency_overrides[get_db]())
    _public_case(db)
    monkeypatch.setattr(settings, "data_mode", "public_real")
    manager = get_harness().execute(db, ExecutionContext(user_id=ids["manager"], role="manager", source="test"), "search_public_real_cases", {"category": "消防设施"})
    assert manager.ok and manager.data["mode"] == "public_real" and len(manager.data["items"]) == 1
    resident = get_harness().execute(db, ExecutionContext(user_id=ids["resident"], role="resident", source="test"), "search_public_real_cases", {})
    assert not resident.ok and resident.error["code"] == "FORBIDDEN"
    assert get_harness().registry["search_public_real_cases"].operation_type == "read"
    db.close()


def test_public_real_agent_query_is_staff_only_and_never_creates_work_order(isolated_client, monkeypatch):
    client, _ = isolated_client
    db = next(app.dependency_overrides[get_db]())
    _public_case(db)
    before = db.query(WorkOrder).count()
    db.close()
    monkeypatch.setattr(settings, "data_mode", "public_real")

    manager = _login(client, "m")
    session = client.post("/api/v1/agent/sessions", headers=manager).json()["data"]
    response = client.post(
        f"/api/v1/agent/sessions/{session['id']}/messages",
        headers=manager,
        json={"content": "\u67e5\u8be2\u516c\u5f00\u5386\u53f2\u771f\u5b9e\u6848\u4f8b"},
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["intent"] == "public_real_case_query"
    assert result["tool_result"]["mode"] == "public_real"

    db = next(app.dependency_overrides[get_db]())
    assert db.query(WorkOrder).count() == before
    db.close()

    resident = _login(client, "r")
    resident_session = client.post("/api/v1/agent/sessions", headers=resident).json()["data"]
    denied = client.post(
        f"/api/v1/agent/sessions/{resident_session['id']}/messages",
        headers=resident,
        json={"content": "\u67e5\u8be2\u516c\u5f00\u5386\u53f2\u771f\u5b9e\u6848\u4f8b"},
    )
    assert denied.status_code == 400
