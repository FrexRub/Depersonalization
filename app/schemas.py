from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RedactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    mode: Literal["typed", "redacted"] = "typed"
    policy: Literal["ru_resume", "opf_only"] = "ru_resume"


class RedactionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_mode: Literal["typed", "redacted"]
    span_count: int = Field(ge=0)
    by_label: dict[str, int]
    pii_check_passed: bool
    leftover_labels: list[str] = Field(default_factory=list)
    warning: str | None = None


class RedactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    redacted_text: str
    summary: RedactionSummary


class HealthResponse(BaseModel):
    status: Literal["ok", "ready", "not_ready"]


class ErrorResponse(BaseModel):
    detail: str

