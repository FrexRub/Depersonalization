from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Literal


class ConfigurationError(RuntimeError):
    """Raised when service configuration is unsafe or inconsistent."""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    try:
        value = default if raw is None else int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be >= {minimum}")
    return value


def _env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = os.getenv(name)
    try:
        value = default if raw is None else float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} must be >= {minimum}")
    return value


def _read_secret(value_name: str, file_name: str) -> str | None:
    direct = os.getenv(value_name)
    path_value = os.getenv(file_name)
    if direct and path_value:
        raise ConfigurationError(f"Set only one of {value_name} and {file_name}")
    if direct:
        return direct.strip()
    if not path_value:
        return None
    path = Path(path_value)
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ConfigurationError(f"Unable to read {file_name}") from exc
    if not secret:
        raise ConfigurationError(f"{file_name} points to an empty secret")
    return secret


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: Literal["development", "test", "production"] = "development"
    api_token: str | None = None
    model_path: str | None = None
    device: Literal["cpu", "cuda"] = "cpu"
    inference_concurrency: int = 1
    queue_capacity: int = 2
    queue_wait_seconds: float = 2.0
    max_text_chars: int = 250_000
    max_request_bytes: int = 1_000_000
    docs_enabled: bool = True
    opf_enabled: bool = True

    def validate(self) -> Settings:
        if self.app_env == "production" and not self.api_token:
            raise ConfigurationError("API token is required in production")
        if self.inference_concurrency < 1:
            raise ConfigurationError("inference_concurrency must be >= 1")
        if self.queue_capacity < 0:
            raise ConfigurationError("queue_capacity must be >= 0")
        if self.max_text_chars < 1 or self.max_request_bytes < 1:
            raise ConfigurationError("request limits must be positive")
        return self


def load_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env not in {"development", "test", "production"}:
        raise ConfigurationError("APP_ENV must be development, test, or production")

    device = os.getenv("OPF_DEVICE", "cpu").strip().lower()
    if device not in {"cpu", "cuda"}:
        raise ConfigurationError("OPF_DEVICE must be cpu or cuda")

    model_path = os.getenv("OPF_MODEL_PATH")
    settings = Settings(
        app_env=app_env,  # type: ignore[arg-type]
        api_token=_read_secret("API_TOKEN", "API_TOKEN_FILE"),
        model_path=model_path.strip() if model_path else None,
        device=device,  # type: ignore[arg-type]
        inference_concurrency=_env_int("INFERENCE_CONCURRENCY", 1, minimum=1),
        queue_capacity=_env_int("INFERENCE_QUEUE_CAPACITY", 2),
        queue_wait_seconds=_env_float("INFERENCE_QUEUE_WAIT_SECONDS", 2.0),
        max_text_chars=_env_int("MAX_TEXT_CHARS", 250_000, minimum=1),
        max_request_bytes=_env_int("MAX_REQUEST_BYTES", 1_000_000, minimum=1),
        docs_enabled=_env_bool("DOCS_ENABLED", app_env != "production"),
        opf_enabled=_env_bool("OPF_ENABLED", True),
    )
    return settings.validate()

