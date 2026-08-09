from fastapi.testclient import TestClient

from api.main import app


def test_malformed_host_is_rejected_before_route_processing():
    with TestClient(app) as client:
        response = client.get("/health", headers={"Host": "example.test/forged?path="})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_HTTP_TARGET"


def test_oversized_declared_body_is_rejected_before_form_parsing():
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", headers={"Content-Length": str(11 * 1024 * 1024)}, content=b"x")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_invalid_content_length_is_rejected_cleanly():
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", headers={"Content-Length": "not-a-number"}, content=b"x")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CONTENT_LENGTH"
