from __future__ import annotations

from fastapi.testclient import TestClient

from app.engine import RedactionService
from app.main import create_app
from app.settings import Settings
from conftest import FakeModel


def _authorization() -> dict[str, str]:
    return {"Authorization": "Bearer test-secret"}


def test_health_auth_and_safe_response(test_settings: Settings, fake_model: FakeModel) -> None:
    service = RedactionService(fake_model)
    app = create_app(test_settings, service)
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {"status": "ready"}
        assert client.post("/v1/redact", json={"text": "test@example.test"}).status_code == 401
        response = client.post(
            "/v1/redact",
            headers=_authorization(),
            json={"text": "test@example.test", "policy": "ru_resume"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["redacted_text"] == "<PRIVATE_EMAIL>"
    assert payload["summary"]["pii_check_passed"] is True
    assert "text" not in payload
    assert "detected_spans" not in payload
    assert "test@example.test" not in response.text


def test_rejects_unknown_fields(test_settings: Settings, fake_model: FakeModel) -> None:
    app = create_app(test_settings, RedactionService(fake_model))
    with TestClient(app) as client:
        response = client.post(
            "/v1/redact",
            headers=_authorization(),
            json={"text": "safe", "debug": True},
        )
    assert response.status_code == 422


def test_rejects_oversized_text(fake_model: FakeModel) -> None:
    settings = Settings(app_env="test", api_token="test-secret", max_text_chars=4)
    app = create_app(settings, RedactionService(fake_model))
    with TestClient(app) as client:
        response = client.post(
            "/v1/redact",
            headers=_authorization(),
            json={"text": "12345"},
        )
    assert response.status_code == 413
    assert "12345" not in response.text


def test_not_ready_when_model_load_fails(test_settings: Settings) -> None:
    model = FakeModel(load_error=True)
    app = create_app(test_settings, RedactionService(model))
    with TestClient(app) as client:
        ready = client.get("/health/ready")
        redact = client.post(
            "/v1/redact",
            headers=_authorization(),
            json={"text": "private@example.test"},
        )
    assert ready.status_code == 503
    assert redact.status_code == 503
    assert "private@example.test" not in redact.text


def test_docs_can_be_disabled(fake_model: FakeModel) -> None:
    settings = Settings(app_env="test", docs_enabled=False, opf_enabled=False)
    app = create_app(settings, RedactionService(fake_model))
    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404

