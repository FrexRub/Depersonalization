from __future__ import annotations

from pathlib import Path

import pytest

from app.settings import ConfigurationError, Settings, load_settings


def test_production_requires_api_token() -> None:
    with pytest.raises(ConfigurationError, match="required"):
        Settings(app_env="production").validate()


def test_reads_token_from_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    token_file = tmp_path / "token"
    token_file.write_text("secret-from-file\n", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("API_TOKEN_FILE", str(token_file))
    monkeypatch.delenv("API_TOKEN", raising=False)
    assert load_settings().api_token == "secret-from-file"

