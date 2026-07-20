from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Iterable


Validator = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class Span:
    label: str
    start: int
    end: int
    placeholder: str
    source: str
    priority: int = 100

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class Rule:
    label: str
    pattern: re.Pattern[str]
    placeholder: str
    group: str | int = 0
    validator: Validator | None = None
    priority: int = 100


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _valid_phone(value: str) -> bool:
    digits = _digits(value)
    return len(digits) == 11 and digits[0] in {"7", "8"}


def _valid_luhn(value: str) -> bool:
    digits = _digits(value)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        number = int(char)
        if index % 2 == parity:
            number *= 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


RULES: tuple[Rule, ...] = (
    Rule(
        "private_email",
        re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}(?![\w.-])", re.I),
        "<PRIVATE_EMAIL>",
        priority=150,
    ),
    Rule(
        "private_url",
        re.compile(r"(?<!\w)(?:https?://|www\.)[^\s<>\]\[(){}]+", re.I),
        "<PRIVATE_URL>",
        priority=120,
    ),
    Rule(
        "private_url",
        re.compile(r"(?<![\w/])(?:t\.me|telegram\.me)/[A-Za-z0-9_]{5,32}(?!\w)", re.I),
        "<PRIVATE_URL>",
        priority=145,
    ),
    Rule(
        "private_url",
        re.compile(r"(?<![\w@])@[A-Za-z][A-Za-z0-9_]{4,31}(?!\w)"),
        "<PRIVATE_URL>",
        priority=140,
    ),
    Rule(
        "private_phone",
        re.compile(r"(?<!\d)(?:\+7|8)[\s(.-]*\d{3}[\s).\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)"),
        "<PRIVATE_PHONE>",
        validator=_valid_phone,
        priority=150,
    ),
    Rule(
        "snils",
        re.compile(r"(?<!\d)\d{3}[-\s]?\d{3}[-\s]?\d{3}\s?\d{2}(?!\d)"),
        "<SNILS>",
        priority=135,
    ),
    Rule(
        "passport_number",
        re.compile(
            r"(?i)(?:паспорт(?:\s+рф)?|серия(?:\s+и\s+номер)?)[\s:#№-]*"
            r"(?P<value>\d{2}\s?\d{2}[\s-]?\d{6})(?!\d)"
        ),
        "<PASSPORT_NUMBER>",
        group="value",
        priority=155,
    ),
    Rule(
        "inn",
        re.compile(r"(?i)(?:инн)[\s:#№-]*(?P<value>\d{10}|\d{12})(?!\d)"),
        "<INN>",
        group="value",
        priority=155,
    ),
    Rule(
        "bank_account",
        re.compile(
            r"(?i)(?:р/с|расч[её]тн(?:ый|ого)\s+сч[её]т|лицев(?:ой|ого)\s+сч[её]т|сч[её]т)"
            r"[\s:#№-]*(?P<value>\d{20})(?!\d)"
        ),
        "<ACCOUNT_NUMBER>",
        group="value",
        priority=155,
    ),
    Rule(
        "bank_card",
        re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"),
        "<BANK_CARD>",
        validator=_valid_luhn,
        priority=130,
    ),
    Rule(
        "private_date",
        re.compile(
            r"(?i)(?:дата\s+рождения|д\.?\s*р\.?|родил(?:ся|ась))"
            r"[\s:,-]*(?P<value>(?:0?[1-9]|[12]\d|3[01])[./-](?:0?[1-9]|1[0-2])[./-](?:19|20)\d{2})"
        ),
        "<PRIVATE_DATE>",
        group="value",
        priority=145,
    ),
)


class RussianResumeRuleEngine:
    def __init__(self, rules: Iterable[Rule] = RULES) -> None:
        self._rules = tuple(rules)

    def detect(self, text: str) -> list[Span]:
        spans: list[Span] = []
        for rule in self._rules:
            for match in rule.pattern.finditer(text):
                value = match.group(rule.group)
                if rule.validator is not None and not rule.validator(value):
                    continue
                start, end = match.span(rule.group)
                spans.append(
                    Span(
                        label=rule.label,
                        start=start,
                        end=end,
                        placeholder=rule.placeholder,
                        source="rule",
                        priority=rule.priority,
                    )
                )
        return spans

