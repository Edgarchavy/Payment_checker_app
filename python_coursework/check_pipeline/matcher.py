from __future__ import annotations

import re

from .models import DocumentRecord, MatchResult, ReferenceRecord


def _normalized_key(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def _same_text(left: str, right: str) -> bool:
    return _normalized_key(left) == _normalized_key(right)


def _date_only(value: str) -> str:
    match = re.search(r"([0-9]{2}\.[0-9]{2}\.[0-9]{4})", value)
    return match.group(1) if match else ""


def compare_records(actual: DocumentRecord, expected: ReferenceRecord) -> MatchResult:
    score = 0
    reasons: list[str] = []

    if actual.amount == expected.expected_amount:
        score += 1
    else:
        reasons.append("amount")

    if actual.currency == expected.expected_currency:
        score += 1
    else:
        reasons.append("currency")

    if _date_only(actual.primary_datetime) == _date_only(expected.expected_datetime):
        score += 1
    else:
        reasons.append("date")

    if _same_text(actual.recipient_name, expected.expected_recipient_name):
        score += 1
    else:
        reasons.append("recipient")

    if actual.receipt_type == expected.expected_receipt_type:
        score += 1
    else:
        reasons.append("type")

    if score == 5:
        status = "matched"
    elif score >= 3:
        status = "partial_match"
    else:
        status = "mismatch"

    return MatchResult(
        file_name=actual.file_name,
        actual_amount=actual.amount,
        expected_amount=expected.expected_amount,
        actual_currency=actual.currency,
        expected_currency=expected.expected_currency,
        actual_datetime=actual.primary_datetime,
        expected_datetime=expected.expected_datetime,
        actual_recipient_name=actual.recipient_name,
        expected_recipient_name=expected.expected_recipient_name,
        actual_receipt_type=actual.receipt_type,
        expected_receipt_type=expected.expected_receipt_type,
        score=f"{score}/5",
        status=status,
        mismatch_reasons=", ".join(reasons),
        source_path=actual.source_path,
    )


def match_all(actual_rows: list[DocumentRecord], expected_rows: list[ReferenceRecord]) -> list[MatchResult]:
    expected_map = {item.file_name: item for item in expected_rows}
    results: list[MatchResult] = []
    for actual in actual_rows:
        expected = expected_map[actual.file_name]
        results.append(compare_records(actual, expected))
    return results
