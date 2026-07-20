from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pytest

from app.engine import RedactionService
from app.settings import Settings


@dataclass(frozen=True, slots=True)
class FakeSpan:
    label: str
    start: int
    end: int
    text: str
    placeholder: str


@dataclass(frozen=True, slots=True)
class FakeResult:
    detected_spans: tuple[FakeSpan, ...]
    warning: str | None = None


class FakeModel:
    def __init__(self, spans: Iterable[FakeSpan] = (), *, load_error: bool = False) -> None:
        self.spans = tuple(spans)
        self.load_error = load_error
        self.load_calls = 0
        self.redact_calls = 0

    def load(self) -> None:
        self.load_calls += 1
        if self.load_error:
            raise RuntimeError("synthetic load failure with private details")

    def redact(self, text: str) -> FakeResult:
        self.redact_calls += 1
        return FakeResult(self.spans)


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        app_env="test",
        api_token="test-secret",
        opf_enabled=False,
        max_text_chars=10_000,
        max_request_bytes=20_000,
        queue_wait_seconds=0.05,
    )


@pytest.fixture
def fake_model() -> FakeModel:
    return FakeModel()


@pytest.fixture
def service(fake_model: FakeModel) -> RedactionService:
    return RedactionService(fake_model)

