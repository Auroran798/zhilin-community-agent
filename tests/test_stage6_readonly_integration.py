from api.config import settings
from test_isolated_integration import isolated_client


def _login(client, username):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": "DemoPass123!"})
    return {"Authorization": "Bearer " + response.json()["data"]["access_token"]}


def test_stage6_adapter_is_disabled_by_default(isolated_client):
    client, _ = isolated_client
    response = client.get("/api/v1/integrations/property-systems/status", headers=_login(client, "m"))
    assert response.status_code == 503


def test_stage6_readonly_adapter_requires_manager_and_exposes_no_write_route(isolated_client, monkeypatch):
    client, _ = isolated_client
    monkeypatch.setattr(settings, "stage6_readonly_integration_enabled", True)
    manager = _login(client, "m")
    resident = _login(client, "r")

    assert client.get("/api/v1/integrations/property-systems/status", headers=manager).json()["status"] == "ready"
    assert client.get("/api/v1/integrations/property-systems/work-orders", headers=resident).status_code == 403

    listed = client.get("/api/v1/integrations/property-systems/work-orders?limit=1", headers=manager)
    assert listed.status_code == 200
    body = listed.json()
    assert body["mode"] == "read_only" and body["total"] == 2 and len(body["items"]) == 1
    external_id = body["items"][0]["external_id"]
    assert client.get(f"/api/v1/integrations/property-systems/work-orders/{external_id}", headers=manager).status_code == 200
    assert client.post("/api/v1/integrations/property-systems/work-orders", headers=manager).status_code == 405


def test_stage6_agent_read_is_manager_only_and_never_creates_an_order(isolated_client, monkeypatch):
    client, _ = isolated_client
    monkeypatch.setattr(settings, "stage6_readonly_integration_enabled", True)
    manager = _login(client, "m")
    resident = _login(client, "r")
    manager_session = client.post("/api/v1/agent/sessions", headers=manager).json()["data"]
    response = client.post(
        f"/api/v1/agent/sessions/{manager_session['id']}/messages",
        headers=manager,
        json={"content": "查询外部工单"},
    ).json()["data"]
    assert response["intent"] == "external_work_order_query"
    assert response["tool_result"]["mode"] == "read_only"

    resident_session = client.post("/api/v1/agent/sessions", headers=resident).json()["data"]
    denied = client.post(
        f"/api/v1/agent/sessions/{resident_session['id']}/messages",
        headers=resident,
        json={"content": "查询外部工单"},
    )
    assert denied.status_code == 400
    assert "仅管理员" in denied.json()["error"]["message"]
