from __future__ import annotations

import pytest

from app.engine import apply_spans, merge_spans
from app.rules_ru import RussianResumeRuleEngine


@pytest.mark.parametrize(
    ("text", "label", "placeholder"),
    [
        ("Почта candidate@example.test", "private_email", "<PRIVATE_EMAIL>"),
        ("Телефон +7 (900) 000-00-00", "private_phone", "<PRIVATE_PHONE>"),
        ("Telegram @candidate_test", "private_url", "<PRIVATE_URL>"),
        ("Профиль https://example.test/profile", "private_url", "<PRIVATE_URL>"),
        ("ИНН 123456789012", "inn", "<INN>"),
        ("СНИЛС 123-456-789 00", "snils", "<SNILS>"),
        ("Паспорт РФ 12 34 567890", "passport_number", "<PASSPORT_NUMBER>"),
        ("р/с 12345678901234567890", "bank_account", "<ACCOUNT_NUMBER>"),
        ("Карта 4111 1111 1111 1111", "bank_card", "<BANK_CARD>"),
        ("Дата рождения: 01.02.1990", "private_date", "<PRIVATE_DATE>"),
    ],
)
def test_detects_supported_russian_resume_values(text: str, label: str, placeholder: str) -> None:
    engine = RussianResumeRuleEngine()
    spans = engine.detect(text)
    assert any(span.label == label and span.placeholder == placeholder for span in spans)
    redacted = apply_spans(text, merge_spans(spans, len(text)), "typed")
    assert placeholder in redacted


@pytest.mark.parametrize(
    "text",
    [
        "Код задачи 1234567890 без подписи ИНН",
        "Невалидная карта 4111 1111 1111 1112",
        "Обычная дата проекта 01.02.2026",
        "Короткий Telegram @abc",
    ],
)
def test_avoids_common_false_positives(text: str) -> None:
    assert RussianResumeRuleEngine().detect(text) == []


def test_redacted_output_passes_second_rule_scan() -> None:
    engine = RussianResumeRuleEngine()
    text = "ИНН 123456789012, +7 900 000-00-00, test@example.test"
    spans = merge_spans(engine.detect(text), len(text))
    redacted = apply_spans(text, spans, "typed")
    assert engine.detect(redacted) == []


def test_redacted_mode_uses_untyped_placeholder() -> None:
    engine = RussianResumeRuleEngine()
    text = "Почта test@example.test"
    spans = merge_spans(engine.detect(text), len(text))
    assert apply_spans(text, spans, "redacted") == "Почта <REDACTED>"

