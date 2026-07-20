from __future__ import annotations

from app.engine import RedactionService, merge_spans
from app.rules_ru import Span
from conftest import FakeModel, FakeSpan


def test_loads_model_once_and_redacts_model_and_rule_spans() -> None:
    text = "Иван Иванов, test@example.test"
    model = FakeModel([FakeSpan("private_person", 0, 11, "Иван Иванов", "<PRIVATE_PERSON>")])
    service = RedactionService(model)
    service.load()
    result = service.redact(text, mode="typed", policy="ru_resume")
    assert model.load_calls == 1
    assert model.redact_calls == 1
    assert result.redacted_text == "<PRIVATE_PERSON>, <PRIVATE_EMAIL>"
    assert result.summary.span_count == 2
    assert result.summary.by_label == {"private_email": 1, "private_person": 1}
    assert result.summary.pii_check_passed is True


def test_specific_rule_wins_over_overlapping_model_span() -> None:
    text = "test@example.test"
    model = FakeModel([FakeSpan("private_person", 0, len(text), text, "<PRIVATE_PERSON>")])
    service = RedactionService(model)
    service.load()
    result = service.redact(text, mode="typed", policy="ru_resume")
    assert result.redacted_text == "<PRIVATE_EMAIL>"
    assert result.summary.by_label == {"private_email": 1}


def test_opf_only_policy_does_not_run_russian_rules() -> None:
    model = FakeModel()
    service = RedactionService(model)
    service.load()
    result = service.redact("test@example.test", mode="typed", policy="opf_only")
    assert result.redacted_text == "test@example.test"
    assert result.summary.pii_check_passed is True


def test_merge_spans_rejects_invalid_offsets_and_resolves_overlap() -> None:
    spans = [
        Span("low", 0, 5, "<LOW>", "opf", 10),
        Span("high", 1, 4, "<HIGH>", "rule", 100),
        Span("invalid", -1, 2, "<BAD>", "rule", 200),
    ]
    assert merge_spans(spans, 5) == [spans[1]]

