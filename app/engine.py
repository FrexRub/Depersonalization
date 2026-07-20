from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import logging
from typing import Any, Literal, Protocol

from app.rules_ru import RussianResumeRuleEngine, Span
from app.schemas import RedactionSummary


logger = logging.getLogger(__name__)


class ModelRedactor(Protocol):
    def load(self) -> None: ...

    def redact(self, text: str) -> Any: ...


class OPFModelRedactor:
    """Loads the official OPF Python runtime once and reuses it."""

    def __init__(self, *, model_path: str | None, device: str) -> None:
        self._model_path = model_path
        self._device = device
        self._redactor: Any | None = None

    def load(self) -> None:
        from opf import OPF

        redactor = OPF(
            model=self._model_path,
            device=self._device,
            output_mode="typed",
        )
        redactor.get_runtime()
        self._redactor = redactor

    def redact(self, text: str) -> Any:
        if self._redactor is None:
            raise RuntimeError("OPF runtime is not loaded")
        return self._redactor.redact(text)


class DisabledModelRedactor:
    """Rule-only mode for development and deterministic tests."""

    @dataclass(frozen=True, slots=True)
    class Result:
        detected_spans: tuple[Any, ...] = ()
        warning: str | None = None

    def load(self) -> None:
        return None

    def redact(self, text: str) -> Result:
        return self.Result()


@dataclass(frozen=True, slots=True)
class ServiceResult:
    redacted_text: str
    summary: RedactionSummary


def _model_spans(result: Any) -> list[Span]:
    spans: list[Span] = []
    for item in getattr(result, "detected_spans", ()):
        label = str(item.label)
        placeholder = str(getattr(item, "placeholder", "") or f"<{label.upper()}>")
        spans.append(
            Span(
                label=label,
                start=int(item.start),
                end=int(item.end),
                placeholder=placeholder,
                source="opf",
                priority=50,
            )
        )
    return spans


def merge_spans(spans: list[Span], text_length: int) -> list[Span]:
    candidates = [span for span in spans if 0 <= span.start < span.end <= text_length]
    candidates.sort(key=lambda span: (-span.priority, -span.length, span.start, span.end))
    accepted: list[Span] = []
    for candidate in candidates:
        if any(candidate.start < existing.end and existing.start < candidate.end for existing in accepted):
            continue
        accepted.append(candidate)
    return sorted(accepted, key=lambda span: (span.start, span.end))


def apply_spans(text: str, spans: list[Span], mode: Literal["typed", "redacted"]) -> str:
    parts: list[str] = []
    cursor = 0
    for span in spans:
        parts.append(text[cursor : span.start])
        parts.append(span.placeholder if mode == "typed" else "<REDACTED>")
        cursor = span.end
    parts.append(text[cursor:])
    return "".join(parts)


class RedactionService:
    def __init__(
        self,
        model: ModelRedactor,
        rule_engine: RussianResumeRuleEngine | None = None,
    ) -> None:
        self._model = model
        self._rules = rule_engine or RussianResumeRuleEngine()
        self._ready = False
        self._load_error = False

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def load_failed(self) -> bool:
        return self._load_error

    def load(self) -> None:
        try:
            self._model.load()
        except Exception:
            self._load_error = True
            logger.exception("Privacy model initialization failed")
            raise
        self._ready = True

    def redact(
        self,
        text: str,
        *,
        mode: Literal["typed", "redacted"],
        policy: Literal["ru_resume", "opf_only"],
    ) -> ServiceResult:
        if not self._ready:
            raise RuntimeError("Privacy model is not ready")

        model_result = self._model.redact(text)
        spans = _model_spans(model_result)
        if policy == "ru_resume":
            spans.extend(self._rules.detect(text))
        merged = merge_spans(spans, len(text))
        redacted_text = apply_spans(text, merged, mode)

        leftovers = self._rules.detect(redacted_text) if policy == "ru_resume" else []
        leftover_labels = sorted({span.label for span in leftovers})
        counts = dict(sorted(Counter(span.label for span in merged).items()))
        summary = RedactionSummary(
            output_mode=mode,
            span_count=len(merged),
            by_label=counts,
            pii_check_passed=not leftovers,
            leftover_labels=leftover_labels,
            warning=getattr(model_result, "warning", None),
        )
        return ServiceResult(redacted_text=redacted_text, summary=summary)

