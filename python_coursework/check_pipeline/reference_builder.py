from __future__ import annotations

from .models import DocumentRecord, ReferenceRecord


SCENARIO_OVERRIDES: dict[str, dict[str, str]] = {}


def build_reference(records: list[DocumentRecord]) -> list[ReferenceRecord]:
    result: list[ReferenceRecord] = []
    for record in records:
        payload = {
            "file_name": record.file_name,
            "expected_datetime": record.primary_datetime,
            "expected_amount": record.amount,
            "expected_currency": record.currency,
            "expected_recipient_name": record.recipient_name,
            "expected_receipt_type": record.receipt_type,
            "expected_status": "matched_expected",
            "scenario_note": "Exact reference generated from extracted check",
        }
        overrides = SCENARIO_OVERRIDES.get(record.file_name, {})
        payload.update(overrides)
        result.append(ReferenceRecord(**payload))
    return result
